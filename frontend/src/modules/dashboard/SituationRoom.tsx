'use client';

import React, {useState, useEffect, useRef, useCallback} from 'react';
import {useRouter} from 'next/navigation';
import {api, buildAuthenticatedWsUrl} from '@/lib/api';
import {socketClient} from '@/lib/socket';
import {
    Shield, Activity, Cpu, Radar, Terminal, ChevronDown, AlertTriangle,
    BrainCircuit, Zap, Eye, Network, Lock, Globe, TrendingUp,
    CheckCircle2, XCircle, Clock, Radio, Target, Crosshair
} from 'lucide-react';
import {GodsEyeGraph} from '@/components/vanguard/GodsEyeGraph';
import {ActionTerminal} from './ActionTerminal';
import {GlobalOpsMap} from './GlobalOpsMap';
import {CommandCenter} from '@/components/CommandCenter';
import {GlassDossier, type EntityData} from '@/components/CommandCenter/GlassDossier';
import {clsx} from 'clsx';
import AssetRecoveryPage from "@/app/devices/page";

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

// ─── Component ────────────────────────────────────────────────────────────────

const SituationRoom: React.FC = () => {
    // --- Clickable Popup Terminal Modal Feature States ---
    const [terminalOpen, setTerminalOpen] = useState(false);
    const [logs, setLogs] = useState<string[]>(["[SYSTEM]: Initializing Interactive Terminal Engine..."]);
    const [terminalInput, setTerminalInput] = useState("");

    const [monitoringMenuOpen, setMonitoringMenuOpen] = useState(false);
    const [activeSubView, setActiveSubView] = useState<'SELF_MONITORING' | 'PERIMETER_RADAR' | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const scrollRef = useRef<HTMLDivElement | null>(null);

    // Connection hooks linking directly to your working backend terminal.py route
    // Open/Close connection hooks linking directly to your backend terminal.py routing pipeline
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

    // Dispatch command function triggered by the single-click Execute button
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

    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [globalVaccines, setGlobalVaccines] = useState<{ ip: string; origin: string }[]>([]);

    // Live threat feed state
    const [threatFeed, setThreatFeed] = useState<ThreatEvent[]>([]);
    const [criticalCount, setCriticalCount] = useState(0);
    const [blockedCount, setBlockedCount] = useState(0);
    const [alertsToday, setAlertsToday] = useState(0);
    const [systemHealth, setSystemHealth] = useState(98);

    // Active threat pulser (creates an always-updating live feel)
    const feedRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const threatIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const globeRef = useRef<any>(null);

    // ─── Add live threat event ──────────────────────────────────────────────

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

    // ─── Initial data load ──────────────────────────────────────────────────

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
        const interval = setInterval(fetchStats, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, [fetchStats]);

    // ─── WebSocket real-time telemetry ──────────────────────────────────────

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

    // ─── Click-outside for dropdown ─────────────────────────────────────────

    useEffect(() => {
        const handle = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) setIsMenuOpen(false);
        };
        document.addEventListener('mousedown', handle);
        return () => document.removeEventListener('mousedown', handle);
    }, []);

    // ─── Auto-scroll threat feed ────────────────────────────────────────────

    // (Feed is newest-first so no need to scroll)

    const handleExecuteAction = (command: string) => {
        addThreat({text: `Operator override: ${command}`, severity: 'INFO', confidence: 100});
    };

    const roe = ROE_CFG[roeLevel];

    // ─── Metrics panel data ─────────────────────────────────────────────────

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

    const cyberMenuItems = [
        {
            icon: <Shield size={13}/>,
            label: 'GHOST PROTOCOL',
            desc: 'Deploy honeypots & deceptive lattice',
            action: 'ENGAGE GHOST PROTOCOL'
        },
        {
            icon: <Activity size={13}/>,
            label: 'PULSE TRACE',
            desc: 'Kinetic network motion tracking',
            action: 'PULSE_TRACE --subnet ALL'
        },
        {
            icon: <Terminal size={13} className="text-rose-500"/>,
            label: 'THE SPEAR (AEG)',
            desc: 'Autonomous Exploit Generation',
            action: 'SPEAR-AEG --mode AUTO'
        },
        {
            icon: <Cpu size={13} className="text-amber-500"/>,
            label: 'THE FORGE (PQC)',
            desc: 'Generate quantum-resistant keys',
            action: 'FORGE-PQC'
        },
        {
            icon: <Radar size={13} className="text-purple-500"/>,
            label: 'THE ORACLE',
            desc: 'Predictive threat forecasting',
            action: 'ORACLE-PREDICT'
        },
        {
            icon: <Globe size={13} className="text-cyan-500"/>,
            label: 'OMNI-PROBE',
            desc: 'Launch full-spectrum network scan',
            action: 'SCAN --target LOCAL_SUBNET'
        },
    ];

    return (
        <div className="grid grid-cols-12 w-full h-full bg-[#050505] text-slate-300 font-mono overflow-hidden">

            {/* ── LEFT PANEL: Threat Intelligence Feed ── */}
            <div className="col-span-3 h-full flex flex-col border-r border-slate-800/60">

                {/* Live metrics */}
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

                {/* Threat Feed Header */}
                <div
                    className="flex items-center justify-between px-3 py-2 border-b border-slate-800/60 bg-[#0a0a0a] shrink-0">
                    <div className="flex items-center gap-2">
                        <BrainCircuit size={12} className="text-indigo-400 animate-pulse"/>
                        <span
                            className="text-[9px] font-bold text-indigo-400 tracking-widest">AI THREAT INTELLIGENCE</span>
                    </div>
                    <span className="text-[8px] text-slate-600">{threatFeed.length} events</span>
                </div>

                {/* Scrollable Threat Events */}
                <div ref={feedRef} className="flex-1 overflow-y-auto custom-scrollbar">
                    {threatFeed.map((ev) => {
                        const sev = SEV_CFG[ev.severity];
                        return (
                            <div key={ev.id}
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
                            </div>
                        );
                    })}
                    {threatFeed.length === 0 && (
                        <div
                            className="flex flex-col items-center justify-center h-full text-slate-700 opacity-50 gap-2">
                            <BrainCircuit size={24}/>
                            <p className="text-[10px] tracking-widest">Initializing neural engine...</p>
                        </div>
                    )}
                </div>
            </div>

            {/* ── CENTER: Command Center ── */}
            <div className="col-span-6 h-full flex flex-col relative">
                <CommandCenter
                    selectedNode={selectedNode}
                    onNodeSelect={(node) => setSelectedNode(node)}
                    onDeepScan={(nodeId) => {
                        console.log(`Deep scan initiated on node ${nodeId}`);
                    }}
                >
                    <div className="w-full h-full">

                        {/* ── SAFETY BLANKET HIDES OLD GRAPH WHEN NEW TRACKING LAYER IS ACTIVE ── */}
                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            viewMode === 'LOCAL' ? (
                                <GodsEyeGraph />
                            ) : (
                                <GlobalOpsMap
                                    globeRef={globeRef}
                                    graphData={{ nodes: [], links: [] }}
                                    attackArcs={[]}
                                    onNavigateToDevices={() => router.push('/devices')}
                                />
                            )
                        )}

                        {/* Pulse scan overlay (Hides cleanly when browsing system monitoring) */}
                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <div className="absolute bottom-3 left-3 flex items-center gap-2 pointer-events-none z-10">
                                <div className="relative w-3 h-3">
                                    <div className="absolute inset-0 rounded-full bg-cyan-500/30 animate-ping" />
                                    <div className="w-3 h-3 rounded-full bg-cyan-500" />
                                </div>
                                <span className="text-[9px] text-cyan-600 tracking-widest">SCANNING</span>
                            </div>
                        )}

                        {/* ASSET RECOVERY BUTTON (Hides safely when system monitoring is active) */}
                        {viewMode !== 'SELF_MONITORING' && viewMode !== 'PERIMETER_RADAR' && (
                            <button onClick={() => router.push('/devices')}
                                    className="absolute top-3 right-3 z-20 bg-red-600/20 hover:bg-red-600/40 border border-red-700/50 text-red-500 px-3 py-1.5 rounded text-[10px] font-bold tracking-widest transition-all flex items-center gap-1.5">
                                ASSET RECOVERY
                            </button>
                        )}

                        {/* ── PANEL A: DYNAMIC SYSTEM SELF-MONITORING INFRASTRUCTURE MAP ── */}
                        {viewMode === 'SELF_MONITORING' && (
                            <div className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-cyan-500/30 text-[9px] font-bold tracking-widest text-cyan-400 uppercase font-mono">
                                    ● SYSTEM SELF-MONITORING // LIVE INFRASTRUCTURE
                                </div>
                                <AssetRecoveryPage />
                            </div>
                        )}

                        {/* ── PANEL B: DYNAMIC PERIMETER THREAT RADAR GRAPH LAYER ── */}
                        {viewMode === 'PERIMETER_RADAR' && (
                            <div className="absolute inset-0 top-24 w-full h-[calc(100%-96px)] overflow-hidden p-2 rounded-xl border border-zinc-900 bg-zinc-950/40 z-30">
                                <div className="absolute top-4 left-4 z-40 bg-black/80 backdrop-blur px-2 py-0.5 rounded border border-red-500/30 text-[9px] font-bold tracking-widest text-red-500 uppercase font-mono">
                                    ● PERIMETER THREAT RADAR // BATTLEFIELD TOPOLOGY
                                </div>
                                <GodsEyeGraph />
                            </div>
                        )}

                        {/* View mode toggle - integrated into CommandCenter */}
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


            </div>



            {/* ── RIGHT PANEL: Action Terminal ── */}
            <div className="col-span-3 h-full flex flex-col border-l border-slate-800/60">
                <ActionTerminal selectedNode={selectedNode} onExecuteAction={handleExecuteAction}/>
            </div>
            {/* --- FORCED FIXED PORTAL TERMINAL WINDOW OVERLAY --- */}
            {terminalOpen && (
                <div
                    className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
                    style={{zIndex: 999999}}
                >
                    <div
                        className="bg-[#0a0a0c] border border-zinc-800 rounded-xl w-full max-w-xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.95)] p-4 flex flex-col justify-between h-[340px] font-mono text-white">

                        {/* Modal Mini Toolbar Title */}
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

                        {/* Output log collector console box */}
                        <div
                            className="flex-1 overflow-y-auto space-y-1 mb-3 text-zinc-300 text-xs p-3 bg-[#020204] rounded border border-zinc-900/80 max-h-[160px] custom-scrollbar">
                            {logs.map((log, i) => (
                                <pre key={i} className="whitespace-pre-wrap text-left leading-relaxed">{log}</pre>
                            ))}
                            <div ref={scrollRef}/>
                        </div>

                        {/* Input entry textbox panel area with direct action execute button */}
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

                            {/* CLICKABLE SINGLE-CLICK EXECUTION CONTROL BUTTON */}
                            <button
                                type="submit"
                                disabled={!terminalInput.trim()}
                                className="w-full bg-cyan-600/20 hover:bg-cyan-600/40 border border-cyan-500/40 text-cyan-400 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-30 disabled:pointer-events-none"
                            >
                                Execute Command
                            </button>
                        </form>

                    </div>
                </div>
            )}

            {/* --- FIXED LAYOUT SYSTEM FLOATING TERMINAL TRIGGER --- */}
            <div
                className="fixed bottom-6 right-6"
                style={{zIndex: 99999, pointerEvents: 'auto'}}
            >
                <button
                    onClick={() => setTerminalOpen(true)}
                    className="flex items-center gap-2 bg-gradient-to-r from-cyan-950 to-zinc-900 hover:from-cyan-900 hover:to-zinc-850 border-2 border-cyan-400/80 text-cyan-400 font-bold px-6 py-3.5 rounded-xl text-xs tracking-widest shadow-[0_0_30px_rgba(34,211,238,0.4)] hover:scale-105 active:scale-95 uppercase"
                >
                    Terminal
                </button>
            </div>

        </div>
    );
};
export default SituationRoom;
