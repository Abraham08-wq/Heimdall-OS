'use client';

// Sensor agent page — the client the MONITORED DEVICE (e.g. your phone) runs.
// Open this on the device at http://<host>:3005/sensor, paste a one-time
// enrollment token, and it enrolls then heartbeats every 60s.
//
// IMPORTANT: this page does NOT use the dashboard's apiRequest/JWT client.
// A sensor agent authenticates with its own per-device secret (issued once at
// enrollment), sent as `Authorization: Bearer <agent_secret>` — never a human
// JWT. All calls use relative /api/v1 paths so they go same-origin through the
// Next.js proxy (no CORS). See backend/app/routers/sensor_router.py.
//
// Limitation: a browser tab pauses timers when backgrounded or the screen
// locks, so heartbeats stop until it's foregrounded again. Fine for a live
// test; a real always-on agent would be a PWA or native app.

import { useCallback, useEffect, useRef, useState } from 'react';

const LS = {
    deviceId: 'pxy.sensor.deviceId',
    secret: 'pxy.sensor.agentSecret',
} as const;

type AgentStatus = 'idle' | 'enrolling' | 'online' | 'offline' | 'error';

export default function SensorAgentPage() {
    const [token, setToken] = useState('');
    const [name, setName] = useState('');
    const [deviceId, setDeviceId] = useState<string | null>(null);
    const [status, setStatus] = useState<AgentStatus>('idle');
    const [lastBeat, setLastBeat] = useState<string>('—');
    const [logLines, setLogLines] = useState<string[]>([]);
    const timer = useRef<ReturnType<typeof setInterval> | null>(null);

    const log = useCallback((msg: string) => {
        const t = new Date().toLocaleTimeString();
        setLogLines((prev) => [`[${t}] ${msg}`, ...prev].slice(0, 100));
    }, []);

    const heartbeat = useCallback(async () => {
        const id = localStorage.getItem(LS.deviceId);
        const secret = localStorage.getItem(LS.secret);
        if (!id || !secret) return;

        try {
            const res = await fetch(`/api/v1/sensor/${id}/heartbeat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${secret}`,
                },
                body: JSON.stringify({ status: 'online' }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setStatus('offline');
                log(`Heartbeat rejected (${res.status}): ${data.detail ?? 'unknown'}`);
                return;
            }
            setStatus('online');
            setLastBeat(new Date().toLocaleTimeString());
            if (data.command) {
                log(`Command received: ${data.command.action} (${data.command.command_id})`);
                // v1: acknowledge only — a phone browser cannot actually isolate itself.
                await fetch(`/api/v1/sensor/${id}/commands/${data.command.command_id}/result`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${secret}`,
                    },
                    body: JSON.stringify({
                        status: 'completed',
                        result: { note: 'Acknowledged by mobile test agent (no real action taken).' },
                    }),
                });
                log(`Command ${data.command.command_id} acknowledged.`);
            } else {
                log('Heartbeat ok');
            }
        } catch (e) {
            setStatus('offline');
            log(`Network error: ${(e as Error).message}`);
        }
    }, [log]);

    const startLoop = useCallback(() => {
        if (timer.current) clearInterval(timer.current);
        void heartbeat();
        timer.current = setInterval(() => void heartbeat(), 60_000); // backend asks for 60s
    }, [heartbeat]);

    const enroll = useCallback(async () => {
        if (!token.trim()) {
            log('Enrollment token is required.');
            return;
        }
        setStatus('enrolling');
        log('POST /api/v1/sensor/enroll');
        try {
            const res = await fetch('/api/v1/sensor/enroll', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    enrollment_token: token.trim(),
                    hostname: name.trim() || 'My Device',
                    os: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 120) : null,
                    ip: null,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setStatus('error');
                log(`Enroll failed (${res.status}): ${data.detail ?? JSON.stringify(data)}`);
                return;
            }
            localStorage.setItem(LS.deviceId, data.device_id);
            localStorage.setItem(LS.secret, data.agent_secret);
            setDeviceId(data.device_id);
            log(`Enrolled. device_id=${data.device_id}`);
            startLoop();
        } catch (e) {
            setStatus('error');
            log(`Network error during enroll: ${(e as Error).message}`);
        }
    }, [token, name, log, startLoop]);

    const forget = useCallback(() => {
        if (timer.current) clearInterval(timer.current);
        localStorage.removeItem(LS.deviceId);
        localStorage.removeItem(LS.secret);
        setDeviceId(null);
        setStatus('idle');
        setLastBeat('—');
        log('Stopped and cleared local credentials.');
    }, [log]);

    // Resume if this device already enrolled
    useEffect(() => {
        const id = localStorage.getItem(LS.deviceId);
        const secret = localStorage.getItem(LS.secret);
        if (id && secret) {
            setDeviceId(id);
            log('Resuming from saved enrollment.');
            startLoop();
        }
        return () => {
            if (timer.current) clearInterval(timer.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const dotColor =
        status === 'online' ? 'bg-emerald-400'
        : status === 'offline' || status === 'error' ? 'bg-rose-500'
        : status === 'enrolling' ? 'bg-amber-400'
        : 'bg-slate-500';

    const statusText =
        status === 'online' ? 'Online · reporting'
        : status === 'offline' ? 'Offline · cannot reach backend'
        : status === 'enrolling' ? 'Enrolling…'
        : status === 'error' ? 'Error'
        : 'Idle';

    return (
        <div className="mx-auto max-w-md space-y-4 p-4 text-slate-100">
            <div>
                <h1 className="text-lg font-semibold">ProjectXY Sensor Agent</h1>
                <p className="text-xs text-slate-400">Enroll this device, then it reports live status.</p>
            </div>

            {!deviceId ? (
                <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div>
                        <label className="mb-1 block text-xs text-slate-400">Enrollment token (from admin)</label>
                        <input
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            autoCapitalize="off"
                            autoCorrect="off"
                            placeholder="paste the one-time token"
                            className="w-full rounded-lg border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm outline-none focus:border-teal-400/50"
                        />
                    </div>
                    <div>
                        <label className="mb-1 block text-xs text-slate-400">Device name</label>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="My Phone"
                            className="w-full rounded-lg border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm outline-none focus:border-teal-400/50"
                        />
                    </div>
                    <button
                        onClick={() => void enroll()}
                        disabled={status === 'enrolling'}
                        className="w-full rounded-lg bg-teal-400 px-4 py-3 text-sm font-semibold text-teal-950 disabled:opacity-50"
                    >
                        {status === 'enrolling' ? 'Enrolling…' : 'Enroll this device'}
                    </button>
                </div>
            ) : (
                <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
                        <span className="text-sm font-semibold">{statusText}</span>
                    </div>
                    <div>
                        <div className="text-xs text-slate-400">Device ID</div>
                        <div className="break-all font-mono text-xs">{deviceId}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-400">Last heartbeat</div>
                        <div className="font-mono text-xs">{lastBeat}</div>
                    </div>
                    <button
                        onClick={forget}
                        className="w-full rounded-lg border border-white/10 bg-slate-900/60 px-4 py-2.5 text-sm text-slate-300"
                    >
                        Stop &amp; forget this device
                    </button>
                </div>
            )}

            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="mb-2 text-xs text-slate-400">Activity</div>
                <div className="h-40 overflow-y-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-slate-900/60 p-2 font-mono text-[11px] text-slate-400">
                    {logLines.join('\n')}
                </div>
            </div>
        </div>
    );
}