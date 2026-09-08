'use client';

import { useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { TelemetryMessage } from '@/components/providers/TelemetryProvider';
import { useLiveTelemetry } from '@/hooks/useLiveTelemetry';

type ThreatPayload = {
    title?: string;
    source?: string;
    target?: string;
    severity?: 'low' | 'medium' | 'high' | 'critical';
    summary?: string;
};

type LiveThreatFeedProps = {
    className?: string;
    maxItems?: number;
};

function severityTone(severity: string) {
    if (severity === 'critical') {
        return {
            badge: 'bg-red-500/20 text-red-200 border-red-400/35',
            flash: 'rgba(239, 68, 68, 0.18)',
        };
    }

    if (severity === 'high') {
        return {
            badge: 'bg-amber-500/20 text-amber-200 border-amber-400/35',
            flash: 'rgba(245, 158, 11, 0.18)',
        };
    }

    if (severity === 'medium') {
        return {
            badge: 'bg-yellow-500/15 text-yellow-200 border-yellow-400/30',
            flash: 'rgba(234, 179, 8, 0.14)',
        };
    }

    return {
        badge: 'bg-emerald-500/15 text-emerald-200 border-emerald-400/30',
        flash: 'rgba(16, 185, 129, 0.1)',
    };
}

function parseThreat(message: TelemetryMessage<ThreatPayload>) {
    const payload = message.payload ?? {};
    const severity = (payload.severity ?? message.severity ?? 'low').toLowerCase();

    return {
        id: message.id,
        timestamp: message.timestamp,
        title: payload.title ?? message.event_type,
        source: payload.source ?? 'unknown',
        target: payload.target ?? 'unknown',
        summary: payload.summary ?? 'No additional context available.',
        severity,
    };
}

export function LiveThreatFeed({ className = '', maxItems = 100 }: LiveThreatFeedProps) {
    const { items, connectionState } = useLiveTelemetry<ThreatPayload>('threats', { maxItems });

    const threats = useMemo(() => items.map(parseThreat), [items]);

    return (
        <section className={`rounded-3xl border border-white/10 bg-slate-950/70 p-4 backdrop-blur-md ${className}`}>
            <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-red-500/10 text-red-300">
                        <ShieldAlert size={16} />
                    </span>
                    <div>
                        <p className="text-[10px] uppercase tracking-[0.34em] text-slate-500">Live Telemetry</p>
                        <h3 className="text-sm font-semibold text-white">Threat Feed</h3>
                    </div>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.3em] text-slate-300">
                    {connectionState}
                </span>
            </div>

            <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-2 px-3 pb-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
                <span>Threat</span>
                <span>Source</span>
                <span>Target</span>
                <span>Severity</span>
            </div>

            <div className="space-y-2">
                <AnimatePresence initial={false}>
                    {threats.map((threat) => {
                        const tone = severityTone(threat.severity);

                        return (
                            <motion.div
                                key={threat.id}
                                layout
                                initial={{ opacity: 0, y: -20, height: 0, backgroundColor: tone.flash }}
                                animate={{ opacity: 1, y: 0, height: 'auto', backgroundColor: 'rgba(0,0,0,0)' }}
                                exit={{ opacity: 0, y: 12, height: 0 }}
                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3"
                            >
                                <div className="min-w-0">
                                    <p className="truncate text-sm font-medium text-white">{threat.title}</p>
                                    <p className="truncate text-xs text-slate-400">{threat.summary}</p>
                                </div>
                                <p className="truncate text-xs text-slate-300">{threat.source}</p>
                                <p className="truncate text-xs text-slate-300">{threat.target}</p>
                                <div className="justify-self-end">
                                    <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.24em] ${tone.badge}`}>
                                        {threat.severity}
                                    </span>
                                </div>
                            </motion.div>
                        );
                    })}
                </AnimatePresence>

                {threats.length === 0 ? (
                    <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-8 text-sm text-slate-400">
                        <AlertTriangle size={16} className="text-amber-300" />
                        Waiting for threat events from telemetry stream.
                    </div>
                ) : null}
            </div>
        </section>
    );
}
