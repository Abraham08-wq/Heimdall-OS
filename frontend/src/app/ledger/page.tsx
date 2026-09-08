'use client';
import { useEffect, useState } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import { KeyRound, CheckCircle, XCircle, Hash, RefreshCw, Shield } from 'lucide-react';
import { apiRequest } from '@/lib/api';

interface AuditLog {
  id?: string; timestamp?: string; actor_id?: string; action?: string;
  resource_type?: string; resource_id?: string; hash?: string;
  previous_hash?: string; metadata?: Record<string, any>;
}

function truncHash(h?: string) {
  if (!h) return '—';
  return h.length > 16 ? `${h.slice(0, 8)}…${h.slice(-8)}` : h;
}

export default function ImmutableLedger() {
  const [logs, setLogs]         = useState<AuditLog[]>([]);
  const [loading, setLoading]   = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{ valid?: boolean; message?: string } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await apiRequest<AuditLog[] | { items?: AuditLog[]; logs?: AuditLog[] }>(
        '/audit/logs?skip=0&limit=50'
      );
      setLogs(Array.isArray(res) ? res : (res?.items ?? res?.logs ?? []));
    } finally {
      setLoading(false);
    }
  };

  const verify = async () => {
    setVerifying(true); setVerifyResult(null);
    try {
      const res = await apiRequest<{ valid?: boolean; message?: string }>('/audit/verify', { method: 'POST' });
      setVerifyResult(res);
    } catch (e: any) {
      setVerifyResult({ valid: false, message: e?.message ?? 'Verification failed' });
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <TeamShell team="platform" title="Immutable Ledger" subtitle="WORM Audit Trail — CBK / GDPR / HIPAA Compliant">
      <div className="p-6 space-y-6">
        {/* Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={verify}
            disabled={verifying}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-mono text-xs font-bold tracking-wider rounded border border-slate-700 transition-colors"
          >
            <Shield size={12} />
            {verifying ? 'VERIFYING...' : 'VERIFY CHAIN INTEGRITY'}
          </button>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 bg-slate-900 hover:bg-slate-800 text-slate-400 font-mono text-xs rounded border border-slate-800 transition-colors"
          >
            <RefreshCw size={11} />
            REFRESH
          </button>
          {verifyResult && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded border text-xs font-mono ${
              verifyResult.valid
                ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                : 'bg-red-950/50 border-red-800 text-red-400'
            }`}>
              {verifyResult.valid ? <CheckCircle size={12} /> : <XCircle size={12} />}
              {verifyResult.message ?? (verifyResult.valid ? 'Chain valid' : 'Chain compromised')}
            </div>
          )}
        </div>

        {/* Audit Table */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
            <Hash size={12} className="text-slate-500" />
            <span className="text-[11px] font-mono font-bold tracking-widest text-slate-400">HASH-CHAINED AUDIT TRAIL</span>
            <span className="ml-auto text-[9px] font-mono text-slate-600">{logs.length} records</span>
          </div>
          {loading ? (
            <div className="py-12 text-center text-slate-600 font-mono text-sm">Loading audit records...</div>
          ) : logs.length === 0 ? (
            <div className="py-12 text-center">
              <KeyRound size={20} className="text-slate-700 mx-auto mb-2" />
              <p className="text-slate-600 text-sm font-mono">No audit records yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="border-b border-slate-800">
                    {['TIMESTAMP', 'ACTOR', 'ACTION', 'RESOURCE', 'HASH', 'PREV HASH'].map(h => (
                      <th key={h} className="px-4 py-2.5 text-left text-[8px] font-black tracking-widest text-slate-600">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {logs.map((log, i) => (
                    <tr key={log.id ?? i} className="hover:bg-slate-800/20 transition-colors">
                      <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">
                        {log.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400 font-mono max-w-[80px] truncate">
                        {(log.actor_id ?? '—').slice(0, 8)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-slate-300 font-bold tracking-wide">{log.action ?? '—'}</span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-500">{log.resource_type ?? '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className="text-emerald-600 font-mono">{truncHash(log.hash)}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className="text-slate-700 font-mono">{truncHash(log.previous_hash)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </TeamShell>
  );
}
