'use client';

import React, {useState, useEffect, useRef, useCallback} from 'react';
import {useRouter} from 'next/navigation';
import {motion, AnimatePresence} from 'framer-motion';
import {api, buildAuthenticatedWsUrl} from '@/lib/api';
import {socketClient} from '@/lib/socket';
import {
    Shield, Activity, Cpu, Radar, Terminal, ChevronDown, AlertTriangle,
    BrainCircuit, Zap, Eye, Network, Lock, Globe, TrendingUp,
    CheckCircle2, XCircle, Clock, Radio, Target, Crosshair, Command as CommandIcon
} from 'lucide-react';
import {GodsEyeGraph} from '@/components/vanguard/GodsEyeGraph';
import {ActionTerminal} from './ActionTerminal';
import {GlobalOpsMap} from './GlobalOpsMap';
import {CommandCenter} from '@/components/CommandCenter';
import {GlassDossier, type EntityData} from '@/components/CommandCenter/GlassDossier';
import {clsx} from 'clsx';
import {DeviceRegistry} from '@/components/devices/DeviceRegistry';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ThreatEvent {
    id: string;
    ts: string;
    text: string;
    confidence: number;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
    technique?: string;
    src_ip?: string;
}

interface LiveMetric {
    label: string;
    value: string | number;
    delta?: string;
    positive?: boolean;
    color: string;
    icon: React.ReactNode;
}

interface ActionStatus {
    label: string;
    state: 'pending' | 'success' | 'error';
    detail?: string;
}

// ─── Threat Severity Config ───────────────────────────────────────────────────

const SEV_CFG = {
    CRITICAL: {
        dot: 'bg-rose-500',
        text: 'text-rose-400',
        badge: 'bg-rose-950/50 border-rose-700 text-rose-400',
        glow: 'shadow-[0_0_8px_rgba(244,63,94,0.5)]'
    },
    HIGH: {
        dot: 'bg-orange-500',
        text: 'text-orange-400',
        badge: 'bg-orange-950/40 border-orange-700 text-orange-400',
        glow: ''
    },
    MEDIUM: {
        dot: 'bg-amber-500',
        text: 'text-amber-400',
        badge: 'bg-amber-950/30 border-amber-700 text-amber-400',
        glow: ''
    },
    LOW: {
        dot: 'bg-emerald-500',
        text: 'text-emerald-400',
        badge: 'bg-emerald-950/30 border-emerald-700 text-emerald-400',
        glow: ''
    },
    INFO: {
        dot: 'bg-slate-500',
        text: 'text-slate-400',
        badge: 'bg-slate-900 border-slate-700 text-slate-400',
        glow: ''
    },
};

// ─── Live ROE status bar ──────────────────────────────────────────────────────

const ROE_CFG = {
    PASSIVE: {
        color: 'text-slate-400',
        bg: 'bg-slate-800',
        border: 'border-slate-600',
        desc: 'Monitor only — no autonomous response',
        glow: ''
    },
    DEFENSIVE: {
        color: 'text-amber-400',
        bg: 'bg-amber-900/60',
        border: 'border-amber-600',
        desc: 'Isolate & contain — approval required for offensive action',
        glow: 'shadow-[0_0_12px_rgba(245,158,11,0.3)]'
    },
    AGGRESSIVE: {
        color: 'text-rose-400',
        bg: 'bg-rose-900/60',
        border: 'border-rose-600',
        desc: 'Full autonomous response — active counter-measures enabled',
        glow: 'shadow-[0_0_15px_rgba(244,63,94,0.4)]'
    },
};

// ─── Panel entrance animation presets ──────────────────────────────────────────
// Kept subtle and fast so the dashboard still reads as "live ops," not a
// marketing site — this is the only real "look" lever I changed without
// seeing the rest of the app's pages. Tell me if you want a bigger visual
// departure (new palette, new layout) rather than this polish pass.

const panelVariants = {
    hidden: {opacity: 0, y: 12},
    visible: (delay: number) => ({
        opacity: 1,
        y: 0,
        transition: {duration: 0.35, delay, ease: 'easeOut'},
    }),
};

// ─── Component ────────────────────────────────────────────────────────────────

const SituationRoom: React.FC = () => {
    // --- Clickable Popup Terminal Modal Feature States ---
    const [terminalOpen, setTerminalOpen] = useState(false);
    const [logs, setLogs] = useState<string[]>(["[SYSTEM]: Initializing Interactive Terminal Engine..."]);
    const [terminalInput, setTerminalInput] = useState("");

    // --- Tactical command menu (was declared with click-outside handling but
    // never actually rendered anywhere — no trigger button, no dropdown JSX.
    // Wired up below.) ---
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [actionStatus, setActionStatus] = useState<ActionStatus | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (terminalOpen && !wsRef.current) {
            const wsUrl = buildAuthenticatedWsUrl('/api/v1/ws/terminal');

            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onmessage = (e) => setLogs((prev) => [...prev, e.data]);
            ws.onclose = () => {
                wsRef.current = null;
            };
            ws.onerror = (err) => console.error("WebSocket Pipeline Error Matrix:", err);
        }
        return () => {
            if (!terminalOpen && wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [terminalOpen]);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({behavior: "smooth"});
    }, [logs]);

    const dispatchCommand = () => {
        if (!terminalInput.trim() || !wsRef.current) return;
        setLogs((prev) => [...prev, `$ ${terminalInput}`]);
        wsRef.current.send(terminalInput);
        setTerminalInput("");
    };

    const handleTerminalSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        dispatchCommand();
    };

    const router = useRouter();

    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] }>({nodes: [], links: []});
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [roeLevel, setRoeLevel] = useState<'PASSIVE' | 'DEFENSIVE' | 'AGGRESSIVE'>('PASSIVE');
    const [viewMode, setViewMode] = useState<'LOCAL' | 'GLOBAL' | 'SELF_MONITORING' | 'PERIMETER_RADAR'>('LOCAL');

    const [globalVaccines, setGlobalVaccines] = useState<{ ip: string; origin: string }[]>([]);

    const [threatFeed, setThreatFeed] = useState<ThreatEvent[]>([]);
    const [criticalCount, setCriticalCount] = useState(0);
    const [blockedCount, setBlockedCount] = useState(0);
    const [alertsToday, setAlertsToday] = useState(0);
    const [systemHealth, setSystemHealth] = useState(98);

    const feedRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const globeRef = useRef<any>(null);

    const addThreat = useCallback((event: Omit<ThreatEvent, 'id' | 'ts'>) => {
        const entry: ThreatEvent = {
            ...event,
            id: `${Date.now()}-${Math.random()}`,
            ts: new Date().toLocaleTimeString(),
        };
        setThreatFeed(prev => [entry, ...prev].slice(0, 60));
    }, []);

    const fetchStats = useCallback(async () => {
        try {
            const stats = await api.getStats();
            setAlertsToday(stats.alerts_today || 0);
            setBlockedCount(stats.blocked_threats || 0);
            setCriticalCount(stats.critical_alerts || 0);
            setSystemHealth(stats.system_health || 98);
        } catch (err) {
            console.error('Failed to fetch stats', err);
        }
    }, []);

    useEffect(() => {
        const loadIntel = async () => {
            try {
                const gData = await api.getGraph();
                setGraphData(gData);

                fetchStats();

                const tacticalFeed = await api.getTacticalFeed();
                const formattedFeed = tacticalFeed.map((item: any) => ({
                    id: item.id || `${Date.now()}-${Math.random()}`,
                    ts: new Date(item.timestamp).toLocaleTimeString(),
                    text: item.message,
                    confidence: item.confidence,
                    severity: item.level,
                    technique: item.technique,
                    src_ip: item.src_ip,
                }));
                setThreatFeed(formattedFeed);

            } catch (err: any) {
                if (err?.status === 401 || String(err?.message).toLowerCase().includes('unauthorized')) {
                    router.push('/login');
                } else {
                    console.error('Error fetching initial data:', err);
                }
            }
        };
        loadIntel();
    }, [router, fetchStats]);

    useEffect(() => {
        const interval = setInterval(fetchStats, 5000);
        return () => clearInterval(interval);
    }, [fetchStats]);

    useEffect(() => {
        socketClient.connect();

        socketClient.subscribe('ALERT', (data: any) => addThreat({
            text: data.insight || data.message || 'Unknown alert',
            severity: data.level === 'CRITICAL' ? 'CRITICAL' : 'HIGH',
            confidence: Math.round(data.confidence || 85),
            technique: data.technique,
            src_ip: data.src_ip,
        }));

        socketClient.subscribe('THREAT_INTERCEPT', (data: any) => {
            addThreat({
                text: `AI intercept: ${data.message || 'Lateral movement blocked'}`,
                severity: 'CRITICAL',
                confidence: 95
            });
        });

        socketClient.subscribe('GLOBAL_INOCULATION_EVENT', (data: any) => {
            setGlobalVaccines(prev => [{ip: data.threat_ip, origin: data.origin}, ...prev].slice(0, 3));
            addThreat({
                text: `Hive-Mind vaccine deployed for ${data.threat_ip} (Origin: ${data.origin})`,
                severity: 'INFO',
                confidence: 100
            });
        });

        return () => {
            socketClient.unsubscribe('ALERT', () => {
            });
            socketClient.unsubscribe('THREAT_INTERCEPT', () => {
            });
            socketClient.unsubscribe('GLOBAL_INOCULATION_EVENT', () => {
            });
        };
    }, [addThreat]);

    useEffect(() => {
        const handle = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) setIsMenuOpen(false);
        };
        document.addEventListener('mousedown', handle);
        return () => document.removeEventListener('mousedown', handle);
    }, []);

    // FIXED: was a bare `console.log`, so clicking a node's deep-scan action did
    // nothing visible and never touched the backend. api.investigateEntity()
    // already existed in api.ts and was unused.
    const handleDeepScan = useCallback(async (nodeId: string) => {
        setActionStatus({label: 'DEEP SCAN', state: 'pending'});
        addThreat({text: `Deep scan initiated on node ${nodeId}`, severity: 'INFO', confidence: 100});
        try {
            const result = await api.investigateEntity(nodeId);
            setActionStatus({label: 'DEEP SCAN', state: 'success'});
            addThreat({
                text: `Deep scan complete on ${nodeId}: ${result?.summary || 'analysis returned'}`,
                severity: 'INFO',
                confidence: 100,
            });
        } catch (err: any) {
            setActionStatus({label: 'DEEP SCAN', state: 'error', detail: err?.message});
            addThreat({text: `Deep scan on ${nodeId} failed: ${err?.message || 'unknown error'}`, severity: 'HIGH', confidence: 100});
        } finally {
            setTimeout(() => setActionStatus(null), 4000);
        }
    }, [addThreat]);

    // TODO: I don't have ActionTerminal.tsx, so I can't see what command
    // strings/payloads it actually sends. Right now this only writes a local
    // fake log line and never reaches the backend — send me that file and
    // I'll route these through the matching api.ts methods (isolateWarRoomHost,
    // blackholeIp, quarantineNode, etc. all already exist and are unused here).
    const handleExecuteAction = (command: string) => {
        addThreat({text: `Operator override: ${command}`, severity: 'INFO', confidence: 100});
    };

    const roe = ROE_CFG[roeLevel];

    const liveMetrics: LiveMetric[] = [
        {
            label: 'THREATS DETECTED',
            value: alertsToday,
            color: 'text-rose-400',
            delta: '+' + alertsToday,
            positive: false,
            icon: <AlertTriangle size={14} className="text-rose-500"/>
        },
        {
            label: 'THREATS BLOCKED',
            value: blockedCount,
            color: 'text-emerald-400',
            delta: '+' + blockedCount,
            positive: true,
            icon: <Shield size={14} className="text-emerald-500"/>
        },
        {
            label: 'CRITICAL ALERTS',
            value: criticalCount,
            color: 'text-orange-400',
            delta: '',
            positive: false,
            icon: <Zap size={14} className="text-orange-500"/>
        },
        {
            label: 'SYSTEM HEALTH',
            value: `${systemHealth}%`,
            color: systemHealth > 85 ? 'text-emerald-400' : 'text-amber-400',
            delta: '',
            positive: true,
            icon: <Activity size={14} className="text-cyan-500"/>
        },
    ];

    // ─── Cyber command menu ─────────────────────────────────────────────────
    // FIXED: this array existed alongside isMenuOpen/menuRef/the click-outside
    // handler above, but nothing ever rendered a trigger button or the dropdown
    // itself — the six actions below were completely unreachable. Three map
    // directly onto api.ts methods that already existed and were never called
    // from anywhere (generatePQCKeys, predictThreats, scanOmniProbe). The other
    // three don't have a matching backend endpoint yet, so they surface a clear
    // error in the threat feed instead of silently pretending to work.

    const cyberMenuItems = [
        {
            icon: <Shield size={13}/>,
            label: 'GHOST PROTOCOL',
            desc: 'Deploy honeypots & deceptive lattice',
            action: 'ENGAGE GHOST PROTOCOL',
        },
        {
            icon: <Activity size={13}/>,
            label: 'PULSE TRACE',
            desc: 'Kinetic network motion tracking',
            action: 'PULSE_TRACE --subnet ALL',
        },
        {
            icon: <Terminal size={13} className="text-rose-500"/>,
            label: 'THE SPEAR (AEG)',
            desc: 'Autonomous Exploit Generation',
            action: 'SPEAR-AEG --mode AUTO',
        },
        {
            icon: <Cpu size={13} className="text-amber-500"/>,
            label: 'THE FORGE (PQC)',
            desc: 'Generate quantum-resistant keys',
            action: 'FORGE-PQC',
        },
        {
            icon: <Radar size={13} className="text-purple-500"/>,
            label: 'THE ORACLE',
            desc: 'Predictive threat forecasting',
            action: 'ORACLE-PREDICT',
        },
        {
            icon: <Globe size={13} className="text-cyan-500"/>,
            label: 'OMNI-PROBE',
            desc: 'Launch full-spectrum network scan',
            action: 'SCAN --target LOCAL_SUBNET',
        },
    ] as const;

    const runTacticalAction = useCallback(async (item: (typeof cyberMenuItems)[number]) => {
        setIsMenuOpen(false);
        setActionStatus({label: item.label, state: 'pending'});
        addThreat({text: `Dispatch: ${item.action}`, severity: 'INFO', confidence: 100});

        try {
            let resultSummary: string;
            switch (item.label) {
                case 'THE FORGE (PQC)': {
                    const result = await api.generatePQCKeys();
                    resultSummary = result?.key_id || result?.status || 'keys generated';
                    break;
                }
                case 'THE ORACLE': {
                    const result = await api.predictThreats();
                    resultSummary = Array.isArray(result?.predictions)
                        ? `${result.predictions.length} forecasts returned`
                        : 'forecast returned';
                    break;
                }
                case 'OMNI-PROBE': {
                    // TODO: hardcoded target CIDR — wire this to an operator
                    // input or the currently selected subnet instead.
                    const result = await api.scanOmniProbe('0.0.0.0/24');
                    resultSummary = result?.hosts_found != null
                        ? `${result.hosts_found} hosts found`
                        : 'scan queued';
                    break;
                }
                default:
                    // GHOST PROTOCOL / PULSE TRACE / THE SPEAR don't have a
                    // matching backend endpoint in api.ts yet.
                    throw new Error(`No backend endpoint wired for "${item.label}" yet`);
            }
            setActionStatus({label: item.label, state: 'success'});
            addThreat({text: `${item.label} complete: ${resultSummary}`, severity: 'INFO', confidence: 100});
        } catch (err: any) {
            setActionStatus({label: item.label, state: 'error', detail: err?.message});
            addThreat({text: `${item.label} failed: ${err?.message || 'unknown error'}`, severity: 'HIGH', confidence: 100});
        } finally {
            setTimeout(() => setActionStatus(null), 4000);
        }
    }, [addThreat]);

    return (
        <div className="grid grid-cols-12 w-full h-full bg-[#050505] text-slate-300 font-mono overflow-hidden">

            {/* ── LEFT PANEL: Threat Intelligence Feed ── */}
            <motion.div
                custom={0}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-3 h-full flex flex-col border-r border-slate-800/60"
            >
                <div className="grid grid-cols-2 border-b border-slate-800/60 shrink-0">
                    {liveMetrics.map((m, i) => (
                        <div key={i}
                             className={clsx("flex flex-col items-center py-3 border-r border-b border-slate-800/60 last:border-r-0", i >= 2 && "border-b-0")}>
                            <div className="flex items-center gap-1 mb-0.5">{m.icon}</div>
                            <span className={clsx("text-xl font-bold font-mono", m.color)}>{m.value}</span>
                            <span
                                className="text-[8px] text-slate-700 tracking-wider text-center leading-tight">{m.label}</span>
                        </div>
                    ))}
                </div>

                <div
                    className="flex items-center justify-between px-3 py-2 border-b border-slate-800/60 bg-[#0a0a0a] shrink-0">
                    <div className="flex items-center gap-2">
                        <BrainCircuit size={12} className="text-indigo-400 animate-pulse"/>
                        <span
                            className="text-[9px] font-bold text-indigo-400 tracking-widest">AI THREAT INTELLIGENCE</span>
                    </div>
                    <span className="text-[8px] text-slate-600">{threatFeed.length} events</span>
                </div>

                <div ref={feedRef} className="flex-1 overflow-y-auto custom-scrollbar">
                    <AnimatePresence initial={false}>
                        {threatFeed.map((ev) => {
                            const sev = SEV_CFG[ev.severity];
                            return (
                                <motion.div
                                    key={ev.id}
                                    initial={{opacity: 0, x: -8}}
                                    animate={{opacity: 1, x: 0}}
                                    transition={{duration: 0.2}}
                                    className={clsx(
                                        "px-3 py-2 border-b border-slate-900/80 hover:bg-slate-900/30 transition-colors",
                                        ev.severity === 'CRITICAL' && 'bg-rose-950/10'
                                    )}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span
                                            className={clsx("w-1.5 h-1.5 rounded-full shrink-0", sev.dot, ev.severity === 'CRITICAL' && 'animate-pulse')}/>
                                        <span
                                            className={clsx("text-[8px] font-bold px-1 py-0.5 rounded border", sev.badge)}>{ev.severity}</span>
                                        {ev.technique && (
                                            <span
                                                className="text-[8px] bg-slate-900 border border-slate-700 text-slate-500 px-1 rounded font-bold">{ev.technique}</span>
                                        )}
                                        <span className="text-[8px] text-slate-700 ml-auto shrink-0">{ev.ts}</span>
                                    </div>
                                    <p className={clsx("text-[10px] leading-relaxed", sev.text)}>{ev.text}</p>
                                    {ev.src_ip && (
                                        <p className="text-[8px] text-slate-700 mt-0.5">SRC: <span
                                            className="text-slate-500 font-mono">{ev.src_ip}</span></p>
                                    )}
                                    {ev.confidence > 0 && (
                                        <div className="flex items-center gap-1 mt-1.5">
                                            <div className="h-0.5 flex-1 bg-slate-900 rounded-full overflow-hidden">
                                                <div
                                                    className={clsx("h-full rounded-full transition-all", ev.confidence > 90 ? 'bg-rose-500' : ev.confidence > 70 ? 'bg-amber-500' : 'bg-emerald-500')}
                                                    style={{width: `${ev.confidence}%`}}/>
                                            </div>
                                            <span className="text-[8px] text-slate-600">{ev.confidence}%</span>
                                        </div>
                                    )}
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
                    {threatFeed.length === 0 && (
                        <div
                            className="flex flex-col items-center justify-center h-full text-slate-700 opacity-50 gap-2">
                            <BrainCircuit size={24}/>
                            <p className="text-[10px] tracking-widest">Initializing neural engine...</p>
                        </div>
                    )}
                </div>
            </motion.div>

            {/* ── CENTER: Command Center ── */}
            <motion.div
                custom={0.08}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-6 h-full flex flex-col relative"
            >
                <CommandCenter
                    selectedNode={selectedNode}
                    onNodeSelect={(node) => setSelectedNode(node)}
                    onDeepScan={handleDeepScan}
                >
                    <div className="w-full h-full relative overflow-hidden">

                        {/* Uses the scan-line keyframe already defined in tailwind.config.ts
                            but never applied anywhere — a free bit of "maintain animation." */}
                        <div
                            className="pointer-events-none absolute inset-x-0 h-px bg-primary/50 animate-scan-line z-10"/>

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            viewMode === 'LOCAL' ? (
                                <GodsEyeGraph/>
                            ) : (
                                <GlobalOpsMap
                                    globeRef={globeRef}
                                    graphData={{nodes: [], links: []}}
                                    attackArcs={[]}
                                    onNavigateToDevices={() => router.push('/devices')}
                                />
                            )
                        )}

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <div className="absolute bottom-3 left-3 flex items-center gap-2 pointer-events-none z-10">
                                <div className="relative w-3 h-3">
                                    <div className="absolute inset-0 rounded-full bg-cyan-500/30 animate-ping"/>
                                    <div className="w-3 h-3 rounded-full bg-cyan-500"/>
                                </div>
                                <span className="text-[9px] text-cyan-600 tracking-widest">SCANNING</span>
                            </div>
                        )}

                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <motion.button
                                whileHover={{scale: 1.04}}
                                whileTap={{scale: 0.96}}
                                onClick={() => router.push('/devices')}
                                className="absolute top-3 right-3 z-20 bg-red-600/20 hover:bg-red-600/40 border border-red-700/50 text-red-500 px-3 py-1.5 rounded text-[10px] font-bold tracking-widest transition-colors flex items-center gap-1.5">
                                ASSET RECOVERY
                            </motion.button>
                        )}

                        {viewMode === 'SELF_MONITORING' && (
                            <div
                                className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div
                                    className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-cyan-500/30 text-[9px] font-bold tracking-widest text-cyan-400 uppercase font-mono">
                                    ● SYSTEM SELF-MONITORING // LIVE INFRASTRUCTURE
                                </div>
                                {/* FIXED: was <AssetRecoveryPage/>, importing the /devices route's
                                    page.tsx directly. That page wraps its content in TeamShell
                                    (min-h-screen) and used fixed-positioned overlays, so embedding
                                    it here blew out of this panel and covered the whole dashboard
                                    when a device row was clicked. DeviceRegistry is the same UI
                                    extracted into a container-relative component instead. */}
                                <DeviceRegistry/>
                            </div>
                        )}

                        {viewMode === 'PERIMETER_RADAR' && (
                            <div
                                className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div
                                    className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-red-500/30 text-[9px] font-bold tracking-widest text-red-500 uppercase font-mono">
                                    ● PERIMETER THREAT RADAR // BATTLEFIELD TOPOLOGY
                                </div>
                                <GodsEyeGraph/>
                            </div>
                        )}

                        <div className="absolute top-16 left-0 right-0 flex border-b border-slate-800/60 shrink-0 px-4">
                            <button onClick={() => setViewMode('SELF_MONITORING')}
                                    className={clsx("flex-1 py-1.5 text-[9px] font-bold tracking-widest transition-colors flex items-center justify-center gap-1.5",
                                        viewMode === 'SELF_MONITORING' ? 'text-cyan-400 bg-cyan-950/20 border-b-2 border-cyan-500' : 'text-slate-600 hover:text-slate-400')}>
                                LOCAL AEGIS VAULT
                            </button>
                            <button onClick={() => setViewMode('PERIMETER_RADAR')}
                                    className={clsx("flex-1 py-1.5 text-[9px] font-bold tracking-widest transition-colors flex items-center justify-center gap-1.5",
                                        viewMode === 'PERIMETER_RADAR' ? 'text-purple-400 bg-purple-950/20 border-b-2 border-purple-500' : 'text-slate-600 hover:text-slate-400')}>
                                GLOBAL OMNI-MAP
                            </button>
                        </div>

                    </div>
                </CommandCenter>
            </motion.div>

            {/* ── RIGHT PANEL: Action Terminal ── */}
            <motion.div
                custom={0.16}
                initial="hidden"
                animate="visible"
                variants={panelVariants}
                className="col-span-3 h-full flex flex-col border-l border-slate-800/60"
            >
                <ActionTerminal selectedNode={selectedNode} onExecuteAction={handleExecuteAction}/>
            </motion.div>

            {/* --- Action status toast (feedback for the newly-wired backend calls) --- */}
            <AnimatePresence>
                {actionStatus && (
                    <motion.div
                        initial={{opacity: 0, y: 16}}
                        animate={{opacity: 1, y: 0}}
                        exit={{opacity: 0, y: 16}}
                        className={clsx(
                            "fixed bottom-24 left-1/2 -translate-x-1/2 z-[99998] px-4 py-2 rounded-lg border text-[11px] font-bold tracking-wide flex items-center gap-2",
                            actionStatus.state === 'pending' && 'bg-slate-900/95 border-slate-700 text-slate-300',
                            actionStatus.state === 'success' && 'bg-emerald-950/95 border-emerald-700 text-emerald-400',
                            actionStatus.state === 'error' && 'bg-rose-950/95 border-rose-700 text-rose-400',
                        )}
                    >
                        {actionStatus.state === 'pending' && <span className="animate-pulse">●</span>}
                        {actionStatus.state === 'success' && <CheckCircle2 size={14}/>}
                        {actionStatus.state === 'error' && <XCircle size={14}/>}
                        <span>{actionStatus.label}: {actionStatus.state}{actionStatus.detail ? ` — ${actionStatus.detail}` : ''}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* --- FORCED FIXED PORTAL TERMINAL WINDOW OVERLAY --- */}
            <AnimatePresence>
                {terminalOpen && (
                    <motion.div
                        initial={{opacity: 0}}
                        animate={{opacity: 1}}
                        exit={{opacity: 0}}
                        className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
                        style={{zIndex: 999999}}
                    >
                        <motion.div
                            initial={{opacity: 0, scale: 0.96, y: 12}}
                            animate={{opacity: 1, scale: 1, y: 0}}
                            exit={{opacity: 0, scale: 0.96, y: 12}}
                            transition={{duration: 0.18}}
                            className="bg-[#0a0a0c] border border-zinc-800 rounded-xl w-full max-w-xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.95)] p-4 flex flex-col justify-between h-[340px] font-mono text-white"
                        >
                            <div
                                className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-2 flex-shrink-0">
                                <div
                                    className="text-xs text-cyan-400 font-bold tracking-wider uppercase flex items-center gap-2">
                                    <span className="animate-pulse">●</span> Interactive Threat Mitigation Terminal
                                </div>
                                <button
                                    onClick={() => setTerminalOpen(false)}
                                    className="text-zinc-500 hover:text-white border border-zinc-800 hover:border-zinc-700 px-2 py-0.5 rounded text-[10px] transition-colors bg-zinc-900/40"
                                >
                                    Esc to close
                                </button>
                            </div>

                            <div
                                className="flex-1 overflow-y-auto space-y-1 mb-3 text-zinc-300 text-xs p-3 bg-[#020204] rounded border border-zinc-900/80 max-h-[160px] custom-scrollbar">
                                {logs.map((log, i) => (
                                    <pre key={i} className="whitespace-pre-wrap text-left leading-relaxed">{log}</pre>
                                ))}
                                <div ref={scrollRef}/>
                            </div>

                            <form onSubmit={handleTerminalSubmit}
                                  className="flex flex-col gap-2 border-t border-zinc-900 pt-3 flex-shrink-0">
                                <div
                                    className="flex items-center bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5">
                                    <span className="text-cyan-500 font-bold text-xs mr-2 font-mono">#</span>
                                    <input
                                        type="text"
                                        value={terminalInput}
                                        onChange={(e) => setTerminalInput(e.target.value)}
                                        placeholder="Type a mitigation command here (e.g. 'help', 'lockdown')..."
                                        className="w-full bg-transparent text-white text-xs outline-none focus:ring-0 py-0.5"
                                    />
                                </div>

                                <motion.button
                                    whileHover={{scale: terminalInput.trim() ? 1.01 : 1}}
                                    whileTap={{scale: terminalInput.trim() ? 0.98 : 1}}
                                    type="submit"
                                    disabled={!terminalInput.trim()}
                                    className="w-full bg-cyan-600/20 hover:bg-cyan-600/40 border border-cyan-500/40 text-cyan-400 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-colors disabled:opacity-30 disabled:pointer-events-none"
                                >
                                    Execute Command
                                </motion.button>
                            </form>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* --- Tactical command menu trigger + dropdown (previously dead code) --- */}
            <div ref={menuRef} className="fixed bottom-6 right-[168px]" style={{zIndex: 99999}}>
                <AnimatePresence>
                    {isMenuOpen && (
                        <motion.div
                            initial={{opacity: 0, y: 8, scale: 0.98}}
                            animate={{opacity: 1, y: 0, scale: 1}}
                            exit={{opacity: 0, y: 8, scale: 0.98}}
                            transition={{duration: 0.15}}
                            className="absolute bottom-full right-0 mb-2 w-64 bg-[#0a0a0c] border border-zinc-800 rounded-xl overflow-hidden shadow-[0_0_40px_rgba(0,0,0,0.9)]"
                        >
                            {cyberMenuItems.map((item) => (
                                <button
                                    key={item.label}
                                    onClick={() => runTacticalAction(item)}
                                    className="w-full flex items-start gap-2.5 px-3 py-2.5 hover:bg-zinc-900/70 border-b border-zinc-900 last:border-b-0 text-left transition-colors"
                                >
                                    <span className="mt-0.5 text-slate-400">{item.icon}</span>
                                    <span className="flex flex-col">
                                        <span className="text-[10px] font-bold tracking-widest text-slate-200">{item.label}</span>
                                        <span className="text-[9px] text-slate-500">{item.desc}</span>
                                    </span>
                                </button>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                <motion.button
                    whileHover={{scale: 1.05}}
                    whileTap={{scale: 0.95}}
                    onClick={() => setIsMenuOpen((v) => !v)}
                    className="flex items-center gap-2 bg-gradient-to-r from-purple-950 to-zinc-900 hover:from-purple-900 hover:to-zinc-850 border-2 border-purple-400/80 text-purple-300 font-bold px-5 py-3.5 rounded-xl text-xs tracking-widest shadow-[0_0_30px_rgba(168,85,247,0.35)] uppercase"
                >
                    <CommandIcon size={14}/>
                    COMMAND
                    <ChevronDown size={12} className={clsx('transition-transform', isMenuOpen && 'rotate-180')}/>
                </motion.button>
            </div>

            {/* --- FIXED LAYOUT SYSTEM FLOATING TERMINAL TRIGGER --- */}
            <div
                className="fixed bottom-6 right-6"
                style={{zIndex: 99999, pointerEvents: 'auto'}}
            >
                <motion.button
                    whileHover={{scale: 1.05}}
                    whileTap={{scale: 0.95}}
                    onClick={() => setTerminalOpen(true)}
                    className="flex items-center gap-2 bg-gradient-to-r from-cyan-950 to-zinc-900 hover:from-cyan-900 hover:to-zinc-850 border-2 border-cyan-400/80 text-cyan-400 font-bold px-6 py-3.5 rounded-xl text-xs tracking-widest shadow-[0_0_30px_rgba(34,211,238,0.4)] uppercase"
                >
                    Terminal
                </motion.button>
            </div>

        </div>
    );
};
export default SituationRoom;
