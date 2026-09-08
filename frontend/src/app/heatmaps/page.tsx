'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import TeamShell from '@/components/Layout/TeamShell';
import { api } from '@/lib/api';
import { Entity } from '@/lib/api';
import {
  TrendingUp, AlertTriangle, Activity, Clock,
  RefreshCw, Flame, BarChart2, Layers
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
type TimeRange = '1h' | '6h' | '24h' | '7d';

interface HeatEntity extends Entity {
  last_activity?: string;
}

// ─── Color Scale ──────────────────────────────────────────────────────────────
function riskToHSL(score: number): string {
  // Green (120) → Yellow (60) → Orange (30) → Red (0)
  const hue = Math.max(0, 120 - score * 1.2);
  const sat = 80 + score * 0.2;
  const light = 30 + (1 - score / 100) * 10;
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

function riskLabel(score: number): string {
  if (score >= 80) return 'CRITICAL';
  if (score >= 60) return 'HIGH';
  if (score >= 40) return 'MEDIUM';
  if (score >= 20) return 'LOW';
  return 'MINIMAL';
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────
interface TooltipState {
  entity: HeatEntity;
  x: number;
  y: number;
}

function Tooltip({ tooltip }: { tooltip: TooltipState }) {
  const { entity, x, y } = tooltip;
  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{ left: x + 14, top: y - 10 }}
    >
      <div className="rounded-xl border border-indigo-700/50 bg-[#0a0a1f] shadow-2xl p-3 min-w-[200px]"
        style={{ boxShadow: '0 0 20px rgba(99,102,241,0.15)' }}>
        <p className="text-xs font-semibold text-indigo-200 mb-1.5 truncate max-w-[180px]">{entity.canonical_name}</p>
        <div className="space-y-1 text-[10px] font-mono">
          <div className="flex justify-between gap-4">
            <span className="text-indigo-700">Type</span>
            <span className="text-indigo-400">{entity.type}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-indigo-700">Risk Score</span>
            <span className="font-black" style={{ color: riskToHSL(entity.risk_score) }}>{entity.risk_score}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-indigo-700">Level</span>
            <span className="text-indigo-300">{riskLabel(entity.risk_score)}</span>
          </div>
          {entity.last_activity && (
            <div className="flex justify-between gap-4">
              <span className="text-indigo-700">Last Activity</span>
              <span className="text-indigo-500 truncate max-w-[90px]">{entity.last_activity}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Color Legend ─────────────────────────────────────────────────────────────
function ColorLegend() {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] font-mono text-indigo-800">0</span>
      <div className="h-2.5 w-32 rounded-full overflow-hidden" style={{
        background: 'linear-gradient(to right, hsl(120,80%,30%), hsl(60,85%,32%), hsl(30,90%,30%), hsl(0,85%,30%)'
      }} />
      <span className="text-[9px] font-mono text-indigo-800">100</span>
      <div className="flex items-center gap-3 ml-4">
        {[['MINIMAL','hsl(120,80%,30%)'],['LOW','hsl(80,80%,30%)'],['MEDIUM','hsl(60,85%,32%)'],['HIGH','hsl(25,90%,30%)'],['CRITICAL','hsl(0,85%,30%)']].map(([label, color]) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm" style={{ background: color }} />
            <span className="text-[9px] font-mono text-indigo-800">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon, sub }: { label: string; value: string | number; icon: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded-xl border border-indigo-900/30 bg-gradient-to-br from-indigo-950/30 to-[#030307] p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[9px] font-mono text-indigo-700 tracking-widest uppercase">{label}</p>
        <div className="text-indigo-600">{icon}</div>
      </div>
      <p className="text-2xl font-black text-indigo-100 tabular-nums">{value}</p>
      {sub && <p className="text-[10px] font-mono text-indigo-800 mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function HeatmapsPage() {
  const [entities, setEntities] = useState<HeatEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchEntities = useCallback(async () => {
    try {
      setRefreshing(true);
      const data = await api.apiRequest<HeatEntity[]>('/entities/');
      setEntities(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setEntities([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchEntities(); }, [fetchEntities]);

  // Fill to 100 cells for the 10×10 grid
  const gridEntities = useMemo(() => {
    const base = entities.slice(0, 100);
    // Pad with empty cells if fewer than 100 entities
    const empties: HeatEntity[] = Array.from({ length: Math.max(0, 100 - base.length) }, (_, i) => ({
      id: `__empty_${i}`,
      canonical_name: '',
      type: '',
      risk_score: 0,
      attributes: [],
    }));
    return [...base, ...empties];
  }, [entities]);

  const criticalEntities = useMemo(() => entities.filter(e => e.risk_score >= 80), [entities]);
  const avgRisk = useMemo(() => entities.length
    ? Math.round(entities.reduce((s, e) => s + e.risk_score, 0) / entities.length)
    : 0, [entities]);
  const highest = useMemo(() => entities.length
    ? entities.reduce((a, b) => a.risk_score > b.risk_score ? a : b)
    : null, [entities]);

  const TIME_RANGES: TimeRange[] = ['1h', '6h', '24h', '7d'];

  return (
    <TeamShell
      team="platform"
      title="RISK HEATMAP — ENTITY TELEMETRY SURFACE"
      subtitle="Real-time entity risk visualization — 10×10 grid, color-coded by risk score (0–100)"
    >
      <div className="p-6 space-y-6">
        {/* Stats + Controls Row */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="grid grid-cols-3 gap-3 flex-1">
            <StatCard
              label="Highest Risk Entity"
              value={highest?.risk_score ?? '—'}
              icon={<Flame size={15} />}
              sub={highest?.canonical_name ?? 'N/A'}
            />
            <StatCard
              label="Average Risk Score"
              value={avgRisk || '—'}
              icon={<BarChart2 size={15} />}
              sub={`${entities.length} entities`}
            />
            <StatCard
              label="Critical Entities"
              value={criticalEntities.length}
              icon={<AlertTriangle size={15} />}
              sub={`Score ≥ 80`}
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Clock size={13} className="text-indigo-700" />
            {TIME_RANGES.map(t => (
              <button
                key={t}
                onClick={() => { setTimeRange(t); fetchEntities(); }}
                className={`text-[10px] font-mono px-3 py-1.5 rounded border tracking-widest transition-all ${timeRange === t ? 'bg-indigo-900/60 text-indigo-300 border-indigo-700' : 'text-indigo-800 border-indigo-900/30 hover:border-indigo-700/40'}`}
              >
                {t}
              </button>
            ))}
            <button
              onClick={fetchEntities}
              disabled={refreshing}
              className="ml-1 text-indigo-700 hover:text-indigo-400 transition-colors"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
            <AlertTriangle size={14} className="text-red-400 shrink-0" />
            <p className="text-xs font-mono text-red-400">{error} — showing empty grid</p>
          </div>
        )}

        {/* Heatmap Grid */}
        <div className="rounded-xl border border-indigo-900/30 bg-[#030307] p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Layers size={13} className="text-indigo-600" />
              <span className="text-[10px] font-mono text-indigo-700 tracking-widest uppercase">
                Entity Risk Grid — {entities.length} entities
              </span>
            </div>
            <ColorLegend />
          </div>

          {loading ? (
            <div className="grid gap-1.5" style={{ gridTemplateColumns: 'repeat(10, minmax(0, 1fr))' }}>
              {Array.from({ length: 100 }).map((_, i) => (
                <div key={i} className="rounded aspect-square bg-indigo-950/40 animate-pulse" style={{ animationDelay: `${(i % 20) * 30}ms` }} />
              ))}
            </div>
          ) : (
            <div
              className="grid gap-1.5"
              style={{ gridTemplateColumns: 'repeat(10, minmax(0, 1fr))' }}
            >
              {gridEntities.map((entity, i) => {
                const isEmpty = entity.id.startsWith('__empty_');
                return (
                  <div
                    key={entity.id}
                    className={`rounded aspect-square relative transition-transform duration-150 ${isEmpty ? 'bg-indigo-950/10' : 'cursor-pointer hover:scale-110 hover:z-10'}`}
                    style={isEmpty ? {} : {
                      background: riskToHSL(entity.risk_score),
                      boxShadow: entity.risk_score >= 80 ? `0 0 8px ${riskToHSL(entity.risk_score)}80` : undefined,
                    }}
                    onMouseEnter={e => {
                      if (!isEmpty) {
                        const rect = (e.target as HTMLElement).getBoundingClientRect();
                        setTooltip({ entity, x: rect.right, y: rect.top });
                      }
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  >
                    {!isEmpty && entity.risk_score >= 80 && (
                      <div className="absolute inset-0 rounded animate-pulse opacity-30" style={{ background: riskToHSL(entity.risk_score) }} />
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Critical Entities List */}
        {criticalEntities.length > 0 && (
          <div className="rounded-xl border border-red-900/30 bg-[#030307] overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-red-900/20">
              <Flame size={13} className="text-red-500" />
              <span className="text-[10px] font-mono text-red-700 tracking-widest uppercase">
                Critical Entities ({criticalEntities.length})
              </span>
            </div>
            <div className="divide-y divide-indigo-950/30 max-h-52 overflow-y-auto">
              {criticalEntities.map(e => (
                <div key={e.id} className="flex items-center justify-between px-5 py-2.5 hover:bg-indigo-950/10 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: riskToHSL(e.risk_score) }} />
                    <span className="text-xs font-mono text-indigo-300">{e.canonical_name || e.id}</span>
                    <span className="text-[9px] text-indigo-700 border border-indigo-900/40 px-1.5 py-0.5 rounded">{e.type}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {e.last_activity && (
                      <span className="text-[9px] font-mono text-indigo-800 flex items-center gap-1">
                        <Activity size={9} />{e.last_activity}
                      </span>
                    )}
                    <span className="font-black text-sm tabular-nums" style={{ color: riskToHSL(e.risk_score) }}>
                      {e.risk_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state for zero entities */}
        {!loading && entities.length === 0 && !error && (
          <div className="rounded-xl border border-indigo-900/20 bg-[#030307] py-16 flex flex-col items-center gap-3">
            <TrendingUp size={32} className="text-indigo-900" />
            <p className="text-indigo-800 text-[11px] font-mono tracking-widest">NO ENTITY TELEMETRY AVAILABLE</p>
          </div>
        )}
      </div>

      {/* Tooltip */}
      {tooltip && <Tooltip tooltip={tooltip} />}
    </TeamShell>
  );
}
