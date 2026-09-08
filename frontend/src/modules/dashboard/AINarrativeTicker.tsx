import React, { useEffect, useRef, useState, useCallback } from 'react';
import { BrainCircuit, AlertTriangle, TrendingUp, Eye, Zap, Radio } from 'lucide-react';
import { clsx } from 'clsx';

// ─── Types ───────────────────────────────────────────────────────────────────

type EventType = 'OBSERVATION' | 'CORRELATION' | 'RECOMMENDATION' | 'CRITICAL' | 'PREDICTION';

interface NarrativeEvent {
    id: string;
    timestamp: string;
    text: string;
    confidence: number;
    type: EventType;
    source?: string;
    mitre?: string;
}

interface AINarrativeTickerProps {
    narrativeStream?: NarrativeEvent[];
}

// ─── Live AI narrative pool ───────────────────────────────────────────────────

const NARRATIVE_POOL: Omit<NarrativeEvent, 'id' | 'timestamp'>[] = [
    { type: 'CRITICAL', confidence: 96, mitre: 'T1003.001', source: 'DC-01', text: 'LSASS credential dump confirmed on DC-01. NTLM hashes for 14 domain accounts extracted. Immediate credential rotation required — active lateral movement risk.', },
    { type: 'CORRELATION', confidence: 91, mitre: 'T1071.004', source: '10.0.1.22', text: 'DNS query entropy (4.8 bits) on 10.0.1.22 correlates with known Cobalt Strike DNS beacon pattern. 8,420 TXT queries in 60 minutes — C2 channel confirmed.', },
    { type: 'PREDICTION', confidence: 87, source: 'Geopolitical Feed', text: 'SIGINT correlation: APT-41 infrastructure activated 3h ago. 94% probability of coordinated campaign against financial sector within 72h. Recommend elevated posture.', },
    { type: 'RECOMMENDATION', confidence: 100, mitre: 'T1078', source: 'UEBA Engine', text: 'Invoke CREDENTIAL_INVALIDATION playbook immediately. Impossible travel detected for admin@corp.com — simultaneous sessions from US East and EU West (112ms apart).', },
    { type: 'OBSERVATION', confidence: 78, mitre: 'T1046', source: 'Omni-Probe', text: 'Internal recon activity detected from 192.168.1.105. Half-open SYN sweep across /16 subnet — 892 unique destinations. Low-and-slow evasion pattern identified.', },
    { type: 'CRITICAL', confidence: 99, mitre: 'T1486', source: 'FILESERVER-01', text: 'Ransomware pre-detonation IOC: VSS deletion command executed (vssadmin delete shadows /all). Bulk file rename with .locked extension in progress. Isolate IMMEDIATELY.', },
    { type: 'CORRELATION', confidence: 88, mitre: 'T1550.002', source: 'Lateral Movement', text: 'Pass-the-Hash chain reconstructed: WORKSTN-089 → FILESERVER-01 → DC-01. All hops used NTLM hash b4b9b02e6f09a9bd760f388b67351e2b. No plaintext password required.', },
    { type: 'RECOMMENDATION', confidence: 95, source: 'Threat Intelligence', text: 'Deploy Sentinel YARA rule NEXUS_LOCKBIT_V3_BEHAVIORAL to all Windows endpoints. 3 additional hosts likely infected based on network traffic pattern similarity (Jaccard: 0.94).', },
    { type: 'PREDICTION', confidence: 82, source: 'ML Model v4.2', text: 'Isolation Forest outlier score for 45.33.22.11: 97th percentile. Predicted exfiltration window: next 4-6 hours via HTTPS. Recommend honeypot redirect via HONEY-TRAP command.', },
    { type: 'OBSERVATION', confidence: 71, mitre: 'T1195', source: 'CI/CD Monitor', text: 'Anomalous Docker image push to ECR registry by svc_deploy account. Image hash mismatch from known-good baseline. Supply chain compromise possible — quarantine pending review.', },
];

const TYPE_CFG: Record<EventType, { icon: React.ReactNode; dot: string; badge: string; text: string; glow?: string }> = {
    CRITICAL: { icon: <AlertTriangle size={9} />, dot: 'bg-rose-500 shadow-[0_0_10px_rgba(239,68,68,0.8)] animate-pulse', badge: 'bg-rose-950/60 border-rose-700 text-rose-400', text: 'text-rose-200', glow: 'shadow-[0_0_20px_rgba(239,68,68,0.08)]' },
    PREDICTION: { icon: <TrendingUp size={9} />, dot: 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]', badge: 'bg-purple-950/60 border-purple-700 text-purple-400', text: 'text-slate-300' },
    RECOMMENDATION: { icon: <Zap size={9} />, dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]', badge: 'bg-amber-950/60 border-amber-700 text-amber-400', text: 'text-slate-300' },
    CORRELATION: { icon: <Radio size={9} />, dot: 'bg-indigo-500', badge: 'bg-indigo-950/50 border-indigo-700 text-indigo-400', text: 'text-slate-300' },
    OBSERVATION: { icon: <Eye size={9} />, dot: 'bg-cyan-500', badge: 'bg-cyan-950/50 border-cyan-700 text-cyan-400', text: 'text-slate-400' },
};

// ─── Component ────────────────────────────────────────────────────────────────

export const AINarrativeTicker: React.FC<AINarrativeTickerProps> = ({ narrativeStream: external }) => {
    const [events, setEvents] = useState<NarrativeEvent[]>([]);
    const streamEndRef = useRef<HTMLDivElement>(null);

    const addEvent = useCallback((data: Omit<NarrativeEvent, 'id' | 'timestamp'>) => {
        setEvents(prev => [{
            ...data,
            id: `${Date.now()}-${Math.random()}`,
            timestamp: new Date().toLocaleTimeString('en-GB', { hour12: false }),
        }, ...prev].slice(0, 40));
    }, []);

    useEffect(() => {
        if (external?.length) {
            setEvents(external);
        }
    }, [addEvent, external]);

    const criticals = events.filter(e => e.type === 'CRITICAL').length;

    return (
        <div className="flex flex-col h-full bg-[#050507] border border-slate-900/80 font-mono overflow-hidden">
            {/* Header */}
            <div className="px-3 py-2.5 border-b border-indigo-900/30 bg-black/60 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <BrainCircuit size={12} className="text-indigo-400 animate-pulse" />
                    <span className="text-[10px] font-bold text-indigo-400 tracking-widest">NEXUS AI — INTELLIGENCE FEED</span>
                </div>
                <div className="flex items-center gap-2">
                    {criticals > 0 && (
                        <span className="text-[8px] bg-rose-950/50 border border-rose-800 text-rose-400 px-1.5 py-0.5 rounded font-bold animate-pulse">{criticals} CRITICAL</span>
                    )}
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
                </div>
            </div>

            {/* Type filter pills */}
            <div className="flex gap-1 px-2 py-1.5 border-b border-slate-900/60 flex-wrap shrink-0 bg-black/40">
                {(['CRITICAL', 'PREDICTION', 'RECOMMENDATION', 'CORRELATION', 'OBSERVATION'] as EventType[]).map(t => {
                    const cfg = TYPE_CFG[t];
                    const count = events.filter(e => e.type === t).length;
                    return count > 0 ? (
                        <span key={t} className={clsx("text-[7px] font-bold px-1.5 py-0.5 rounded border", cfg.badge)}>
                            {t.slice(0, 4)} ×{count}
                        </span>
                    ) : null;
                })}
            </div>

            {/* Stream */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                {events.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-700 gap-2 opacity-50">
                        <BrainCircuit size={24} />
                        <p className="text-[10px] uppercase tracking-widest text-center">Neural Engine Standby</p>
                    </div>
                ) : events.map(event => {
                    const cfg = TYPE_CFG[event.type];
                    return (
                        <div key={event.id} className={clsx("rounded border border-slate-900/60 bg-black/50 p-2.5 transition-all", cfg.glow)}>
                            {/* Meta row */}
                            <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                                <div className={clsx("w-1.5 h-1.5 rounded-full shrink-0", cfg.dot)} />
                                <span className={clsx("flex items-center gap-0.5 text-[8px] font-bold px-1.5 py-0.5 rounded border", cfg.badge)}>
                                    {cfg.icon} {event.type}
                                </span>
                                {event.source && <span className="text-[8px] text-slate-600">SRC: {event.source}</span>}
                                {event.mitre && (
                                    <span className="text-[8px] text-slate-600 border border-slate-800 px-1 rounded">{event.mitre}</span>
                                )}
                                <span className="text-[8px] text-slate-700 ml-auto">{event.timestamp}</span>
                            </div>

                            {/* Body */}
                            <p className={clsx("text-[10px] leading-relaxed font-sans", cfg.text)}>{event.text}</p>

                            {/* Confidence bar */}
                            <div className="flex items-center gap-2 mt-2">
                                <span className="text-[7px] text-slate-700 tracking-widest shrink-0">CONFIDENCE</span>
                                <div className="flex-1 h-0.5 bg-slate-900 rounded-full overflow-hidden">
                                    <div className={clsx("h-full rounded-full transition-all duration-1000",
                                        event.confidence >= 90 ? 'bg-rose-500' :
                                            event.confidence >= 80 ? 'bg-amber-500' : 'bg-emerald-500'
                                    )} style={{ width: `${event.confidence}%` }} />
                                </div>
                                <span className="text-[8px] text-slate-500 font-mono shrink-0">{event.confidence}%</span>
                            </div>
                        </div>
                    );
                })}
                <div ref={streamEndRef} />
            </div>
        </div>
    );
};
