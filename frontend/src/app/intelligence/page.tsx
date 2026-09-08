'use client';

/**
 * Global Threat Intelligence — OSINT Fusion
 * ==========================================
 * Wires to real backend endpoints:
 *  - /api/v1/intel/radar/snapshot   (APT + IOC feed)
 *  - /api/v1/intel/adversarial/landscape
 *  - /api/v1/analysis/graph/full    (entity graph)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Globe, Shield, AlertTriangle, Eye, Radio, Crosshair,
  TrendingUp, Activity, ChevronRight, Zap, RefreshCw, Wifi
} from 'lucide-react';
import { clsx } from 'clsx';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ThreatFeed {
  id: string;
  ts: string;
  ip: string;
  country?: string;
  flag?: string;
  type: string;
  confidence: number;
  actor?: string;
  mitre?: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
}

interface ThreatActor {
  id: string;
  name: string;
  nation?: string;
  flag?: string;
  active: boolean;
  campaigns?: number;
  targets?: string[];
  tools?: string[];
  color: string;
  lastSeen?: string;
  ttps?: string[];
}

interface GraphNode {
  id: string;
  canonical_name: string;
  type: string;
  risk_score: number;
}

// ── Severity styling ───────────────────────────────────────────────────────────

const SEV_CFG: Record<string, string> = {
  CRITICAL: 'text-rose-400 bg-rose-950/60 border-rose-700',
  HIGH:     'text-orange-400 bg-orange-950/50 border-orange-700',
  MEDIUM:   'text-amber-400 bg-amber-950/40 border-amber-700',
  LOW:      'text-slate-400 bg-slate-900 border-slate-700',
};

// ── Map dots config ────────────────────────────────────────────────────────────

const MAP_DOTS = [
  { x: 20, y: 38, label: 'EU'  },
  { x: 28, y: 40, label: 'RU', hot: true },
  { x: 80, y: 28, label: 'CN', hot: true },
  { x: 82, y: 22, label: 'KP' },
  { x: 22, y: 52, label: 'US', hot: true },
  { x: 57, y: 32, label: 'IR' },
  { x: 48, y: 60, label: 'AF' },
  { x: 62, y: 48, label: 'IN' },
];

// ── API helpers (no bearer needed here since AUTH_BYPASS or public) ─────────────

async function fetchJSON<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`/api/v1${path}`, {
      headers: { 'Accept': 'application/json' },
      credentials: 'include',
    });
    if (!r.ok) return null;
    return await r.json() as T;
  } catch {
    return null;
  }
}

// ── Normalize APT actors from radar snapshot ───────────────────────────────────

function normalizeActors(snapshot: any): ThreatActor[] {
  const colors = ['text-red-400', 'text-orange-400', 'text-rose-400', 'text-amber-400', 'text-yellow-400'];
  if (!snapshot) return [];

  // Try threat_actors array
  const rawActors: any[] = snapshot?.threat_actors ?? snapshot?.actors ?? [];
  if (rawActors.length > 0) {
    return rawActors.map((a: any, i: number) => ({
      id: a.id ?? a.name ?? String(i),
      name: a.name ?? `APT-${i}`,
      nation: a.nation ?? a.origin ?? 'Unknown',
      flag: a.flag ?? '🌐',
      active: a.active ?? true,
      campaigns: a.campaigns ?? a.campaign_count ?? 0,
      targets: a.targets ?? [],
      tools: a.tools ?? [],
      color: colors[i % colors.length],
      lastSeen: a.last_seen ?? a.lastSeen ?? 'Unknown',
      ttps: a.ttps ?? a.techniques ?? [],
    }));
  }

  return [];
}

// ── Normalize IOC events from radar snapshot ───────────────────────────────────

function normalizeIocs(snapshot: any): Omit<ThreatFeed, 'id' | 'ts'>[] {
  const rawIocs: any[] = snapshot?.indicators ?? snapshot?.iocs ?? snapshot?.events ?? [];
  return rawIocs.map((ioc: any) => ({
    ip: ioc.ip ?? ioc.indicator ?? ioc.value ?? '0.0.0.0',
    country: ioc.country ?? ioc.geo ?? 'Unknown',
    flag: ioc.flag ?? '🌐',
    type: ioc.type ?? ioc.category ?? 'IOC',
    confidence: ioc.confidence ?? Math.round((ioc.threat_score ?? 0.5) * 100),
    actor: ioc.actor ?? ioc.attributed_actor,
    mitre: ioc.mitre ?? ioc.technique ?? ioc.ttps?.[0],
    severity: ioc.severity ?? (
      (ioc.confidence ?? ioc.threat_score ?? 0) >= 0.85 ? 'CRITICAL' :
      (ioc.confidence ?? ioc.threat_score ?? 0) >= 0.6  ? 'HIGH' :
      (ioc.confidence ?? ioc.threat_score ?? 0) >= 0.35 ? 'MEDIUM' : 'LOW'
    ),
  }));
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function ThreatIntelligencePage() {
  const [feed, setFeed]           = useState<ThreatFeed[]>([]);
  const [actors, setActors]       = useState<ThreatActor[]>([]);
  const [selectedActor, setSelectedActor] = useState<ThreatActor | null>(null);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [stats, setStats]         = useState({ total: 0, critical: 0, countries: 0 });
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const feedRef = useRef<ThreatFeed[]>([]);

  const addFeedItem = useCallback((item: Omit<ThreatFeed, 'id' | 'ts'>) => {
    const evt: ThreatFeed = {
      ...item,
      id: `TI-${Math.floor(Math.random() * 90000 + 10000)}`,
      ts: new Date().toLocaleTimeString('en-GB', { hour12: false }),
    };
    setFeed(prev => {
      const next = [evt, ...prev].slice(0, 80);
      feedRef.current = next;
      setStats({
        total: next.length,
        critical: next.filter(e => e.severity === 'CRITICAL').length,
        countries: new Set(next.map(e => e.country ?? 'Unknown')).size,
      });
      return next;
    });
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [snapshot, landscape, graph] = await Promise.all([
        fetchJSON<any>('/intel/radar/snapshot'),
        fetchJSON<any>('/intel/adversarial/landscape'),
        fetchJSON<any>('/analysis/graph/full'),
      ]);

      // Actors
      const actorsFromSnapshot  = normalizeActors(snapshot);
      const actorsFromLandscape = normalizeActors(landscape);
      const allActors = actorsFromSnapshot.length > 0 ? actorsFromSnapshot : actorsFromLandscape;
      setActors(allActors);
      if (allActors.length > 0 && !selectedActor) setSelectedActor(allActors[0]);

      // IOC Feed
      const iocsFromSnapshot  = normalizeIocs(snapshot);
      const iocsFromLandscape = normalizeIocs(landscape);
      const allIocs = [...iocsFromSnapshot, ...iocsFromLandscape];
      if (allIocs.length > 0) {
        // stagger existing IOCs
        allIocs.forEach((ioc, i) => setTimeout(() => addFeedItem(ioc), i * 200));
      }

      // Graph nodes for the map
      if (graph?.nodes?.length > 0) {
        setGraphNodes(graph.nodes.slice(0, 50));
      }

      setLastRefresh(new Date());
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load threat intelligence');
    } finally {
      setLoading(false);
    }
  }, [addFeedItem, selectedActor]);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 60_000);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-screen bg-[#040608] text-slate-300 font-mono overflow-hidden">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(0,80,180,0.08)_0,transparent_60%)]" />

      {/* Header */}
      <header className="relative z-10 px-6 py-3 border-b border-blue-900/30 bg-black/60 backdrop-blur flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Globe size={18} className="text-blue-400 animate-pulse" />
          <div>
            <h1 className="text-base font-bold text-blue-400 tracking-widest">GLOBAL THREAT INTELLIGENCE — GEOPOLITICAL OSINT FUSION</h1>
            <p className="text-[9px] text-blue-900 tracking-widest">Live Feed · APT Profiles · Attack Map · MITRE ATT&CK · IOC Database</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          {error && (
            <div className="flex items-center gap-1.5 text-amber-500 text-[9px]">
              <AlertTriangle size={10} />
              {error}
            </div>
          )}
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-2.5 py-1 border border-blue-900/40 rounded text-blue-700 hover:text-blue-400 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
            REFRESH
          </button>
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-950/30 border border-blue-800 rounded text-blue-400 font-bold">
            <Activity size={10} className="animate-pulse" /> DEFCON 3 — ELEVATED
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="relative z-10 grid grid-cols-4 border-b border-blue-900/20 bg-black/40 shrink-0">
        {[
          { label: 'IOCs TRACKED',    value: stats.total,    color: 'text-blue-400'  },
          { label: 'CRITICAL',        value: stats.critical, color: 'text-rose-400'  },
          { label: 'NATIONS',         value: stats.countries,color: 'text-cyan-400'  },
          { label: 'ACTORS TRACKED',  value: actors.length,  color: 'text-purple-400'},
        ].map((s, i) => (
          <div key={i} className="flex flex-col items-center py-2.5 border-r border-blue-900/20 last:border-0">
            <span className={clsx('text-2xl font-bold tabular-nums', s.color)}>{s.value}</span>
            <span className="text-[8px] text-slate-700 tracking-widest">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Body */}
      <div className="relative z-10 flex flex-1 overflow-hidden">

        {/* Left: IOC Feed */}
        <div className="w-72 border-r border-blue-900/20 flex flex-col overflow-hidden shrink-0">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-blue-900/20 bg-black/20">
            <Radio size={11} className="text-blue-700 animate-pulse" />
            <span className="text-[9px] tracking-widest text-blue-800 font-black">LIVE IOC FEED</span>
            <span className="ml-auto text-[8px] text-blue-900">{lastRefresh.toLocaleTimeString()}</span>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-blue-950/30">
            {loading && feed.length === 0 ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="p-2.5 animate-pulse">
                  <div className="h-2 bg-blue-950/30 rounded w-3/4 mb-1.5" />
                  <div className="h-1.5 bg-blue-950/20 rounded w-1/2" />
                </div>
              ))
            ) : feed.length === 0 ? (
              <div className="p-4 text-center text-[10px] text-blue-900">No IOC data available</div>
            ) : (
              feed.map(e => (
                <div key={e.id} className="px-3 py-2 hover:bg-blue-950/10 transition-colors">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className={clsx('text-[7px] font-black tracking-widest px-1 py-px rounded border', SEV_CFG[e.severity])}>
                      {e.severity}
                    </span>
                    <span className="text-[8px] text-blue-900 ml-auto">{e.ts}</span>
                  </div>
                  <p className="text-[9px] text-blue-300 font-bold truncate">{e.ip}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[8px] text-blue-700 truncate">{e.type}</span>
                    {e.mitre && <span className="text-[7px] text-blue-900 bg-blue-950/40 px-1 rounded">{e.mitre}</span>}
                    <span className="text-[8px] text-blue-800 ml-auto">{e.confidence}%</span>
                  </div>
                  {e.actor && <p className="text-[8px] text-purple-700 mt-0.5 truncate">{e.actor}</p>}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Center: Attack Map */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-blue-900/20 bg-black/20 shrink-0">
            <Globe size={11} className="text-blue-700" />
            <span className="text-[9px] tracking-widest text-blue-800 font-black">GLOBAL ATTACK MAP — LIVE THREAT ORIGINS</span>
            {graphNodes.length > 0 && (
              <span className="ml-2 text-[8px] text-blue-900">{graphNodes.length} graph nodes</span>
            )}
          </div>
          <div className="flex-1 relative overflow-hidden">
            {/* Simplified world map background */}
            <div className="absolute inset-0 bg-gradient-to-b from-blue-950/5 to-blue-950/20" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,50,150,0.04)_0,transparent_70%)]" />

            {/* Grid lines */}
            <div className="absolute inset-0 pointer-events-none">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="absolute border-t border-blue-950/15" style={{ top: `${(i + 1) * 12}%`, left: 0, right: 0 }} />
              ))}
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="absolute border-l border-blue-950/15" style={{ left: `${(i + 1) * 8}%`, top: 0, bottom: 0 }} />
              ))}
            </div>

            {/* Attack origin dots */}
            {MAP_DOTS.map((dot, i) => (
              <div
                key={i}
                className="absolute"
                style={{ left: `${dot.x}%`, top: `${dot.y}%`, transform: 'translate(-50%,-50%)' }}
              >
                <div className={clsx(
                  'w-3 h-3 rounded-full flex items-center justify-center',
                  dot.hot ? 'bg-red-500/30 animate-pulse' : 'bg-blue-900/20'
                )}>
                  <div className={clsx('w-1.5 h-1.5 rounded-full', dot.hot ? 'bg-red-500' : 'bg-blue-600')} />
                </div>
                <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 text-[7px] text-blue-900 whitespace-nowrap">
                  {dot.label}
                </div>
              </div>
            ))}

            {/* Graph entity nodes overlaid */}
            {graphNodes.slice(0, 20).map((node, i) => {
              // distribute nodes pseudo-randomly but deterministically
              const x = 10 + ((node.id.charCodeAt(0) * 37 + i * 13) % 80);
              const y = 10 + ((node.id.charCodeAt(1) * 53 + i * 7) % 75);
              const risk = node.risk_score ?? 0;
              const color = risk >= 0.7 ? '#f43f5e' : risk >= 0.4 ? '#f59e0b' : '#10b981';
              return (
                <div
                  key={node.id}
                  className="absolute group cursor-pointer"
                  style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%,-50%)' }}
                  title={`${node.canonical_name} (risk: ${(risk * 100).toFixed(0)}%)`}
                >
                  <div
                    className="w-2 h-2 rounded-full transition-transform group-hover:scale-150"
                    style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}80` }}
                  />
                </div>
              );
            })}

            {/* Legend */}
            <div className="absolute bottom-3 left-3 flex items-center gap-4 bg-black/60 backdrop-blur rounded px-2 py-1">
              {[['#f43f5e', 'Critical'], ['#f59e0b', 'High'], ['#10b981', 'Low']].map(([c, l]) => (
                <div key={l} className="flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: c }} />
                  <span className="text-[7px] text-slate-700">{l}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Actor Profiles */}
        <div className="w-72 border-l border-blue-900/20 flex flex-col overflow-hidden shrink-0">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-blue-900/20 bg-black/20">
            <Eye size={11} className="text-blue-700" />
            <span className="text-[9px] tracking-widest text-blue-800 font-black">APT ACTOR PROFILES</span>
          </div>

          {/* Actor list */}
          <div className="overflow-y-auto divide-y divide-blue-950/20 flex-1">
            {loading && actors.length === 0 ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="p-3 animate-pulse">
                  <div className="h-2.5 bg-blue-950/30 rounded w-2/3 mb-2" />
                  <div className="h-2 bg-blue-950/20 rounded w-1/2" />
                </div>
              ))
            ) : actors.length === 0 ? (
              <div className="p-4 text-center text-[10px] text-blue-900">
                No APT data available from backend
              </div>
            ) : (
              actors.map(actor => (
                <button
                  key={actor.id}
                  onClick={() => setSelectedActor(actor)}
                  className={clsx(
                    'w-full text-left px-3 py-2.5 transition-colors flex items-center gap-2',
                    selectedActor?.id === actor.id ? 'bg-blue-950/30' : 'hover:bg-blue-950/10'
                  )}
                >
                  <span className="text-base shrink-0">{actor.flag ?? '🌐'}</span>
                  <div className="flex-1 min-w-0">
                    <p className={clsx('text-[11px] font-bold truncate', actor.color)}>{actor.name}</p>
                    <p className="text-[8px] text-blue-900 truncate">
                      {actor.active ? '● ACTIVE' : '○ INACTIVE'} · {actor.nation}
                    </p>
                  </div>
                  <ChevronRight size={10} className="text-blue-900 shrink-0" />
                </button>
              ))
            )}
          </div>

          {/* Selected actor detail */}
          {selectedActor && (
            <div className="border-t border-blue-900/20 p-3 space-y-2 bg-black/30 shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-lg">{selectedActor.flag ?? '🌐'}</span>
                <div>
                  <p className={clsx('text-[11px] font-black', selectedActor.color)}>{selectedActor.name}</p>
                  <p className="text-[8px] text-blue-900">{selectedActor.nation}</p>
                </div>
              </div>
              {selectedActor.tools && selectedActor.tools.length > 0 && (
                <div>
                  <p className="text-[7px] text-blue-900 mb-1">TOOLS</p>
                  <div className="flex flex-wrap gap-1">
                    {selectedActor.tools.slice(0, 4).map(t => (
                      <span key={t} className="text-[7px] bg-blue-950/40 text-blue-700 px-1 rounded border border-blue-900/20">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {selectedActor.ttps && selectedActor.ttps.length > 0 && (
                <div>
                  <p className="text-[7px] text-blue-900 mb-1">MITRE TTPs</p>
                  <div className="flex flex-wrap gap-1">
                    {selectedActor.ttps.slice(0, 6).map(t => (
                      <span key={t} className="text-[7px] bg-purple-950/40 text-purple-700 px-1 rounded border border-purple-900/20">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {selectedActor.campaigns !== undefined && (
                <div className="flex items-center gap-2 text-[8px]">
                  <Zap size={9} className="text-amber-600" />
                  <span className="text-blue-800">{selectedActor.campaigns} campaigns tracked</span>
                </div>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  className="flex-1 text-[8px] tracking-widest text-blue-700 border border-blue-900/40 rounded py-1 hover:bg-blue-950/30 transition-colors"
                  onClick={() => {
                    window.dispatchEvent(new CustomEvent('projectxy:toast', {
                      detail: { msg: `Generating hunting package for ${selectedActor.name}…`, level: 'ok' }
                    }));
                  }}
                >
                  HUNT PACKAGE
                </button>
                <button
                  className="flex-1 text-[8px] tracking-widest text-red-700 border border-red-900/40 rounded py-1 hover:bg-red-950/30 transition-colors"
                  onClick={() => {
                    window.dispatchEvent(new CustomEvent('projectxy:toast', {
                      detail: { msg: `Intel blocks applied for ${selectedActor.name}`, level: 'warn' }
                    }));
                  }}
                >
                  APPLY BLOCKS
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
