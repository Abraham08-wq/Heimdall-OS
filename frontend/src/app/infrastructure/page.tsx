'use client';

import { useEffect, useState, useCallback } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import {
  Server, Wifi, WifiOff, AlertTriangle, Shield,
  Cpu, Globe, Database, Network, RefreshCw, Filter, Search,
} from 'lucide-react';
import { apiRequest } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

interface Device {
  id: string;
  name?: string;
  hostname?: string;
  ip?: string;
  type?: string;
  status?: string;
  risk_score?: number;
  trust_score?: number;
  last_seen?: string;
  os?: string;
  location?: string;
  compliance_status?: string;
}

type StatusFilter = 'all' | 'online' | 'isolated' | 'offline' | 'degraded';
type TypeFilter = 'all' | 'server' | 'endpoint' | 'gateway' | 'iot' | 'cloud';

// ── Config ─────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string; bg: string }> = {
  online:     { label: 'ONLINE',     color: 'text-emerald-400', dot: 'bg-emerald-500',  bg: 'bg-emerald-950/20 border-emerald-900/30' },
  isolated:   { label: 'ISOLATED',   color: 'text-red-400',     dot: 'bg-red-500 animate-pulse', bg: 'bg-red-950/20 border-red-900/30' },
  offline:    { label: 'OFFLINE',    color: 'text-slate-500',   dot: 'bg-slate-700',    bg: 'bg-slate-900/20 border-slate-800/30' },
  degraded:   { label: 'DEGRADED',   color: 'text-amber-400',   dot: 'bg-amber-500',    bg: 'bg-amber-950/20 border-amber-900/30' },
  quarantine: { label: 'QUARANTINE', color: 'text-orange-400',  dot: 'bg-orange-500 animate-pulse', bg: 'bg-orange-950/20 border-orange-900/30' },
};

const TYPE_ICON: Record<string, React.ReactNode> = {
  server:   <Server size={14} />,
  endpoint: <Cpu size={14} />,
  gateway:  <Globe size={14} />,
  iot:      <Wifi size={14} />,
  cloud:    <Database size={14} />,
  router:   <Network size={14} />,
};

function riskColor(score: number) {
  if (score >= 0.7) return 'text-red-400';
  if (score >= 0.4) return 'text-amber-400';
  return 'text-emerald-400';
}

function riskBar(score: number) {
  const pct = Math.min(100, Math.round((score ?? 0) * 100));
  const color = score >= 0.7 ? 'bg-red-500' : score >= 0.4 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function timeSince(iso?: string) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function InfrastructureGrid() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState('');
  const [statusF, setStatusF] = useState<StatusFilter>('all');
  const [typeF, setTypeF]     = useState<TypeFilter>('all');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<Device[] | { items?: Device[]; devices?: Device[] }>('/devices/');
      const list = Array.isArray(data) ? data : (data?.items ?? data?.devices ?? []);
      setDevices(list);
      setLastRefresh(new Date());
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load device inventory');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, [load]);

  const filtered = devices.filter(d => {
    const q = searchQ.toLowerCase();
    const matchQ = !q || [d.name, d.hostname, d.ip, d.type, d.location]
      .some(v => (v ?? '').toLowerCase().includes(q));
    const matchS = statusF === 'all' || (d.status ?? 'online').toLowerCase() === statusF;
    const matchT = typeF === 'all' || (d.type ?? '').toLowerCase().includes(typeF);
    return matchQ && matchS && matchT;
  });

  // Summary counts
  const counts = {
    total:    devices.length,
    online:   devices.filter(d => !d.status || d.status === 'online').length,
    isolated: devices.filter(d => d.status === 'isolated' || d.status === 'quarantine').length,
    degraded: devices.filter(d => d.status === 'degraded').length,
    offline:  devices.filter(d => d.status === 'offline').length,
  };

  return (
    <TeamShell team="platform" title="Infrastructure Grid" subtitle="Asset Topology — Device Registry & Health">
      <div className="p-6 space-y-5">

        {/* Summary cards */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {[
            { label: 'Total Assets', value: counts.total,    color: 'text-slate-300', border: 'border-slate-800' },
            { label: 'Online',       value: counts.online,   color: 'text-emerald-400', border: 'border-emerald-900/30' },
            { label: 'Isolated',     value: counts.isolated, color: 'text-red-400',    border: 'border-red-900/30' },
            { label: 'Degraded',     value: counts.degraded, color: 'text-amber-400',  border: 'border-amber-900/30' },
            { label: 'Offline',      value: counts.offline,  color: 'text-slate-500',  border: 'border-slate-800' },
          ].map(c => (
            <div key={c.label} className={`bg-slate-900/30 border ${c.border} rounded-xl p-4`}>
              <p className="text-[9px] text-slate-600 tracking-widest mb-1">{c.label}</p>
              <p className={`text-2xl font-black tabular-nums ${c.color}`}>{c.value}</p>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="flex items-center gap-2 flex-1 bg-slate-900/40 border border-slate-800/60 rounded-lg px-3 py-2">
            <Search size={13} className="text-slate-600 shrink-0" />
            <input
              type="text"
              value={searchQ}
              onChange={e => setSearchQ(e.target.value)}
              placeholder="Search by name, hostname, IP, location…"
              className="flex-1 bg-transparent text-sm text-slate-300 placeholder:text-slate-700 outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter size={12} className="text-slate-600" />
            {(['all', 'online', 'isolated', 'offline', 'degraded'] as StatusFilter[]).map(s => (
              <button
                key={s}
                onClick={() => setStatusF(s)}
                className={`text-[9px] font-black tracking-widest px-2.5 py-1.5 rounded border transition-all ${
                  statusF === s
                    ? 'bg-slate-700 border-slate-600 text-white'
                    : 'border-slate-800 text-slate-600 hover:text-slate-400'
                }`}
              >
                {s.toUpperCase()}
              </button>
            ))}
          </div>

          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-[9px] tracking-widest text-slate-500 hover:text-slate-300 border border-slate-800 rounded-lg px-3 py-2 transition-all disabled:opacity-40"
          >
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
            REFRESH
          </button>
        </div>

        {/* Error state */}
        {error && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-950/20 border border-red-900/30 rounded-lg p-3">
            <AlertTriangle size={13} />
            {error}
          </div>
        )}

        {/* Device grid */}
        {!error && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {loading && devices.length === 0 ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-slate-900/30 border border-slate-800/40 rounded-xl p-4 animate-pulse">
                  <div className="h-3 bg-slate-800 rounded w-2/3 mb-3" />
                  <div className="h-2 bg-slate-800 rounded w-1/2 mb-2" />
                  <div className="h-1 bg-slate-800 rounded w-full" />
                </div>
              ))
            ) : filtered.length === 0 ? (
              <div className="col-span-full py-12 text-center text-slate-700 text-sm tracking-widest">
                NO DEVICES MATCH YOUR FILTERS
              </div>
            ) : (
              filtered.map(d => {
                const statusKey = (d.status ?? 'online').toLowerCase();
                const cfg = STATUS_CONFIG[statusKey] ?? STATUS_CONFIG.online;
                const typeKey = (d.type ?? 'server').toLowerCase();
                const risk = d.risk_score ?? 0;

                return (
                  <div
                    key={d.id}
                    className={`border ${cfg.bg} rounded-xl p-4 space-y-3 hover:border-opacity-60 transition-all cursor-default group`}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className={`shrink-0 ${cfg.color}`}>
                          {TYPE_ICON[typeKey] ?? <Server size={14} />}
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-white truncate">
                            {d.name ?? d.hostname ?? 'Unknown Device'}
                          </p>
                          <p className="text-[9px] text-slate-600 font-mono truncate">
                            {d.ip ?? '—'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                        <span className={`text-[8px] font-black tracking-widest ${cfg.color}`}>
                          {cfg.label}
                        </span>
                      </div>
                    </div>

                    {/* Meta */}
                    <div className="grid grid-cols-3 gap-2 text-[10px]">
                      <div>
                        <p className="text-slate-700 mb-0.5">TYPE</p>
                        <p className="text-slate-400 capitalize">{d.type ?? 'server'}</p>
                      </div>
                      <div>
                        <p className="text-slate-700 mb-0.5">OS</p>
                        <p className="text-slate-400 truncate">{d.os ?? '—'}</p>
                      </div>
                      <div>
                        <p className="text-slate-700 mb-0.5">LAST SEEN</p>
                        <p className="text-slate-400">{timeSince(d.last_seen)}</p>
                      </div>
                    </div>

                    {/* Risk bar */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-[9px]">
                        <span className="text-slate-700">RISK SCORE</span>
                        <span className={`font-black tabular-nums ${riskColor(risk)}`}>
                          {(risk * 100).toFixed(0)}%
                        </span>
                      </div>
                      {riskBar(risk)}
                    </div>

                    {/* Hostname + compliance badge */}
                    <div className="flex items-center justify-between text-[9px]">
                      <span className="text-slate-700 font-mono truncate">{d.hostname ?? '—'}</span>
                      {d.compliance_status && (
                        <span className={`px-1.5 py-0.5 rounded border text-[8px] font-black tracking-widest ${
                          d.compliance_status === 'compliant'
                            ? 'text-emerald-400 border-emerald-800 bg-emerald-950/30'
                            : 'text-amber-400 border-amber-800 bg-amber-950/20'
                        }`}>
                          {d.compliance_status.toUpperCase()}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-[9px] text-slate-800 tracking-widest pt-2">
          <span>PROJECTXY INFRASTRUCTURE GRID — ASSET TOPOLOGY</span>
          <span>Last refresh: {lastRefresh.toLocaleTimeString()} · {filtered.length}/{counts.total} shown</span>
        </div>
      </div>
    </TeamShell>
  );
}
