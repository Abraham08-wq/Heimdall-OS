'use client';
import { useEffect, useState } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import { Activity, AlertTriangle, TrendingUp } from 'lucide-react';
import { apiRequest } from '@/lib/api';

interface SemanticLog {
  id?: string; created_at?: string; entity_id?: string;
  threat_score?: number; action?: string; intent_classification?: string;
  multi_stage_flag?: boolean;
}
interface Stats { blocked_requests?: number; total_requests?: number; avg_threat_score?: number; pii_events?: number; }

const BUCKETS = [
  { label: '0.0 – 0.3',  key: 'safe',     color: 'bg-emerald-600', textColor: 'text-emerald-400', range: [0, 0.3]    },
  { label: '0.3 – 0.6',  key: 'warn',     color: 'bg-yellow-600',  textColor: 'text-yellow-400',  range: [0.3, 0.6]  },
  { label: '0.6 – 0.8',  key: 'high',     color: 'bg-orange-600',  textColor: 'text-orange-400',  range: [0.6, 0.8]  },
  { label: '0.8 – 1.0',  key: 'critical', color: 'bg-red-600',     textColor: 'text-red-400',     range: [0.8, 1.01] },
];

export default function AnomalyMatrix() {
  const [logs, setLogs]   = useState<SemanticLog[]>([]);
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const [l, s] = await Promise.allSettled([
        apiRequest<SemanticLog[] | { items?: SemanticLog[] }>('/ai/feed/merged'),
        apiRequest<Stats>('/stats/'),
      ]);
      if (l.status === 'fulfilled') {
        const raw = l.value;
        setLogs(Array.isArray(raw) ? raw : (raw?.items ?? []));
      }
      if (s.status === 'fulfilled') setStats(s.value ?? {});
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 12000);
    return () => clearInterval(iv);
  }, []);

  // Compute bucket counts
  const bucketCounts = BUCKETS.map(b => ({
    ...b,
    count: logs.filter(l => (l.threat_score ?? 0) >= b.range[0] && (l.threat_score ?? 0) < b.range[1]).length,
  }));
  const maxCount = Math.max(1, ...bucketCounts.map(b => b.count));

  // Entity risk grid
  const entityMap: Record<string, number> = {};
  logs.forEach(l => {
    if (l.entity_id) entityMap[l.entity_id] = Math.max(entityMap[l.entity_id] ?? 0, l.threat_score ?? 0);
  });
  const entities = Object.entries(entityMap).sort(([, a], [, b]) => b - a).slice(0, 24);

  const riskColor = (s: number) =>
    s > 0.7 ? 'bg-red-950 border-red-800 text-red-400'
    : s > 0.3 ? 'bg-yellow-950 border-yellow-800 text-yellow-500'
    : 'bg-emerald-950/30 border-emerald-900/30 text-emerald-600';

  return (
    <TeamShell team="purple" title="Anomaly Matrix" subtitle="Behavioral Analysis — Live TimescaleDB Feed">
      <div className="p-6 space-y-6">
        {/* Threat Score Distribution */}
        <div className="bg-[#0D0018] border border-purple-900/30 rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-purple-900/20">
            <TrendingUp size={12} className="text-purple-600" />
            <span className="text-[11px] font-mono font-bold tracking-widest text-purple-400">THREAT SCORE DISTRIBUTION</span>
            <span className="ml-auto text-[9px] font-mono text-slate-600">{logs.length} samples</span>
          </div>
          <div className="p-6">
            <div className="flex items-end gap-4 h-36">
              {bucketCounts.map(b => (
                <div key={b.key} className="flex-1 flex flex-col items-center gap-2">
                  <span className={`text-xs font-black tabular-nums ${b.textColor}`}>{b.count}</span>
                  <div className="w-full flex items-end" style={{ height: '80px' }}>
                    <div
                      className={`w-full rounded-t transition-all duration-700 ${b.color} opacity-80`}
                      style={{ height: `${Math.max(4, (b.count / maxCount) * 80)}px` }}
                    />
                  </div>
                  <div className="text-center">
                    <span className="text-[8px] font-mono text-slate-500 block">{b.label}</span>
                    <span className="text-[7px] font-black tracking-widest text-slate-600">{b.key.toUpperCase()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Anomalies Feed */}
          <div className="bg-[#0D0018] border border-purple-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-purple-900/20">
              <Activity size={12} className="text-purple-600 animate-pulse" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-purple-400">RECENT ANOMALIES</span>
            </div>
            <div className="divide-y divide-purple-900/20 max-h-72 overflow-y-auto">
              {loading ? (
                <p className="text-center py-6 text-slate-600 text-xs font-mono">Loading feed...</p>
              ) : logs.filter(l => (l.threat_score ?? 0) > 0.1).slice(0, 20).map((l, i) => (
                <div key={l.id ?? i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-purple-950/20">
                  <span className={`text-xs font-black tabular-nums ${
                    (l.threat_score ?? 0) > 0.7 ? 'text-red-400'
                    : (l.threat_score ?? 0) > 0.3 ? 'text-yellow-400'
                    : 'text-emerald-400'
                  }`}>
                    {(l.threat_score ?? 0).toFixed(4)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-mono text-slate-400 truncate">{l.entity_id ?? 'anonymous'}</p>
                    <p className="text-[9px] text-slate-600">{l.intent_classification ?? l.action ?? '—'}</p>
                  </div>
                  {l.multi_stage_flag && (
                    <AlertTriangle size={10} className="text-red-500 flex-shrink-0" />
                  )}
                  <span className="text-[8px] font-mono text-slate-700 flex-shrink-0">
                    {l.created_at ? new Date(l.created_at).toLocaleTimeString() : '—'}
                  </span>
                </div>
              ))}
              {!loading && logs.filter(l => (l.threat_score ?? 0) > 0.1).length === 0 && (
                <p className="text-center py-6 text-slate-600 text-xs font-mono">No anomalies detected.</p>
              )}
            </div>
          </div>

          {/* Entity Risk Grid */}
          <div className="bg-[#0D0018] border border-purple-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-purple-900/20">
              <Activity size={12} className="text-purple-600" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-purple-400">ENTITY RISK GRID</span>
            </div>
            <div className="p-3 grid grid-cols-4 gap-1.5">
              {entities.length === 0 ? (
                <p className="col-span-4 text-center py-6 text-slate-600 text-xs font-mono">No entity data yet</p>
              ) : entities.map(([eid, score]) => (
                <div
                  key={eid}
                  className={`border rounded p-1.5 text-center transition-colors ${riskColor(score)}`}
                  title={eid}
                >
                  <p className="text-[8px] font-mono truncate">{eid.slice(0, 8)}</p>
                  <p className="text-[10px] font-black tabular-nums mt-0.5">{score.toFixed(2)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </TeamShell>
  );
}
