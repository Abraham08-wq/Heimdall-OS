'use client';

// EnrollmentTokenIssuer — the ADMIN/human side. Mints a one-time enrollment
// token to hand to a device being onboarded. Uses the dashboard's api client,
// which attaches the logged-in operator's JWT automatically.
//
// Calls POST /api/v1/devices/enrollment-tokens. The path is passed WITHOUT the
// /api/v1 prefix because api.apiRequest prepends it (see frontend/src/lib/api.ts).

import { useState } from 'react';
import { api } from '@/lib/api';

interface EnrollmentTokenResponse {
  enrollment_token: string;
  expires_at: string;
}

export function EnrollmentTokenIssuer() {
  const [nameHint, setNameHint] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const issue = async () => {
    setLoading(true);
    setError(null);
    setToken(null);
    try {
      const res = await api.apiRequest<EnrollmentTokenResponse>('/devices/enrollment-tokens', {
        method: 'POST',
        body: JSON.stringify({
          deployment_mode: 'endpoint',
          device_name_hint: nameHint.trim() || undefined,
        }),
      });
      setToken(res.enrollment_token);
      setExpiresAt(res.expires_at);
    } catch (e) {
      setError((e as Error).message || 'Failed to issue token');
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be unavailable over plain http; user can select manually
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-sky-900/30 bg-sky-950/10 p-4">
      <div>
        <p className="text-sm font-semibold text-sky-200">Enroll a new device</p>
        <p className="text-[11px] font-mono text-sky-700">
          Issue a one-time token, then open <span className="text-sky-400">/sensor</span> on the device and paste it.
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={nameHint}
          onChange={(e) => setNameHint(e.target.value)}
          placeholder="Device name (optional), e.g. My Phone"
          className="flex-1 rounded-lg border border-sky-900/30 bg-sky-950/20 px-3 py-2 text-sm font-mono text-sky-300 placeholder-sky-900 focus:outline-none focus:border-sky-600/60"
        />
        <button
          onClick={() => void issue()}
          disabled={loading}
          className="rounded-lg border border-sky-700 bg-sky-900/60 px-4 py-2 text-[11px] font-mono font-bold tracking-widest text-sky-200 hover:bg-sky-900 disabled:opacity-50"
        >
          {loading ? 'ISSUING…' : 'ISSUE TOKEN'}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-red-900/50 bg-red-950/20 px-3 py-2 text-[11px] font-mono text-red-400">
          {error}
        </p>
      )}

      {token && (
        <div className="space-y-2 rounded-lg border border-emerald-800/50 bg-emerald-950/10 p-3">
          <p className="text-[9px] font-mono uppercase tracking-widest text-sky-700">
            One-time token · single use{expiresAt ? ` · expires ${new Date(expiresAt).toLocaleString()}` : ''}
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-[#00091A] px-2 py-1.5 font-mono text-xs text-emerald-300">
              {token}
            </code>
            <button
              onClick={() => void copy()}
              className="rounded-lg border border-sky-900/40 bg-sky-950/20 px-3 py-1.5 text-[10px] font-mono tracking-widest text-sky-400 hover:text-sky-200"
            >
              {copied ? 'COPIED' : 'COPY'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}