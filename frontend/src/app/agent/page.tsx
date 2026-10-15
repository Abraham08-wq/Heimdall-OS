'use client';

// Standalone sensor agent (PWA) — the REMOVABLE test client a consenting
// device runs. It is NOT part of the dashboard: it requires no operator login,
// shows no dashboard chrome, and can only do the three agent calls (enroll,
// heartbeat, report command result). The device owner installed it knowingly
// and can uninstall it at any time.
//
// Served at /agent. DashboardShell is bypassed for this path (see the
// isAuthRoute edit), so this renders bare.
//
// All calls are relative /api/v1 paths → same-origin through the Next.js proxy,
// so no CORS. The agent authenticates with its own per-device secret, never a
// human JWT.

import { useCallback, useEffect, useRef, useState } from 'react';

const LS = {
  deviceId: 'pxy.agent.deviceId',
  secret: 'pxy.agent.agentSecret',
  name: 'pxy.agent.deviceName',
} as const;

type AgentStatus = 'idle' | 'enrolling' | 'online' | 'offline' | 'error';

export default function AgentPage() {
  const [token, setToken] = useState('');
  const [name, setName] = useState('');
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [lastBeat, setLastBeat] = useState('—');
  const [log, setLog] = useState<string[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const addLog = useCallback((m: string) => {
    const t = new Date().toLocaleTimeString();
    setLog((p) => [`[${t}] ${m}`, ...p].slice(0, 80));
  }, []);

  const heartbeat = useCallback(async () => {
    const id = localStorage.getItem(LS.deviceId);
    const secret = localStorage.getItem(LS.secret);
    if (!id || !secret) return;
    try {
      const res = await fetch(`/api/v1/sensor/${id}/heartbeat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${secret}` },
        body: JSON.stringify({ status: 'online' }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setStatus('offline');
        addLog(`Heartbeat rejected (${res.status})`);
        return;
      }
      setStatus('online');
      setLastBeat(new Date().toLocaleTimeString());
      if (data.command) {
        addLog(`Command: ${data.command.action}`);
        await fetch(`/api/v1/sensor/${id}/commands/${data.command.command_id}/result`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${secret}` },
          body: JSON.stringify({
            status: 'completed',
            result: { note: 'Acknowledged by removable test agent (no action taken).' },
          }),
        });
      }
    } catch (e) {
      setStatus('offline');
      addLog(`Network error: ${(e as Error).message}`);
    }
  }, [addLog]);

  const startLoop = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    void heartbeat();
    timer.current = setInterval(() => void heartbeat(), 60_000);
  }, [heartbeat]);

  const enroll = useCallback(async () => {
    if (!token.trim()) { addLog('Enrollment token required.'); return; }
    setStatus('enrolling');
    addLog('Enrolling…');
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
        addLog(`Enroll failed (${res.status}): ${data.detail ?? 'error'}`);
        return;
      }
      localStorage.setItem(LS.deviceId, data.device_id);
      localStorage.setItem(LS.secret, data.agent_secret);
      localStorage.setItem(LS.name, name.trim() || 'My Device');
      setDeviceId(data.device_id);
      addLog('Enrolled successfully.');
      startLoop();
    } catch (e) {
      setStatus('error');
      addLog(`Network error: ${(e as Error).message}`);
    }
  }, [token, name, addLog, startLoop]);

  const unenroll = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    localStorage.removeItem(LS.deviceId);
    localStorage.removeItem(LS.secret);
    localStorage.removeItem(LS.name);
    setDeviceId(null);
    setStatus('idle');
    setLastBeat('—');
    addLog('Stopped. This device is no longer reporting.');
  }, [addLog]);

  // Register the service worker (keeps a background heartbeat more reliably
  // than a plain tab) and resume if already enrolled.
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/agent-sw.js').catch(() => {});
    }
    const id = localStorage.getItem(LS.deviceId);
    const secret = localStorage.getItem(LS.secret);
    const savedName = localStorage.getItem(LS.name);
    if (savedName) setName(savedName);
    if (id && secret) {
      setDeviceId(id);
      addLog('Resuming.');
      startLoop();
    }
    // Heartbeat immediately when the app returns to foreground
    const onVisible = () => { if (document.visibilityState === 'visible') void heartbeat(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      if (timer.current) clearInterval(timer.current);
      document.removeEventListener('visibilitychange', onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dot =
    status === 'online' ? '#34d399'
    : status === 'offline' || status === 'error' ? '#f43f5e'
    : status === 'enrolling' ? '#f59e0b'
    : '#64748b';

  const label =
    status === 'online' ? 'Protected · reporting'
    : status === 'offline' ? 'Offline · will retry'
    : status === 'enrolling' ? 'Enrolling…'
    : status === 'error' ? 'Enrollment error'
    : 'Not enrolled';

  return (
    <div style={{
      minHeight: '100vh', background: '#0b0f19', color: '#e2e8f0',
      fontFamily: 'ui-sans-serif, system-ui, sans-serif',
      padding: 'max(20px, env(safe-area-inset-top)) 20px calc(20px + env(safe-area-inset-bottom))',
    }}>
      <div style={{ maxWidth: 440, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg,#2dd4bf,#6366f1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 800, color: '#042f2a', fontSize: 13,
          }}>XY</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>ProjectXY Protection</div>
            <div style={{ fontSize: 11, color: '#7b8aa5' }}>Device security agent</div>
          </div>
        </div>

        {!deviceId ? (
          <div style={{ background: '#121829', border: '1px solid #1f2a40', borderRadius: 14, padding: 16, marginTop: 16 }}>
            <p style={{ fontSize: 13, color: '#9fb0c9', marginTop: 0 }}>
              Enter the enrollment code provided by your security team to connect this device.
            </p>
            <label style={{ fontSize: 12, color: '#7b8aa5', display: 'block', margin: '12px 0 4px' }}>Enrollment code</label>
            <input value={token} onChange={(e) => setToken(e.target.value)} autoCapitalize="off" autoCorrect="off"
              placeholder="paste code" style={inputStyle} />
            <label style={{ fontSize: 12, color: '#7b8aa5', display: 'block', margin: '12px 0 4px' }}>Device name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Jane's Phone" style={inputStyle} />
            <button onClick={() => void enroll()} disabled={status === 'enrolling'} style={primaryBtn}>
              {status === 'enrolling' ? 'Connecting…' : 'Connect device'}
            </button>
          </div>
        ) : (
          <div style={{ background: '#121829', border: '1px solid #1f2a40', borderRadius: 14, padding: 16, marginTop: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 11, height: 11, borderRadius: '50%', background: dot }} />
              <span style={{ fontWeight: 600 }}>{label}</span>
            </div>
            <div style={{ marginTop: 12, fontSize: 12, color: '#7b8aa5' }}>Last check-in</div>
            <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 13 }}>{lastBeat}</div>
            <p style={{ fontSize: 12, color: '#7b8aa5', marginTop: 14 }}>
              Keep this app installed to stay protected. You can remove it at any time.
            </p>
            <button onClick={unenroll} style={secondaryBtn}>Disconnect this device</button>
          </div>
        )}

        <div style={{ background: '#121829', border: '1px solid #1f2a40', borderRadius: 14, padding: 16, marginTop: 14 }}>
          <div style={{ fontSize: 12, color: '#7b8aa5', marginBottom: 8 }}>Activity</div>
          <div style={{
            height: 130, overflowY: 'auto', whiteSpace: 'pre-wrap',
            background: '#0b0f19', border: '1px solid #1f2a40', borderRadius: 10, padding: 10,
            fontFamily: 'ui-monospace, monospace', fontSize: 11, color: '#7b8aa5',
          }}>{log.join('\n')}</div>
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', background: '#0b0f19',
  border: '1px solid #1f2a40', borderRadius: 10, color: '#e2e8f0',
  padding: '11px 12px', fontSize: 15,
};
const primaryBtn: React.CSSProperties = {
  width: '100%', border: 'none', borderRadius: 10, padding: 13, fontSize: 15,
  fontWeight: 600, marginTop: 16, background: '#2dd4bf', color: '#042f2a', cursor: 'pointer',
};
const secondaryBtn: React.CSSProperties = {
  width: '100%', borderRadius: 10, padding: 11, fontSize: 14, marginTop: 14,
  background: 'transparent', border: '1px solid #1f2a40', color: '#9fb0c9', cursor: 'pointer',
};