'use client';

import { useEffect, useRef, useState } from 'react';

type Status = 'online' | 'offline' | 'checking';

// Poll cadence and how long we wait before calling a request dead.
const POLL_INTERVAL_MS = 10_000;
const REQUEST_TIMEOUT_MS = 5_000;

// Reached through the Next.js proxy, same path the rest of the app uses.
// The backend port is never exposed directly, so we go via /api/v1.
// This endpoint requires auth and returns 401 without a token — which is fine:
// a 401 still proves the backend process is answering (see probeBackend).
const HEALTH_URL = '/api/v1/intel/command/system-status';

async function probeBackend(signal: AbortSignal): Promise<boolean> {
    try {
        const res = await fetch(HEALTH_URL, { signal, cache: 'no-store' });
        // Any answer from the server means the process is up — even a 401 or 404.
        // Only a gateway error means the proxy couldn't reach the backend.
        return !(res.status === 502 || res.status === 503 || res.status === 504);
    } catch {
        // Network failure, timeout, or abort: treat as unreachable.
        return false;
    }
}

export function BackendStatus() {
    const [status, setStatus] = useState<Status>('checking');
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        let active = true;

        const check = async () => {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

            const ok = await probeBackend(controller.signal);
            clearTimeout(timeout);

            if (!active) return;
            setStatus(ok ? 'online' : 'offline');
            timer.current = setTimeout(check, POLL_INTERVAL_MS);
        };

        check();

        return () => {
            active = false;
            if (timer.current) clearTimeout(timer.current);
        };
    }, []);

    const config = {
        online: {
            dot: 'bg-emerald-400 shadow-[0_0_12px_rgba(74,222,128,0.7)]',
            text: 'text-emerald-300',
            label: 'Backend online',
            pulse: false,
        },
        offline: {
            dot: 'bg-rose-500 shadow-[0_0_12px_rgba(244,63,94,0.7)]',
            text: 'text-rose-300',
            label: 'Backend offline',
            pulse: true,
        },
        checking: {
            dot: 'bg-slate-400',
            text: 'text-slate-400',
            label: 'Checking backend',
            pulse: true,
        },
    }[status];

    return (
        <div
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"
            title={config.label}
            aria-live="polite"
        >
            <span className={`h-2 w-2 rounded-full ${config.dot} ${config.pulse ? 'animate-pulse' : ''}`} />
            <span className={config.text}>{config.label}</span>
        </div>
    );
}