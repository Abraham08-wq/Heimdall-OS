'use client';

import { useEffect, useState } from 'react';
import { QueryClientProvider, useIsFetching, useIsMutating } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { queryClient } from '@/lib/queryClient';
import { AuthProvider } from '@/components/providers/AuthProvider';
import { TelemetryProvider } from '@/components/providers/TelemetryProvider';
import { SovereignPaletteProvider } from '@/components/CommandCenter/SovereignPalette';

function QueryActivityLayer() {
    const isFetching = useIsFetching();
    const isMutating = useIsMutating();
    const isBusy = isFetching + isMutating > 0;

    return (
        <AnimatePresence>
            {isBusy ? (
                <motion.div
                    key="query-activity"
                    className="fixed inset-x-0 top-0 z-[250] h-1 origin-left bg-gradient-to-r from-teal-400 via-cyan-400 to-indigo-500 shadow-[0_0_24px_rgba(45,212,191,0.45)]"
                    initial={{ scaleX: 0, opacity: 0 }}
                    animate={{ scaleX: 1, opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
            ) : null}
        </AnimatePresence>
    );
}

type QueryErrorDetail = {
    source: 'query' | 'mutation';
    key?: unknown;
    message: string;
};

function QueryErrorLayer() {
    const [error, setError] = useState<QueryErrorDetail | null>(null);

    useEffect(() => {
        const handleQueryError = (event: Event) => {
            const detail = (event as CustomEvent<QueryErrorDetail>).detail;
            if (!detail?.message) {
                return;
            }

            setError(detail);
            window.setTimeout(() => setError(null), 3200);
        };

        window.addEventListener('projectxy:query-error', handleQueryError);
        return () => window.removeEventListener('projectxy:query-error', handleQueryError);
    }, []);

    return (
        <AnimatePresence>
            {error ? (
                <motion.div
                    key="query-error"
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    className="fixed right-4 top-4 z-[280] max-w-sm rounded-2xl border border-rose-400/30 bg-rose-500/15 px-4 py-3 text-sm text-rose-100 backdrop-blur-md"
                >
                    <p className="text-[10px] uppercase tracking-[0.3em] text-rose-200/85">{error.source} error</p>
                    <p className="mt-1 text-sm">{error.message}</p>
                </motion.div>
            ) : null}
        </AnimatePresence>
    );
}

export function Providers({ children }: { children: React.ReactNode }) {
    useEffect(() => {
        const handleError = (event: ErrorEvent) => {
            console.error('Global runtime error', event.error || event.message);
        };

        window.addEventListener('error', handleError);
        return () => window.removeEventListener('error', handleError);
    }, []);

    return (
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <TelemetryProvider>
                    {/* Single global Cmd+K palette — no per-component duplicates */}
                    <SovereignPaletteProvider>
                        <QueryActivityLayer />
                        <QueryErrorLayer />
                        {children}
                    </SovereignPaletteProvider>
                </TelemetryProvider>
            </AuthProvider>
        </QueryClientProvider>
    );
}