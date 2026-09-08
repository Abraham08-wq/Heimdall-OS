import React, { useState, useEffect, useCallback } from 'react';
import {
    Clock, AlertTriangle, CheckCircle2, ArrowRight, Activity,
    Shield, Crosshair, ZapOff, Filter, ChevronRight, Eye
} from 'lucide-react';
import { clsx } from 'clsx';

// ─── Types ────────────────────────────────────────────────────────────────────

interface TimelineEvent {
    id: string;
    ts: string;
    type: string;
    source: string;
    target: string;
    description: string;
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'INFO';
    technique?: string;
    phase?: string;
    status?: 'detected' | 'blocked' | 'active';
}

interface AttackTimelineEngineProps {
    events?: TimelineEvent[];
}

// ─── Kill-chain phases ────────────────────────────────────────────────────────

const KC_PHASES = [
    { key: 'INITIAL ACCESS', short: 'INIT', color: '#6366f1' },
    { key: 'EXECUTION', short: 'EXEC', color: '#8b5cf6' },
    { key: 'PERSISTENCE', short: 'PERS', color: '#a78bfa' },
    { key: 'PRIVILEGE ESCALATION', short: 'PRIV', color: '#f97316' },
    { key: 'CREDENTIAL ACCESS', short: 'CRED', color: '#ef4444' },
    { key: 'LATERAL MOVEMENT', short: 'LAT', color: '#f43f5e' },
    { key: 'EXFILTRATION', short: 'EXFIL', color: '#dc2626' },
    { key: 'IMPACT', short: 'IMPCT', color: '#7f1d1d' },
];

const LIVE_EVENTS: Omit<TimelineEvent, 'id' | 'ts'>[] = [
    { type: 'INITIAL ACCESS', source: '185.220.101.45', target: 'VPN Gateway', description: 'Credential stuffing — admin@corp.com brute-forced via Tor exit node', severity: 'CRITICAL', technique: 'T1078', phase: 'INITIAL ACCESS', status: 'detected' },
    { type: 'EXECUTION', source: 'WORKSTN-089', target: 'svchost.exe', description: 'Macro-dropped PowerShell payload — encoded base64 downloader (LOLBin)', severity: 'CRITICAL', technique: 'T1059.001', phase: 'EXECUTION', status: 'active' },
    { type: 'PERSISTENCE', source: '10.0.1.45', target: 'HKCU\\Run', description: 'Registry run key: WindowsUpdateHelper → %TEMP%\\svchst.exe', severity: 'HIGH', technique: 'T1547.001', phase: 'PERSISTENCE', status: 'blocked' },
    { type: 'PRIV ESCALATION', source: 'WORKSTN-089', target: 'DC-01', description: 'Token impersonation via SeImpersonatePrivilege — NT AUTHORITY\\SYSTEM', severity: 'CRITICAL', technique: 'T1134.001', phase: 'PRIVILEGE ESCALATION', status: 'active' },
    { type: 'CREDENTIAL ACCESS', source: 'DC-01', target: 'lsass.exe', description: 'LSASS memory read — Mimikatz sekurlsa::logonpasswords executed', severity: 'CRITICAL', technique: 'T1003.001', phase: 'CREDENTIAL ACCESS', status: 'detected' },
    { type: 'LATERAL MOVEMENT', source: '10.0.1.45', target: '10.0.1.10', description: 'SMB pass-the-hash using NTLM hash: aad3b435:31d6cfe0', severity: 'HIGH', technique: 'T1550.002', phase: 'LATERAL MOVEMENT', status: 'blocked' },
    { type: 'EXFILTRATION', source: '10.0.5.11', target: '45.33.22.11', description: '2.3GB encrypted upload to external CDN — LZ4 + AES-256 payload', severity: 'HIGH', technique: 'T1041', phase: 'EXFILTRATION', status: 'active' },
    { type: 'COMMAND & CONTROL', source: '10.0.1.22', target: 'ghost-c2.ext', description: 'DNS-over-HTTPS tunneling — 8,420 TXT queries/hr to *.corp-internal-vpn.net', severity: 'CRITICAL', technique: 'T1071.004', phase: 'EXFILTRATION', status: 'active' },
];

// ─── Severity & status config ─────────────────────────────────────────────────

const SEV_CFG = {
    CRITICAL: { dot: 'bg-rose-500 shadow-[0_0_12px_rgba(239,68,68,0.9)]', text: 'text-rose-400', badge: 'bg-rose-950/60 border-rose-700 text-rose-400', border: 'border-rose-900/50', bg: 'bg-rose-950/10' },
    HIGH: { dot: 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]', text: 'text-orange-400', badge: 'bg-orange-950/60 border-orange-700 text-orange-400', border: 'border-orange-900/40', bg: 'bg-orange-950/5' },
    MEDIUM: { dot: 'bg-amber-500', text: 'text-amber-400', badge: 'bg-amber-950/50 border-amber-700 text-amber-400', border: 'border-amber-900/20', bg: '' },
    INFO: { dot: 'bg-cyan-500', text: 'text-cyan-400', badge: 'bg-cyan-950/50 border-cyan-700 text-cyan-400', border: 'border-slate-800', bg: '' },
};

const STATUS_CFG = {
    detected: { icon: <AlertTriangle size={8} />, color: 'text-amber-400', label: 'DETECTED' },
    blocked: { icon: <CheckCircle2 size={8} />, color: 'text-emerald-400', label: 'BLOCKED' },
    active: { icon: <Activity size={8} className="animate-pulse" />, color: 'text-rose-400', label: 'ACTIVE' },
};

const SEVERITY_FILTERS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'INFO'] as const;
type SeverityFilter = typeof SEVERITY_FILTERS[number];

// ─── Component ────────────────────────────────────────────────────────────────

export const AttackTimelineEngine: React.FC<AttackTimelineEngineProps> = ({ events: externalEvents }) => {
    const [events, setEvents] = useState<TimelineEvent[]>([]);
    const [filter, setFilter] = useState<SeverityFilter>('ALL');
    const [activePhase, setActivePhase] = useState<string | null>(null);
    const [actionTarget, setActionTarget] = useState<string | null>(null);

    const addEvent = useCallback((data: Omit<TimelineEvent, 'id' | 'ts'>) => {
        setEvents(prev => [{
            ...data,
            id: `${Date.now()}-${Math.random()}`,
            ts: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        }, ...prev].slice(0, 50));
    }, []);

    useEffect(() => {
        if (externalEvents?.length) {
            setEvents(externalEvents.map((e, i) => ({ ...e, id: `ext-${i}` })));
        }
    }, [externalEvents]);

    const handleOperatorAction = (action: string, event: TimelineEvent) => {
        setActionTarget(`${action} ← ${event.source}`);
        setTimeout(() => setActionTarget(null), 3000);
    };

    // Kill-chain progress: which phases have been observed
    const observedPhases = new Set(events.map(e => e.phase).filter(Boolean));
    const kcProgress = KC_PHASES.findLastIndex(p => observedPhases.has(p.key));
    const critActive = events.filter(e => e.severity === 'CRITICAL' && e.status === 'active').length;

    // Filtered events
    const filtered = events.filter(e => {
        if (filter !== 'ALL' && e.severity !== filter) return false;
        if (activePhase && e.phase !== activePhase) return false;
        return true;
    });

    return (
        <div className="flex flex-col h-full bg-[#050507] border border-slate-900/80 overflow-hidden font-mono">

            {/* ── Header ── */}
            <div className="px-3 py-2 border-b border-slate-800/60 bg-black/60 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <Clock size={11} className="text-rose-500" />
                    <span className="text-[10px] font-bold text-slate-300 tracking-widest">ATTACK KILL-CHAIN</span>
                </div>
                <div className="flex items-center gap-2">
                    {critActive > 0 && (
                        <span className="text-[8px] font-bold text-rose-400 bg-rose-950/50 border border-rose-800 px-1.5 py-0.5 rounded animate-pulse">
                            {critActive} ACTIVE
                        </span>
                    )}
                    <span className="text-[8px] text-slate-700">{events.length} events</span>
                </div>
            </div>

            {/* ── Kill-chain Stage Progress Bar ── */}
            <div className="px-2 py-2 border-b border-slate-900/60 bg-[#080808] shrink-0">
                <div className="text-[7px] text-slate-700 tracking-widest mb-1.5 font-bold">KILL-CHAIN PROGRESSION</div>
                <div className="flex items-center gap-0.5 overflow-x-auto no-scrollbar">
                    {KC_PHASES.map((phase, idx) => {
                        const reached = idx <= kcProgress;
                        const observed = observedPhases.has(phase.key);
                        const isActive = activePhase === phase.key;
                        return (
                            <button
                                key={phase.key}
                                title={phase.key}
                                onClick={() => setActivePhase(isActive ? null : phase.key)}
                                className={clsx(
                                    'flex-1 text-[7px] font-bold tracking-wider py-1 rounded transition-all truncate',
                                    isActive ? 'ring-1 ring-white/30' : '',
                                    reached
                                        ? 'text-white'
                                        : 'text-slate-800'
                                )}
                                style={{
                                    backgroundColor: reached ? `${phase.color}30` : '#111',
                                    borderBottom: reached ? `2px solid ${phase.color}` : '2px solid transparent',
                                    color: observed ? phase.color : reached ? '#666' : '#333',
                                }}
                            >
                                {phase.short}
                            </button>
                        );
                    })}
                </div>
                {activePhase && (
                    <div className="mt-1 text-[8px] text-slate-500">
                        Filtering: <span className="text-cyan-500">{activePhase}</span>
                        <button onClick={() => setActivePhase(null)} className="ml-2 text-slate-700 hover:text-slate-500">
                            ×clear
                        </button>
                    </div>
                )}
            </div>

            {/* ── Action toast ── */}
            {actionTarget && (
                <div className="px-3 py-1.5 bg-cyan-950/30 border-b border-cyan-800/40 text-[9px] text-cyan-400 font-bold flex items-center gap-2 shrink-0">
                    <Crosshair size={9} />
                    EXECUTING: {actionTarget}
                </div>
            )}

            {/* ── Severity filter tabs ── */}
            <div className="flex border-b border-slate-900/60 shrink-0">
                <Filter size={9} className="text-slate-700 self-center ml-2 shrink-0" />
                {SEVERITY_FILTERS.map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={clsx(
                            'flex-1 py-1 text-[8px] font-bold tracking-widest transition-colors',
                            filter === f ? 'text-cyan-400 border-b-2 border-cyan-500 bg-cyan-950/10'
                                : 'text-slate-700 hover:text-slate-500'
                        )}
                    >
                        {f === 'ALL' ? `ALL (${events.length})` : f}
                    </button>
                ))}
            </div>

            {/* ── Timeline list ── */}
            <div className="flex-1 overflow-y-auto custom-scrollbar relative">
                <div className="absolute left-[22px] top-0 bottom-0 w-px bg-slate-800/50 pointer-events-none" />

                {filtered.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-700 gap-2">
                        <Clock size={20} />
                        <p className="text-[9px] tracking-widest">No events match filters</p>
                    </div>
                ) : (
                    <div className="py-2 pr-2 pl-1.5 space-y-2">
                        {filtered.map(evt => {
                            const sev = SEV_CFG[evt.severity];
                            const sta = evt.status ? STATUS_CFG[evt.status] : null;
                            const phaseData = KC_PHASES.find(p => p.key === evt.phase);
                            return (
                                <div key={evt.id} className="flex gap-2.5 items-start group cursor-default">
                                    {/* Timeline dot */}
                                    <div className="flex flex-col items-center shrink-0 mt-2 ml-1">
                                        <div className={clsx('w-2.5 h-2.5 rounded-full border-2 border-[#050507] z-10 relative', sev.dot)} />
                                    </div>

                                    {/* Event card */}
                                    <div className={clsx(
                                        'flex-1 rounded border p-2 transition-all duration-200 group-hover:brightness-110',
                                        sev.border, sev.bg, 'bg-black/50'
                                    )}>
                                        {/* Top row: badges */}
                                        <div className="flex items-center gap-1 mb-1.5 flex-wrap">
                                            <span className={clsx('text-[7px] font-bold px-1 py-0.5 rounded border tracking-widest', sev.badge)}>
                                                {evt.severity}
                                            </span>
                                            <span className={clsx('text-[8px] font-bold', sev.text)}>{evt.type}</span>
                                            {evt.technique && (
                                                <span className="text-[7px] bg-slate-900 border border-slate-800 text-slate-600 px-1 rounded font-mono">
                                                    {evt.technique}
                                                </span>
                                            )}
                                            {phaseData && (
                                                <span
                                                    className="text-[7px] font-bold px-1 py-0.5 rounded ml-auto shrink-0"
                                                    style={{ color: phaseData.color, backgroundColor: `${phaseData.color}18`, border: `1px solid ${phaseData.color}40` }}
                                                >
                                                    {phaseData.short}
                                                </span>
                                            )}
                                        </div>

                                        {/* Source → Target */}
                                        <div className="flex items-center gap-1.5 mb-1.5">
                                            <span className="text-[8px] text-slate-600 font-mono">{evt.source}</span>
                                            <ArrowRight size={8} className="text-slate-700 shrink-0" />
                                            <span className="text-[8px] text-slate-400 font-bold font-mono">{evt.target}</span>
                                            {sta && (
                                                <span className={clsx('flex items-center gap-0.5 text-[7px] font-bold ml-auto shrink-0', sta.color)}>
                                                    {sta.icon} {sta.label}
                                                </span>
                                            )}
                                        </div>

                                        {/* Description */}
                                        <p className="text-[8px] text-slate-500 leading-relaxed mb-1.5">{evt.description}</p>

                                        {/* Operator action buttons */}
                                        <div className="flex items-center gap-1 pt-1 border-t border-slate-900/60">
                                            <span className="text-[7px] text-slate-800 mr-1">RESPOND:</span>
                                            {[
                                                { icon: <Eye size={8} />, label: 'INVESTIGATE', col: 'text-cyan-500  hover:bg-cyan-950/30' },
                                                { icon: <ZapOff size={8} />, label: 'ISOLATE', col: 'text-rose-500  hover:bg-rose-950/30' },
                                                { icon: <Shield size={8} />, label: 'BLOCK', col: 'text-orange-500 hover:bg-orange-950/30' },
                                                { icon: <ChevronRight size={8} />, label: 'ESCALATE', col: 'text-amber-500 hover:bg-amber-950/30' },
                                            ].map(btn => (
                                                <button
                                                    key={btn.label}
                                                    onClick={() => handleOperatorAction(btn.label, evt)}
                                                    className={clsx(
                                                        'flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[7px] font-bold transition-colors',
                                                        btn.col
                                                    )}
                                                    title={btn.label}
                                                >
                                                    {btn.icon}
                                                    <span className="hidden group-hover:inline">{btn.label}</span>
                                                </button>
                                            ))}
                                            <span className="text-[7px] text-slate-800 ml-auto">{evt.ts}</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};
