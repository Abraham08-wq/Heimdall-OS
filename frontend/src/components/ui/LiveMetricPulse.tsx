'use client';

import { useMemo, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useLiveTelemetry } from '@/hooks/useLiveTelemetry';

type MetricPayload = {
    value?: number;
    count?: number;
    total?: number;
};

type LiveMetricPulseProps = {
    label: string;
    channel: string;
    metricKey?: keyof MetricPayload;
    className?: string;
};

function resolveMetricValue(
    items: Array<{ payload: MetricPayload }>,
    metricKey: keyof MetricPayload,
) {
    const latest = items[0]?.payload;

    if (!latest) {
        return 0;
    }

    const candidate = latest[metricKey] ?? latest.value ?? latest.count ?? latest.total;
    return typeof candidate === 'number' ? candidate : 0;
}

export function LiveMetricPulse({ label, channel, metricKey = 'value', className = '' }: LiveMetricPulseProps) {
    const { items, connectionState } = useLiveTelemetry<MetricPayload>(channel, { maxItems: 20 });
    const value = useMemo(() => resolveMetricValue(items, metricKey), [items, metricKey]);

    const previousRef = useRef(value);
    const delta = value - previousRef.current;
    const isSpike = delta > 0;
    previousRef.current = value;

    return (
        <div className={`rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 backdrop-blur-sm ${className}`}>
            <div className="mb-2 flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
                <span>{label}</span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-slate-300">{connectionState}</span>
            </div>

            <div className="flex items-center justify-between gap-3">
                <div className="relative h-9 overflow-hidden">
                    <AnimatePresence mode="wait" initial={false}>
                        <motion.span
                            key={value}
                            className="block text-2xl font-semibold text-white"
                            initial={{ y: 22, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            exit={{ y: -22, opacity: 0 }}
                            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        >
                            {value.toLocaleString()}
                        </motion.span>
                    </AnimatePresence>
                </div>

                <div className="flex items-center gap-2 text-xs text-slate-300">
                    <motion.span
                        className={`h-2.5 w-2.5 rounded-full ${isSpike ? 'bg-red-400' : 'bg-emerald-400'}`}
                        animate={{ scale: isSpike ? [1, 1.35, 1] : [1, 1.15, 1], opacity: [0.7, 1, 0.7] }}
                        transition={{ repeat: Infinity, duration: 1.6, type: 'spring', stiffness: 300, damping: 30 }}
                    />
                    {isSpike ? 'spiking' : 'stable'}
                </div>
            </div>
        </div>
    );
}
