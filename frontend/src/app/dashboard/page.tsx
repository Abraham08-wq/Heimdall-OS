'use client';

// Unified Dashboard — replaces both the old Situation Room and Infrastructure
// Grid. Keeps only the panels wired to real backend data:
//   • 4 live stat cards      → api.getStats()        (/stats/)
//   • live operations feed   → api.getTacticalFeed() (/ai/feed/merged)
//   • device inventory       → <DeviceRegistry/>     (/devices/)
// Decorative panels (GodsEye, GlobalOpsMap, CommandCenter tabs, fake terminal)
// were removed. Accent colour: amber.

import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldAlert, ShieldCheck, Siren, Activity, RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import { DeviceRegistry } from '@/components/devices/DeviceRegistry';

interface Stats {
  alerts_today?: number;
  blocked_threats?: number;
  critical_alerts?: number;
  system_health?: number;
}

interface FeedItem {
  id?: string;
  title?: string;
  message?: string;
  severity?: string;
  source?: string;
  timestamp?: string;
  ts?: string;
}

const SEV_STYLE: Record<string, string> = {
  CRITICAL: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
  HIGH: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  MEDIUM: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  LOW: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  INFO: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
};

function timeAgo(iso?: string) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return '';
  if (diff < 60_000) return `${Math.max(1, Math.floor(diff / 1000))}s`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return `${Math.floor(diff / 86_400_000)}d`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({});
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [s, f] = await Promise.all([
        api.getStats().catch(() => ({})),
        api.getTacticalFeed().catch(() => []),
      ]);
      setStats(s || {});
      setFeed(Array.isArray(f) ? f.slice(0, 30) : []);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, [load]);

  const health = stats.system_health ?? 100;

  const cards = [
    {
      label: 'Threats Detected',
      value: stats.alerts_today ?? 0,
      icon: <ShieldAlert size={18} />,
      tint: 'text-rose-400',
      ring: 'from-rose-500/15 to-transparent border-rose-500/20',
    },
    {
      label: 'Threats Blocked',
      value: stats.blocked_threats ?? 0,
      icon: <ShieldCheck size={18} />,
      tint: 'text-emerald-400',
      ring: 'from-emerald-500/15 to-transparent border-emerald-500/20',
    },
    {
      label: 'Critical Alerts',
      value: stats.critical_alerts ?? 0,
      icon: <Siren size={18} />,
      tint: 'text-orange-400',
      ring: 'from-orange-500/15 to-transparent border-orange-500/20',
    },
    {
      label: 'System Health',
      value: `${health}%`,
      icon: <Activity size={18} />,
      tint: health > 85 ? 'text-amber-400' : 'text-rose-400',
      ring: 'from-amber-500/15 to-transparent border-amber-500/20',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">Operations</p>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-slate-400">Live posture, threat feed, and managed device inventory</p>
        </div>
        <button
          onClick={load}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-300 hover:bg-amber-500/20 disabled:opacity-50 transition-all"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c, i) => (
          <motion.div
            key={c.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className={`rounded-2xl border bg-gradient-to-br p-5 ${c.ring}`}
          >
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{c.label}</p>
              <span className={c.tint}>{c.icon}</span>
            </div>
            <p className={`mt-3 text-4xl font-black tabular-nums ${c.tint}`}>
              {loading ? '—' : c.value}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Feed + Devices */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Live feed */}
        <div className="xl:col-span-1 rounded-2xl border border-white/10 bg-white/5 overflow-hidden flex flex-col">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
            <span className="h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.7)] animate-pulse" />
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Live Operations Feed</p>
          </div>
          <div className="flex-1 overflow-y-auto max-h-[520px] p-3 space-y-2">
            {loading ? (
              <p className="text-center text-xs text-slate-600 py-8">Loading feed…</p>
            ) : feed.length === 0 ? (
              <div className="py-12 text-center">
                <Activity size={28} className="mx-auto mb-2 text-slate-700" />
                <p className="text-xs text-slate-600">No events yet. Live alerts appear here.</p>
              </div>
            ) : (
              feed.map((ev, i) => {
                const sev = (ev.severity || 'INFO').toUpperCase();
                const cls = SEV_STYLE[sev] ?? SEV_STYLE.INFO;
                return (
                  <div key={ev.id ?? i} className={`rounded-xl border px-3 py-2.5 ${cls}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[9px] font-black tracking-widest uppercase">{sev}</span>
                      <span className="text-[9px] text-slate-500 font-mono">{timeAgo(ev.timestamp ?? ev.ts)}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-200 leading-snug">
                      {ev.title || ev.message || 'Event'}
                    </p>
                    {ev.source && <p className="mt-0.5 text-[10px] text-slate-500 font-mono">{ev.source}</p>}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Device inventory */}
        <div className="xl:col-span-2 rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(74,222,128,0.7)]" />
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Managed Devices</p>
          </div>
          {/* DeviceRegistry owns its own relative/scroll container */}
          <div className="relative" style={{ minHeight: 420 }}>
            <DeviceRegistry />
          </div>
        </div>
      </div>
    </div>
  );
}
