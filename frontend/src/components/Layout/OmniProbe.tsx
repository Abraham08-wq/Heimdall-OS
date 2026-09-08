"use client";

import React, { useState, useEffect, useRef } from 'react';
import { useUIStore } from '@/store/uiStore';
import { Terminal, X, ShieldAlert, Globe, Search, Ban, Cpu, Network, Database, Fingerprint, Radar, Activity, Zap, Server, Hexagon, Crosshair, Unlock } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';

type ScanPhase = 'IDLE' | 'RECON' | 'ANALYZE' | 'EXECUTE' | 'PERSIST' | 'COMPLETED' | 'FAILED' | 'NEUTRALIZED';

const phaseToProgress = {
    IDLE: 0,
    RECON: 25,
    ANALYZE: 50,
    EXECUTE: 75,
    PERSIST: 90,
    COMPLETED: 100,
    FAILED: 100,
    NEUTRALIZED: 100,
};


export default function OmniProbe() {
    const { isInterceptOpen, toggleIntercept } = useUIStore();
    const [query, setQuery] = useState('');
    const [phase, setPhase] = useState<ScanPhase>('IDLE');
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState<string[]>([]);
    const [intel, setIntel] = useState<any>(null);
    const logEndRef = useRef<HTMLDivElement>(null);
    const pollingRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    useEffect(() => {
        if (!isInterceptOpen) {
            if (pollingRef.current) clearInterval(pollingRef.current);
            setPhase('IDLE');
            setQuery('');
            setIntel(null);
            setLogs([]);
            setProgress(0);
        }
        // Cleanup on unmount
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        }
    }, [isInterceptOpen]);

    if (!isInterceptOpen) return null;

    const addLog = (msg: string) => {
        setLogs(prev => [...prev, `[${new Date().toISOString().split('T')[1].slice(0, 11)}] ${msg}`]);
    };

    const handleScan = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim() || phase !== 'IDLE') return;

        setLogs([]);
        addLog(`INITIALIZING OMNI-PROBE PROTOCOL FOR TARGET: ${query}`);

        try {
            const mission = await api.launchMission(query);
            addLog(`Mission ${mission.mission_id} launched. Polling for status...`);

            pollingRef.current = setInterval(async () => {
                try {
                    const missionStatus = await api.getMission(mission.mission_id);
                    setPhase(missionStatus.phase as ScanPhase);
                    setProgress(phaseToProgress[missionStatus.phase as ScanPhase]);
                    
                    if (missionStatus.phase === 'COMPLETED' || missionStatus.phase === 'FAILED') {
                        if (pollingRef.current) clearInterval(pollingRef.current);
                        addLog(`Mission ${missionStatus.phase}. Finalizing intelligence package.`);
                        setIntel({
                            ip: missionStatus.target_entity,
                            location: missionStatus.recon_data?.intelligence_feed?.location_data?.country || 'Unknown',
                            risk_score: missionStatus.analysis_findings?.threat_score || 0,
                            cves: missionStatus.recon_data?.potential_cves || [],
                            history: `MISSION ID: ${mission.mission_id.substring(0, 8)}`,
                            ports: Object.keys(missionStatus.recon_data?.services || {}),
                            aliases: missionStatus.analysis_findings?.demasking?.aliases || [],
                            org: 'Unknown'
                        });
                    }
                } catch (pollErr) {
                    addLog(`Error polling mission status: ${(pollErr as Error).message}`);
                    if (pollingRef.current) clearInterval(pollingRef.current);
                }
            }, 3000);

        } catch (error) {
            addLog(`Failed to launch mission: ${(error as Error).message}`);
        }
    };
    
    const handleNeutralize = () => {
        addLog('EXECUTING AEG (AUTONOMOUS EXPLOIT GENERATION)... (SIMULATED)');
        addLog('INJECTING KILLCHAIN PAYLOAD. (SIMULATED)');
        addLog('TARGET COMMUNICATION SEVERED. ISOLATION CONFIRMED.');
        setPhase('NEUTRALIZED');
    };

    const isScanning = phase !== 'IDLE' && phase !== 'COMPLETED' && phase !== 'NEUTRALIZED';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-4 lg:p-8 font-mono">
            <div className="crt-overlay"></div>

            {/* Ambient Background Effects */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <div className="absolute inset-0 opacity-[0.03] data-stream-bg animate-matrix"></div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120vw] h-[120vh] bg-[radial-gradient(circle_at_center,rgba(0,255,255,0.03)_0%,transparent_60%)]"></div>
                {isScanning && (
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full border border-cyan-500/10 bg-[conic-gradient(from_0deg,transparent_0deg,transparent_270deg,rgba(0,255,255,0.15)_360deg)] animate-[spin_1.5s_linear_infinite]"></div>
                )}
            </div>

            <div className="w-full max-w-6xl h-full max-h-[90vh] bg-[#030303]/95 border border-cyan-900/40 shadow-[0_0_80px_rgba(0,255,255,0.05)] rounded-xl overflow-hidden flex flex-col relative z-10 hud-container">

                {/* ── HEADER ── */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-900/30 bg-[#060606] shrink-0">
                    <div className="flex items-center gap-4">
                        <div className="relative flex items-center justify-center w-8 h-8">
                            <Radar size={24} className={clsx("text-cyan-500", isScanning && "animate-spin")} />
                            <div className="absolute inset-0 rounded-full border border-cyan-500/30 animate-ping"></div>
                        </div>
                        <div>
                            <h1 className="font-black tracking-[0.2em] text-cyan-400 text-lg shadow-cyan-500/50 drop-shadow-[0_0_10px_rgba(34,211,238,0.4)] text-glitch" data-text="OMNI-PROBE // DEEP DISCOVERY">
                                OMNI-PROBE {"//"} DEEP DISCOVERY
                            </h1>
                            <p className="text-[10px] text-cyan-700 tracking-widest uppercase mt-0.5 animate-pulse">Sovereign Intelligence Weaponry · Neural Integration Online</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-6">
                        {/* Status Indicator */}
                        <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-black border border-slate-800 rounded">
                            <span className={clsx("w-2 h-2 rounded-full shadow-[0_0_8px_currentColor]",
                                phase === 'IDLE' ? 'bg-slate-500 text-slate-500' :
                                    phase === 'COMPLETED' ? 'bg-red-500 text-red-500 animate-pulse' :
                                        phase === 'NEUTRALIZED' ? 'bg-emerald-500 text-emerald-500' :
                                            'bg-cyan-500 text-cyan-500 animate-pulse'
                            )}></span>
                            <span className="text-[10px] font-bold tracking-widest text-slate-400">
                                {phase === 'IDLE' ? 'STANDBY' : phase === 'COMPLETED' ? 'TARGET LOCKED' : phase === 'NEUTRALIZED' ? 'CONTAINED' : 'SCANNING ACTIVE'}
                            </span>
                        </div>

                        <button onClick={() => toggleIntercept(false)} className="text-slate-500 hover:text-cyan-400 transition-colors p-2 hover:bg-cyan-950/30 rounded">
                            <X size={24} />
                        </button>
                    </div>
                </div>

                {/* ── BODY ── */}
                <div className="flex-1 overflow-hidden flex flex-col p-6 gap-6 relative">

                    {/* Search Input Bar */}
                    <form onSubmit={handleScan} className="relative shrink-0 group">
                        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-purple-500/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-lg"></div>
                        <div className="relative flex items-center bg-black border border-cyan-900/50 rounded-lg overflow-hidden focus-within:border-cyan-500/80 focus-within:shadow-[0_0_30px_rgba(6,182,212,0.2)] transition-all">
                            <div className="pl-6 text-cyan-500">
                                <Terminal size={20} />
                            </div>
                            <input
                                autoFocus
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                disabled={phase !== 'IDLE'}
                                placeholder="ENTER TARGET: IPv4, IPv6, MAC, DOMAIN, OR ENTITY ALIAS..."
                                className="w-full bg-transparent py-5 px-4 text-cyan-300 font-bold tracking-wider focus:outline-none placeholder:text-cyan-950 disabled:opacity-50 text-glow"
                            />
                            <button
                                type="submit"
                                disabled={phase !== 'IDLE' || !query.trim()}
                                className="mx-2 px-8 py-3 bg-cyan-950/40 hover:bg-cyan-900/60 text-cyan-400 font-bold tracking-widest rounded border border-cyan-800/50 hover:border-cyan-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 hover:shadow-[0_0_20px_rgba(0,255,255,0.4)] relative overflow-hidden group/btn"
                            >
                                <div className="absolute inset-0 bg-cyan-400/20 translate-y-full group-hover/btn:translate-y-0 transition-transform"></div>
                                <Crosshair size={16} className="relative z-10" /> <span className="relative z-10">ENGAGE</span>
                            </button>
                        </div>
                    </form>

                    {/* Main Content Grid */}
                    <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">

                        {/* LEFT COLUMN: Logs & Pipeline Status */}
                        <div className="lg:col-span-4 flex flex-col gap-6">

                            {/* Pipeline Stages */}
                            <div className="bg-[#050505] border border-cyan-900/30 rounded-lg p-4 flex flex-col gap-3 relative overflow-hidden">
                                {/* Decorative Hex */}
                                <Hexagon size={120} className="absolute -right-10 -bottom-10 text-cyan-900/10 stroke-[0.5]" />

                                <h3 className="text-[10px] font-bold text-cyan-600 tracking-[0.2em] uppercase border-b border-cyan-900/30 pb-2 flex items-center gap-2">
                                    <Network size={12} /> Integration Pipeline
                                </h3>

                                <PhaseStep active={phase === 'RECON'} completed={progress > 25} label="Global Sensors (Shodan/Censys)" icon={Globe} />
                                <PhaseStep active={phase === 'ANALYZE'} completed={progress > 50} label="Threat Correlation (OTX Vault)" icon={ShieldAlert} />
                                <PhaseStep active={phase === 'EXECUTE'} completed={progress > 75} label="Dark Web Archives (IntelX)" icon={Database} />
                                <PhaseStep active={phase === 'PERSIST'} completed={progress > 90} label="Neural Entity De-Masking" icon={Fingerprint} />

                                {/* Progress Bar */}
                                <div className="mt-4 pt-4 border-t border-cyan-900/30">
                                    <div className="flex justify-between text-[10px] text-cyan-500 font-bold mb-1">
                                        <span>SYSTEM LOAD</span>
                                        <span>{progress}%</span>
                                    </div>
                                    <div className="h-1.5 w-full bg-black rounded-full overflow-hidden border border-cyan-900/50">
                                        <div
                                            className="h-full bg-cyan-500 transition-all duration-300 relative"
                                            style={{ width: `${progress}%` }}
                                        >
                                            <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.5),transparent)] animate-[shimmer_1s_infinite]"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Terminal Logs */}
                            <div className="flex-1 bg-black border border-slate-800 rounded-lg p-4 flex flex-col min-h-0 relative group">
                                <div className="absolute top-0 left-0 w-full h-8 bg-gradient-to-b from-black to-transparent z-10"></div>
                                <h3 className="text-[10px] font-bold text-slate-500 tracking-[0.2em] uppercase mb-2 z-20">Secure Terminal Stream</h3>
                                <div className="flex-1 overflow-y-auto custom-scrollbar text-[11px] text-cyan-600/70 space-y-1.5 z-0 pr-2 pb-4">
                                    {logs.map((log, i) => (
                                        <div key={i} className="animate-in fade-in slide-in-from-left-2 duration-300">
                                            {log.includes('COMPLETE') || log.includes('LOCKED') ? (
                                                <span className="text-emerald-400 font-bold">{log}</span>
                                            ) : log.includes('EXECUTING') || log.includes('SEVERED') ? (
                                                <span className="text-red-500 font-bold">{log}</span>
                                            ) : (
                                                log
                                            )}
                                        </div>
                                    ))}
                                    {isScanning && (
                                        <div className="flex items-center gap-2 mt-2 text-cyan-400 animate-pulse">
                                            <div className="w-1.5 h-3 bg-cyan-400 animate-ping"></div>
                                            <span>Processing...</span>
                                        </div>
                                    )}
                                    <div ref={logEndRef} />
                                </div>
                            </div>
                        </div>

                        {/* RIGHT COLUMN: Results / HUD Overlay */}
                        <div className="lg:col-span-8 relative rounded-lg border border-cyan-900/30 bg-[#050505] overflow-hidden flex flex-col items-center justify-center p-6">

                            {phase === 'IDLE' && (
                                <div className="text-center opacity-40">
                                    <Hexagon size={80} className="mx-auto text-cyan-800 mb-6 stroke-1 animate-[spin_20s_linear_infinite]" />
                                    <p className="text-cyan-600 font-bold tracking-[0.3em] uppercase">Awaiting Target Designation</p>
                                    <p className="text-[10px] text-cyan-800 tracking-widest mt-2">Omni-Probe sensors standing by.</p>
                                </div>
                            )}

                            {isScanning && (
                                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 backdrop-blur-sm z-20">
                                    <div className="relative w-48 h-48">
                                        <div className="absolute inset-0 border-2 border-cyan-500/20 rounded-full border-t-cyan-500 animate-spin"></div>
                                        <div className="absolute inset-4 border-2 border-blue-500/20 rounded-full border-b-blue-500 animate-[spin_1.5s_linear_infinite_reverse]"></div>
                                        <div className="absolute inset-8 border-2 border-purple-500/20 rounded-full border-r-purple-500 animate-[spin_2s_linear_infinite]"></div>
                                        <div className="absolute inset-0 flex items-center justify-center text-cyan-500 font-bold text-xs tracking-widest text-glow">
                                            {progress}%
                                        </div>
                                    </div>
                                    <div className="mt-8 text-cyan-400 font-bold tracking-[0.3em] text-sm animate-pulse text-glow text-glitch" data-text="SYNTHESIZING THREAT MATRIX">
                                        SYNTHESIZING THREAT MATRIX
                                    </div>
                                </div>
                            )}

                            {phase === 'COMPLETED' && intel && (
                                <div className="absolute inset-0 p-6 overflow-y-auto custom-scrollbar animate-in zoom-in-95 duration-500">
                                    <div className="flex items-start justify-between mb-6">
                                        <div>
                                            <h2 className="text-2xl font-black text-red-500 tracking-widest drop-shadow-[0_0_8px_rgba(239,68,68,0.5)] flex items-center gap-3">
                                                <ShieldAlert size={28} /> TARGET ACQUIRED
                                            </h2>
                                            <p className="text-red-400/80 text-xs tracking-[0.2em] mt-1 uppercase">Profile matched across 4 global intel repositories</p>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-[10px] text-slate-500 tracking-widest mb-1">OMNISCIENT RISK SCORE</div>
                                            <div className="text-3xl font-black text-red-500">{intel.risk_score} <span className="text-sm text-red-900 border border-red-900/50 px-2 py-0.5 rounded">/ 100</span></div>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                        {/* Core Identity */}
                                        <div className="bg-red-950/10 border border-red-900/30 p-5 rounded-lg">
                                            <h3 className="text-[10px] font-bold text-red-500 uppercase tracking-[0.2em] mb-4 flex items-center gap-2 border-b border-red-900/30 pb-2">
                                                <Fingerprint size={12} /> Tactical Profile
                                            </h3>
                                            <div className="space-y-3">
                                                <InfoRow label="PRIMARY VECTOR" value={intel.ip} color="text-red-400 font-black text-lg" />
                                                <InfoRow label="GEO-LOCATION" value={intel.location} icon={Globe} color="text-amber-400" />
                                                <InfoRow label="INFRASTRUCTURE" value={intel.org} icon={Server} color="text-slate-300" />
                                                <InfoRow label="EVENT HISTORY" value={intel.history} icon={Activity} color="text-slate-400" />
                                            </div>
                                        </div>

                                        {/* Aliases & Exposure */}
                                        <div className="bg-purple-950/10 border border-purple-900/30 p-5 rounded-lg flex flex-col justify-between">
                                            <div>
                                                <h3 className="text-[10px] font-bold text-purple-500 uppercase tracking-[0.2em] mb-4 flex items-center gap-2 border-b border-purple-900/30 pb-2">
                                                    <Network size={12} /> Neural De-Masking Results
                                                </h3>
                                                <div className="mb-4">
                                                    <div className="text-[10px] text-slate-500 mb-2">RESOLVED ALIASES (INTELX/DARKNET)</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {intel.aliases.map((alias: string, idx: number) => (
                                                            <span key={idx} className="text-xs bg-purple-900/20 text-purple-300 px-2 py-1 rounded border border-purple-800/50 flex items-center gap-1">
                                                                <Search size={10} /> @{alias}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] text-slate-500 mb-2">EXPOSED PORTS / SERVICES (SHODAN)</div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {intel.ports.map((port: string, idx: number) => (
                                                            <span key={idx} className="text-xs font-mono bg-blue-900/20 text-blue-300 px-2 py-1 rounded border border-blue-800/50">
                                                                {port}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Action Bar */}
                                    <div className="flex flex-col md:flex-row gap-4">
                                        <div className="flex-1 bg-red-950/20 border border-red-900/50 p-4 rounded-lg">
                                            <div className="text-[10px] text-red-500 font-bold tracking-widest mb-3">WEAPONIZED CVES DETECTED</div>
                                            <div className="flex flex-wrap gap-2">
                                                {intel.cves.map((cve: string) => (
                                                    <span key={cve} className="text-[10px] bg-red-900 text-white px-2 py-1 rounded shadow-[0_0_10px_rgba(220,38,38,0.4)]">
                                                        {cve}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                        <button
                                            onClick={handleNeutralize}
                                            className="md:w-64 bg-red-600 hover:bg-red-500 text-black font-black py-4 rounded-lg flex items-center justify-center gap-3 hover:shadow-[0_0_30px_rgba(239,68,68,0.6)] transition-all group overflow-hidden relative"
                                        >
                                            <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.2)_50%,transparent_75%)] bg-[length:250%_250%,100%_100%] animate-[shimmer_2s_infinite]"></div>
                                            <Ban size={20} className="relative z-10 group-hover:scale-110 transition-transform" />
                                            <span className="relative z-10 tracking-wider">EXECUTE STRIKE</span>
                                        </button>
                                    </div>
                                </div>
                            )}

                            {phase === 'NEUTRALIZED' && (
                                <div className="absolute inset-0 bg-black flex flex-col items-center justify-center z-30 animate-in fade-in duration-500">
                                    {/* Intensive glitch / success effect overlay */}
                                    <div className="absolute inset-0 bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.5)_50%)] bg-[length:100%_4px] pointer-events-none opacity-20"></div>

                                    <div className="relative">
                                        <Hexagon size={200} className="text-emerald-500/20 animate-pulse stroke-1 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                                        <ShieldAlert size={80} className="text-emerald-500 mb-6 relative z-10 drop-shadow-[0_0_30px_rgba(16,185,129,0.5)]" />
                                    </div>

                                    <h2 className="text-4xl font-black text-emerald-500 tracking-[0.2em] uppercase drop-shadow-[0_0_10px_rgba(16,185,129,0.8)] relative z-10 text-center">
                                        TARGET NEUTRALIZED
                                    </h2>
                                    <p className="text-emerald-400 font-mono text-sm mt-4 relative z-10 bg-emerald-950/50 px-4 py-2 rounded border border-emerald-900/50">
                                        AEG ISOLATION PROTOCOL SUCCESSFUL.
                                    </p>
                                    <p className="text-emerald-800 text-[10px] tracking-widest mt-2">Network bridge severed via zero-trust firewall injection.</p>

                                    <button
                                        onClick={() => setPhase('IDLE')}
                                        className="mt-12 text-slate-500 hover:text-emerald-400 text-xs font-bold tracking-widest transition-colors flex items-center gap-2"
                                    >
                                        <Unlock size={14} /> RESET OMNI-PROBE
                                    </button>
                                </div>
                            )}

                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// Subcomponents
const PhaseStep = ({ active, completed, label, icon: Icon }: any) => (
    <div className={clsx("flex items-center gap-3 transition-all duration-500",
        completed ? "text-cyan-500" : active ? "text-cyan-400 font-bold" : "text-slate-700 opacity-50")}>
        <div className={clsx("relative flex items-center justify-center w-6 h-6 rounded-full border",
            completed ? "bg-cyan-900/30 border-cyan-500" : active ? "border-cyan-400" : "border-slate-800")}>
            {completed ? <div className="w-2 h-2 bg-cyan-500 rounded-full"></div> : <Icon size={10} />}
            {active && !completed && <div className="absolute inset-0 rounded-full border border-cyan-400 animate-ping"></div>}
        </div>
        <span className="text-xs tracking-wider">{label}</span>
    </div>
);

const InfoRow = ({ label, value, icon: Icon, color = "text-cyan-300" }: any) => (
    <div className="flex justify-between items-center text-sm font-mono border-b border-white/5 py-1.5 last:border-0 group">
        <span className="text-slate-500 text-[10px] tracking-widest group-hover:text-slate-400 transition-colors">{label}</span>
        <span className={clsx("font-bold flex items-center gap-2", color)}>
            {Icon && <Icon size={12} className="opacity-70" />}
            {value}
        </span>
    </div>
);
