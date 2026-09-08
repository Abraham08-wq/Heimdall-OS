import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Terminal, ShieldAlert, Cpu, Radar, Wifi, Lock, Zap, Eye,
    Network, Database, Shield, AlertTriangle, CheckCircle2,
    Play, Square, Radio, X, ChevronRight, HelpCircle, Crosshair, Globe, Search
} from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';

// ─── Types ───────────────────────────────────────────────────────────────────

interface LogEntry {
    id: string;
    text: string;
    type: 'input' | 'output' | 'system' | 'error' | 'success' | 'separator';
    timestamp: string;
}

interface DiscoveredHost {
    ip: string;
    hostname?: string;
    os?: string;
    openPorts: { port: number; service: string; version?: string }[];
    riskLevel: 'critical' | 'high' | 'medium' | 'low';
    cves?: string[];
}

interface ActionTerminalProps {
    selectedNode: any | null;
    onExecuteAction: (action: string) => void;
}

const RISK_CFG = {
    critical: { color: 'text-rose-400', bg: 'bg-rose-950/30', border: 'border-rose-700', dot: 'bg-rose-500' },
    high: { color: 'text-orange-400', bg: 'bg-orange-950/20', border: 'border-orange-700', dot: 'bg-orange-500' },
    medium: { color: 'text-amber-400', bg: 'bg-amber-950/10', border: 'border-amber-700', dot: 'bg-amber-500' },
    low: { color: 'text-slate-400', bg: '', border: 'border-slate-700', dot: 'bg-slate-500' },
};

// ─── Help reference ───────────────────────────────────────────────────────────

const HELP_TEXT = [
    '╔══════════════════════════════════════════════════════╗',
    '║           NEXUS COMMAND REFERENCE v5.0              ║',
    '╚══════════════════════════════════════════════════════╝',
    '',
    '  RECONNAISSANCE & SCANNING',
    '  ─────────────────────────',
    '  SCAN --target <IP/CIDR>       Full network topology scan',
    '  SCAN --target <IP> --deep     CVE + service enumeration',
    '  SCAN --target <IP> --stealth  Low-and-slow, port 80/443 only',
    '  PORTS --host <IP>             Enumerate all open ports',
    '  CLUSTER --ip <IP>             Find coordinated attack cluster',
    '  GEOTRACK --ip <IP>            Geolocate + ASN attribution',
    '',
    '  OFFENSIVE OPERATIONS',
    '  ────────────────────',
    '  SPEAR-AEG <target>            Auto exploit generation (AEG)',
    '  EXPLOIT --cve <CVE-ID>        Weaponize specific vulnerability',
    '  INJECT --target <IP>          Memory-only payload injection',
    '  YARA-HUNT --target <IP>       Deploy YARA rule + live hunt',
    '',
    '  DEFENSIVE ACTIONS',
    '  ─────────────────',
    '  ISOLATE --node <ID>           Network-isolate target host',
    '  VACCINATE --target <IP>       Deploy live threat vaccine',
    '  YARA --generate <IOC>         Auto-generate + deploy YARA rule',
    '  HONEY-TRAP --ip <IP>          Redirect attacker to honeynet',
    '',
    '  INTELLIGENCE & ATTRIBUTION',
    '  ──────────────────────────',
    '  ENABLE_GHOST_PROTOCOL         Activate deception lattice',
    '  FORGE-PQC                     Generate post-quantum keys',
    '  ORACLE-PREDICT                Geopolitical threat forecast',
    '  INTEL --actor <APT>           Full actor profile (e.g., APT29)',
    '  UEBA --entity <IP>            Behavioral baseline deviation report',
    '  CAMPAIGN --c2 <DOMAIN>        Map full attack campaign from C2 domain',
    '  DARKWEB --query <TERM>        Query dark web + paste feeds',
    '',
    '  MISSIONS',
    '  ────────',
    '  MISSION --launch <TARGET>     Launch async intelligence mission',
    '  MISSION --status              List all active missions',
    '  MISSION --abort <ID>          Abort and rollback a mission',
    '  TIMELINE --incident <ID>      Reconstruct kill-chain timeline',
    '',
    '  Type "help" to show this menu  |  ↑↓ for command history',
];

// ─── Component ────────────────────────────────────────────────────────────────

export const ActionTerminal: React.FC<ActionTerminalProps> = ({ selectedNode, onExecuteAction }) => {
    const [command, setCommand] = useState('');
    const [isDeceptionActive, setIsDeceptionActive] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [scanProgress, setScanProgress] = useState(0);
    const [discoveredHosts, setDiscoveredHosts] = useState<DiscoveredHost[]>([]);
    const [selectedHost, setSelectedHost] = useState<DiscoveredHost | null>(null);
    const [viewMode, setViewMode] = useState<'terminal' | 'topology'>('terminal');
    const [cmdHistory, setCmdHistory] = useState<string[]>([]);
    const [historyIdx, setHistoryIdx] = useState(-1);
    const [activeMissions, setActiveMissions] = useState<{ id: string; target: string; status: string }[]>([]);
    const [logs, setLogs] = useState<LogEntry[]>([
        { id: 'boot0', text: '╔═══════════════ NEXUS COMMAND CONSOLE ═══════════════╗', type: 'system', timestamp: '' },
        { id: 'boot1', text: '  OMNI-PROBE v5 | GOD MODE | FULL SPECTRUM CAPABILITY  ', type: 'system', timestamp: '' },
        { id: 'boot2', text: '╚═════════════════════════════════════════════════════╝', type: 'system', timestamp: '' },
        { id: 'boot3', text: '', type: 'output', timestamp: '' },
        { id: 'boot4', text: 'Nexus Terminal v5.0 — Type "help" for command reference', type: 'system', timestamp: '' },
        { id: 'boot5', text: 'Use ↑/↓ arrow keys to navigate command history.', type: 'output', timestamp: '' },
    ]);
    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const scanRef = useRef<any>(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [logs]);

    const addLog = useCallback((text: string, type: LogEntry['type'] = 'output') => {
        setLogs(prev => [...prev, {
            id: `${Date.now()}-${Math.random()}`, text, type,
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false })
        }]);
    }, []);

    const simulateOutput = useCallback((lines: string[], type: LogEntry['type'] = 'output', delayMs = 120) => {
        lines.forEach((line, i) => {
            setTimeout(() => addLog(line, type), i * delayMs);
        });
    }, [addLog]);

    // Omni-Probe scan engine
    const runScan = useCallback(async (target: string, mode: 'full' | 'deep' | 'stealth' = 'full') => {
        setIsScanning(true);
        setScanProgress(0);
        setDiscoveredHosts([]);
        setViewMode('topology');

        addLog(`[OMNI-PROBE] Initializing scan engine — Target: ${target}`, 'system');
        addLog(`[*] Scan mode: ${mode.toUpperCase()} SPECTRUM`, 'system');
        
        let p = 0;
        scanRef.current = setInterval(() => {
            p += Math.random() * 10 + 5;
            if (p >= 100) {
                p = 100;
                clearInterval(scanRef.current);
            }
            setScanProgress(p);
        }, 400);

        try {
            const res = await api.scanOmniProbe(target);
            clearInterval(scanRef.current);
            setScanProgress(100);

            const finalHosts: DiscoveredHost[] = (res?.telemetry || []).map((h: any) => ({
                ip: h.ip,
                openPorts: (Object.entries(h.services || {}) as [string, string][]).map(([port, service]) => ({ port: parseInt(port), service })),
                riskLevel: 'medium' as const, // Default risk, real would come from analysis
                hostname: h.hostname || 'Unknown',
                os: 'Unknown',
                cves: []
            }));
            setDiscoveredHosts(finalHosts);

            addLog(`[OMNI-PROBE] Scan complete — ${finalHosts.length} hosts discovered`, 'success');
            finalHosts.forEach(h => addLog(`  [+] ${h.ip} | Ports: ${h.openPorts.map(p => p.port).join(', ')}`, 'output'));

        } catch (e) {
            addLog(`[OMNI-PROBE] Scan failed: ${(e as Error).message}`, 'error');
            clearInterval(scanRef.current);
        } finally {
            setIsScanning(false);
        }
    }, [addLog]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            const nextIdx = Math.min(historyIdx + 1, cmdHistory.length - 1);
            setHistoryIdx(nextIdx);
            setCommand(cmdHistory[nextIdx] ?? '');
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            const nextIdx = Math.max(historyIdx - 1, -1);
            setHistoryIdx(nextIdx);
            setCommand(nextIdx === -1 ? '' : cmdHistory[nextIdx] ?? '');
        }
    };

    const handleCommandSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const cmd = command.trim();
        if (!cmd) return;

        setCmdHistory(prev => [cmd, ...prev].slice(0, 50));
        setHistoryIdx(-1);
        addLog(`root@nexus:~# ${cmd}`, 'input');
        addLog('', 'output');
        onExecuteAction(cmd);
        setCommand('');

        const lower = cmd.toLowerCase();
        const [action, ...args] = lower.split(' ');
        const targetArg = cmd.match(/--target\s+(\S+)/)?.[1] || cmd.match(/--actor\s+(\S+)/)?.[1] || cmd.match(/--node\s+(\S+)/)?.[1] || cmd.match(/--ip\s+(\S+)/)?.[1] || selectedNode?.id || '192.168.1.0/24';

        try {
            switch (action) {
                case 'help':
                    simulateOutput(HELP_TEXT, 'system', 20);
                    break;
                case 'scan':
                    const mode = lower.includes('--deep') ? 'deep' : lower.includes('--stealth') ? 'stealth' : 'full';
                    await runScan(targetArg, mode);
                    break;
                case 'intel':
                    const actorName = (cmd.match(/--actor\s+(.+)/)?.[1] || 'APT-41').toUpperCase().replace(/ /g, '-');
                    addLog(`[INTEL] Fetching profile for ${actorName}...`, 'system');
                    const profile = await api.getThreatActorProfile(actorName);
                    simulateOutput([
                        '╔════════════ THREAT ACTOR PROFILE ════════════╗',
                        `  Designation: ${profile.threat_actor || actorName}`,
                        `  Known IPs: ${profile.infrastructure?.known_ips?.join(', ') || 'N/A'}`,
                        `  Known Domains: ${profile.infrastructure?.known_domains?.join(', ') || 'N/A'}`,
                        `  Malware Samples: ${profile.infrastructure?.malware_samples?.join(', ') || 'N/A'}`,
                        '╚══════════════════════════════════════════════╝',
                    ], 'system', 60);
                    break;
                case 'isolate':
                    addLog(`[NEXUS-SOAR] Isolation protocol → ${targetArg}`, 'system');
                    const res = await api.quarantineNode(targetArg);
                    addLog(`[+] Host ${res.target} completely isolated`, 'success');
                    break;
                case 'vaccinate':
                    addLog(`[VACCINE] Deploying live threat countermeasure → ${targetArg}`, 'system');
                    const vaccineRes = await api.distributeVaccine(targetArg); // Assume target is vaccine_id for now
                    addLog(`[+] Vaccine distributed to ${vaccineRes.nodes_notified} nodes.`, 'success');
                    break;
                case 'honey-trap':
                    addLog(`[GHOST] Routing ${targetArg} into deception lattice...`, 'system');
                    const blackholeRes = await api.blackholeIp(targetArg);
                    addLog(`[+] Attacker ${blackholeRes.target} now routed to honeynet. Session: ${blackholeRes.session_id}`, 'success');
                    break;
                case 'spear-aeg':
                case 'exploit':
                    const cve = cmd.match(/--cve\s+(\S+)/)?.[1] || 'AUTO-DETECT';
                    addLog(`[SPEAR-AEG] Synthesizing exploit for ${targetArg} (CVE: ${cve})`, 'error');
                    const exploitRes = await api.synthesizeExploit({ ip: targetArg, target_cve: cve });
                    addLog(`[+] Payload generated: ${exploitRes.weaponized_package.payload_command}`, 'output');
                    break;
                case 'darkweb':
                    const query = cmd.match(/--query\s+(.+)/)?.[1] || 'corp.local credentials';
                    addLog(`[DARKWEB] Querying TOR paste feeds + markets: "${query}"`, 'system');
                    const results = await api.searchOSINT(query);
                    addLog(`[+] Found ${results.length} results.`, 'success');
                    results.slice(0, 5).forEach(r => addLog(`  - ${r.title}`, 'output'));
                    break;
                case 'mission':
                    const missionAction = args[0];
                    const missionArg = args[1];
                    if (missionAction === '--launch') {
                        addLog(`[MISSION] Launching intelligence mission → ${missionArg}`, 'system');
                        const mission = await api.launchMission(missionArg);
                        setActiveMissions(prev => [...prev, { id: mission.mission_id, target: missionArg, status: 'RUNNING' }]);
                        addLog(`[+] Mission ${mission.mission_id} running. Use 'mission --status'`, 'success');
                    } else if (missionAction === '--status') {
                        const missions = await api.listMissions();
                        addLog('  ID              TARGET          STATUS', 'system');
                        addLog('  ─────────────── ─────────────── ──────', 'system');
                        missions.forEach((m: any) => addLog(`  ${m.mission_id.padEnd(15)} ${m.target_entity.slice(0, 15).padEnd(15)} ${m.phase}`, 'output'));
                    } else if (missionAction === '--abort') {
                        addLog(`[MISSION] Aborting ${missionArg}...`, 'system');
                        await api.abortMission(missionArg);
                        addLog(`[+] Mission ${missionArg} aborted.`, 'success');
                        setActiveMissions(prev => prev.map(m => m.id === missionArg ? { ...m, status: 'ABORTED' } : m));
                    }
                    break;
                case 'clear':
                    setLogs([]);
                    break;
                default:
                    addLog(`Command not recognized: "${action}". Type 'help'.`, 'error');
            }
        } catch (err: any) {
            addLog(`[NEXUS] API Fatal error: ${err.message}`, 'error');
        }
    };

    const logColor = (type: LogEntry['type']) => {
        switch (type) {
            case 'input': return 'text-emerald-400 font-bold';
            case 'system': return 'text-cyan-400';
            case 'error': return 'text-rose-400';
            case 'success': return 'text-emerald-400';
            case 'separator': return 'text-slate-700 border-t border-slate-800 mt-1 pt-1';
            default: return 'text-slate-300';
        }
    };

    return (
        <div className="flex flex-col h-full bg-[#040507] border-l border-slate-900 font-mono relative overflow-hidden">
            <div className="absolute inset-0 pointer-events-none z-50 opacity-[0.04] bg-[linear-gradient(rgba(0,0,0,0)_50%,rgba(0,0,0,0.4)_50%)] bg-[length:100%_3px]" />

            <div className="px-3 py-2.5 border-b border-emerald-900/30 bg-black/70 flex items-center justify-between z-10 shrink-0">
                <div className="flex items-center gap-2">
                    <Terminal size={13} className="text-emerald-400 animate-pulse" />
                    <span className="text-[10px] font-bold text-emerald-400 tracking-widest">NEXUS COMMAND CONSOLE</span>
                    {isDeceptionActive && (
                        <span className="text-[8px] bg-purple-950/60 border border-purple-600 text-purple-400 px-1.5 py-0.5 rounded font-bold animate-pulse">GHOST ACTIVE</span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex rounded overflow-hidden border border-slate-800">
                        <button onClick={() => setViewMode('terminal')}
                            className={clsx("text-[8px] px-2 py-1 font-bold transition-colors", viewMode === 'terminal' ? "bg-emerald-950 text-emerald-400" : "text-slate-600 hover:text-slate-400")}>
                            TERM
                        </button>
                        <button onClick={() => setViewMode('topology')}
                            className={clsx("text-[8px] px-2 py-1 font-bold transition-colors border-l border-slate-800", viewMode === 'topology' ? "bg-cyan-950 text-cyan-400" : "text-slate-600 hover:text-slate-400")}>
                            TOPO
                        </button>
                    </div>
                    <span className="text-[8px] text-slate-700">[ROOT@NEXUS]</span>
                </div>
            </div>

            {isScanning && (
                <div className="shrink-0 px-3 py-1.5 bg-black/60 border-b border-cyan-900/30">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] text-cyan-400 flex items-center gap-1.5"><Radar size={10} className="animate-spin" /> OMNI-PROBE SCANNING</span>
                        <span className="text-[9px] text-cyan-500 font-mono">{Math.round(scanProgress)}%</span>
                    </div>
                    <div className="h-0.5 bg-slate-900 rounded overflow-hidden">
                        <div className="h-full bg-cyan-500 transition-all duration-300 shadow-[0_0_8px_rgba(6,182,212,0.6)]" style={{ width: `${scanProgress}%` }} />
                    </div>
                </div>
            )}

            <div className="flex-1 min-h-0 overflow-hidden">

                {viewMode === 'terminal' ? (
                    <div ref={scrollRef} className="h-full overflow-y-auto custom-scrollbar px-3 py-2 space-y-0.5 text-[10px]">
                        {logs.map(log => (
                            <div key={log.id} className={clsx("flex gap-2 items-start break-words whitespace-pre-wrap leading-relaxed", logColor(log.type))}>
                                {log.timestamp && <span className="text-[8px] text-slate-800 shrink-0 mt-0.5 select-none">[{log.timestamp}]</span>}
                                <span className="flex-1 min-w-0">{log.text}</span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="h-full overflow-y-auto custom-scrollbar p-2">
                        {discoveredHosts.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full text-slate-700 gap-2">
                                <Radar size={24} />
                                <p className="text-[10px] tracking-widest text-center">Run SCAN to discover hosts</p>
                            </div>
                        ) : (
                            <div className="space-y-1.5">
                                <div className="grid grid-cols-4 gap-1 mb-2">
                                    {[
                                        { label: 'HOSTS', value: discoveredHosts.length, color: 'text-cyan-400' },
                                        { label: 'CRITICAL', value: discoveredHosts.filter(h => h.riskLevel === 'critical').length, color: 'text-rose-400' },
                                        { label: 'HIGH', value: discoveredHosts.filter(h => h.riskLevel === 'high').length, color: 'text-orange-400' },
                                        { label: 'CVEs', value: discoveredHosts.flatMap(h => h.cves || []).length, color: 'text-amber-400' },
                                    ].map((s, i) => (
                                        <div key={i} className="bg-black/60 border border-slate-800 rounded p-1.5 text-center">
                                            <div className={clsx("text-sm font-bold", s.color)}>{s.value}</div>
                                            <div className="text-[7px] text-slate-700">{s.label}</div>
                                        </div>
                                    ))}
                                </div>

                                {discoveredHosts.map(host => {
                                    const cfg = RISK_CFG[host.riskLevel];
                                    const isSelected = selectedHost?.ip === host.ip;
                                    return (
                                        <div key={host.ip} onClick={() => setSelectedHost(isSelected ? null : host)}
                                            className={clsx("rounded border p-2 cursor-pointer transition-all", cfg.border, isSelected ? cfg.bg : "bg-black/40 hover:bg-black/60")}>
                                            <div className="flex items-center gap-1.5 mb-1">
                                                <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", cfg.dot)} />
                                                <span className="text-[10px] font-bold font-mono text-white">{host.ip}</span>
                                                <span className={clsx("ml-auto text-[8px] font-bold px-1 rounded", cfg.color)}>{host.riskLevel.toUpperCase()}</span>
                                            </div>
                                            {host.openPorts.length > 0 && <div className="flex flex-wrap gap-1 mt-1">
                                                {host.openPorts.slice(0, 4).map(p => (
                                                    <span key={p.port} className="text-[7px] border border-slate-700 text-slate-500 px-1 rounded">{p.port}/{p.service}</span>
                                                ))}
                                            </div>}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="border-t border-emerald-900/20 bg-black/80 px-3 py-2 z-10 shrink-0">
                <form onSubmit={handleCommandSubmit} className="flex items-center gap-2">
                    <span className="text-emerald-500 text-[11px] font-bold shrink-0">root@nexus:~#</span>
                    <input
                        ref={inputRef}
                        type="text"
                        value={command}
                        onChange={e => setCommand(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="flex-1 bg-transparent outline-none text-emerald-400 text-[11px] placeholder-slate-800 caret-emerald-500"
                        placeholder='type "help" or ↑↓ history...'
                        autoComplete="off"
                        spellCheck={false}
                    />
                </form>
            </div>
        </div>
    );
};
