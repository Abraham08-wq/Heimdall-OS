'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import TeamShell from '@/components/Layout/TeamShell';
import { api } from '@/lib/api';
import {
  Monitor, Laptop, Network, Cpu, Shield, Search,
  Filter, AlertTriangle, ChevronRight, X, RefreshCw,
  Globe, Clock, Hash, Layers, Activity, Server,
  Lock, Unlock, Plus, ShieldAlert
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Device {
  id: string;
  hostname: string;
  ip: string;
  mac?: string;
  os?: string;
  type?: string;
  risk_score?: number;
  last_seen?: string;
  ports?: number[];
  services?: string[];
  cves?: string[];
  tags?: string[];
  status?: string;
  department?: string;
}

type RiskLevel = 'all' | 'critical' | 'high' | 'medium' | 'low';
type DeviceType = 'all' | 'Server' | 'Workstation' | 'Network' | 'IoT';

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getRiskLevel(score: number): RiskLevel {
  if (score >= 80) return 'critical';
  if (score >= 50) return 'high';
  if (score >= 25) return 'medium';
  return 'low';
}

function riskStyle(score: number) {
  if (score >= 80) return { text: 'text-red-400', bg: 'bg-red-500', badge: 'bg-red-950/60 text-red-400 border-red-800/50' };
  if (score >= 50) return { text: 'text-amber-400', bg: 'bg-amber-500', badge: 'bg-amber-950/60 text-amber-400 border-amber-800/50' };
  if (score >= 25) return { text: 'text-yellow-400', bg: 'bg-yellow-500', badge: 'bg-yellow-950/60 text-yellow-400 border-yellow-800/50' };
  return { text: 'text-emerald-400', bg: 'bg-emerald-500', badge: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50' };
}

function TypeIcon({ type }: { type?: string }) {
  const cls = "shrink-0 text-sky-500";
  if (type === 'Server') return <Server size={14} className={cls} />;
  if (type === 'Workstation') return <Laptop size={14} className={cls} />;
  if (type === 'Network') return <Network size={14} className={cls} />;
  if (type === 'IoT') return <Cpu size={14} className={cls} />;
  return <Monitor size={14} className={cls} />;
}

// ─── Device Detail Panel ──────────────────────────────────────────────────────
function DeviceDetail({
  device, onClose, onIsolate, onRelease
}: {
  device: Device;
  onClose: () => void;
  onIsolate: (id: string) => Promise<void>;
  onRelease: (id: string) => Promise<void>;
}) {
  const style = riskStyle(device.risk_score ?? 0);
  const isIsolated = device.status === 'isolated' || device.status === 'quarantined';
  const [acting, setActing] = useState(false);

  const handleIsolate = async () => {
    setActing(true);
    try {
      if (isIsolated) await onRelease(device.id);
      else await onIsolate(device.id);
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-[#00091A] border-l border-sky-900/40 z-40 flex flex-col shadow-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-sky-900/30 bg-gradient-to-r from-sky-950/40 to-[#00091A]">
        <div className="flex items-center gap-2">
          <TypeIcon type={device.type} />
          <div>
            <p className="text-sm font-semibold text-sky-200">{device.hostname}</p>
            <p className="text-[10px] font-mono text-sky-700">{device.ip}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isIsolated && (
            <span className="text-[8px] font-black tracking-widest text-red-400 bg-red-950/60 border border-red-800 px-2 py-0.5 rounded animate-pulse">
              ISOLATED
            </span>
          )}
          <button onClick={onClose} className="text-sky-700 hover:text-sky-400 transition-colors p-1">
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Risk Score */}
        <div>
          <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Risk Posture</p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-sky-950 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${style.bg} transition-all duration-700`} style={{ width: `${device.risk_score ?? 0}%` }} />
            </div>
            <span className={`text-2xl font-black tabular-nums ${style.text}`}>{device.risk_score ?? '—'}</span>
          </div>
          <span className={`mt-1.5 inline-block text-[9px] px-2 py-0.5 rounded border font-mono tracking-widest ${style.badge}`}>
            {getRiskLevel(device.risk_score ?? 0).toUpperCase()}
          </span>
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={handleIsolate}
            disabled={acting}
            className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-[11px] font-mono font-bold tracking-widest transition-all disabled:opacity-50 ${
              isIsolated
                ? 'border-emerald-800/60 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40'
                : 'border-red-800/60 bg-red-950/20 text-red-400 hover:bg-red-950/40'
            }`}
          >
            {acting ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : isIsolated ? (
              <Unlock size={12} />
            ) : (
              <Lock size={12} />
            )}
            {isIsolated ? 'RELEASE' : 'ISOLATE'}
          </button>
          <button
            className="flex items-center justify-center gap-2 rounded-lg border border-sky-900/40 bg-sky-950/10 px-3 py-2.5 text-[11px] font-mono font-bold tracking-widest text-sky-600 hover:text-sky-400 hover:bg-sky-950/20 transition-all"
            onClick={() => {
              window.dispatchEvent(new CustomEvent('projectxy:toast', {
                detail: { msg: `Port scan queued for ${device.hostname}`, level: 'ok' }
              }));
            }}
          >
            <ShieldAlert size={12} />
            SCAN
          </button>
        </div>

        {/* Details Grid */}
        <div>
          <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">System Info</p>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
            {[
              { label: 'MAC', value: device.mac ?? '—', icon: <Hash size={10} /> },
              { label: 'OS', value: device.os ?? '—', icon: <Layers size={10} /> },
              { label: 'Type', value: device.type ?? '—', icon: <Monitor size={10} /> },
              { label: 'Dept', value: device.department ?? '—', icon: <Globe size={10} /> },
              { label: 'Status', value: device.status ?? '—', icon: <Activity size={10} /> },
              { label: 'Last Seen', value: device.last_seen ?? '—', icon: <Clock size={10} /> },
            ].map(({ label, value, icon }) => (
              <div key={label} className="rounded-lg bg-sky-950/20 border border-sky-900/20 p-2.5">
                <div className="flex items-center gap-1 text-sky-700 mb-1">{icon}<span className="text-[9px] tracking-widest">{label}</span></div>
                <p className="text-sky-300 truncate">{value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Open Ports */}
        {(device.ports?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Open Ports ({device.ports!.length})</p>
            <div className="flex flex-wrap gap-1.5">
              {device.ports!.map(p => (
                <span key={p} className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950/40 border border-sky-900/30 text-sky-400">{p}</span>
              ))}
            </div>
          </div>
        )}

        {/* Services */}
        {(device.services?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Services</p>
            <div className="space-y-1">
              {device.services!.map(s => (
                <div key={s} className="text-[11px] font-mono text-sky-400 flex items-center gap-1.5 py-1 border-b border-sky-950/30">
                  <Activity size={10} className="text-sky-700" />{s}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CVEs */}
        {(device.cves?.length ?? 0) > 0 && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase flex items-center gap-1.5">
              <AlertTriangle size={10} className="text-red-500" />
              CVEs ({device.cves!.length})
            </p>
            <div className="space-y-1">
              {device.cves!.map(cve => (
                <div key={cve} className="text-[10px] font-mono text-red-400 bg-red-950/20 px-2 py-1 rounded border border-red-900/20">{cve}</div>
              ))}
            </div>
          </div>
        )}

        {/* Last Activity */}
        {device.last_seen && (
          <div>
            <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-2 uppercase">Last Activity</p>
            <p className="text-xs font-mono text-sky-500">{device.last_seen}</p>
          </div>
        )}
      </div>
    </div>
  );
}


// ─── Main Page ────────────────────────────────────────────────────────────────
export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<RiskLevel>('all');
  const [selected, setSelected] = useState<Device | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [deviceTypes, setDeviceTypes] = useState<string[]>(['all', 'Server', 'Workstation', 'Network', 'IoT', 'Mobile', 'Firewall', 'ICS/OT']);

  const fetchDevices = useCallback(async () => {
    try {
      setRefreshing(true);
      const [deviceData, configTypes] = await Promise.all([
        api.apiRequest<Device[]>('/devices/'),
        // ✅ Fetch live device types from /api/v1/config/device-types
        fetch('/api/v1/config/device-types')
          .then(r => r.ok ? r.json() : null)
          .catch(() => null),
      ]);
      setDevices(Array.isArray(deviceData) ? deviceData : []);
      if (configTypes && Array.isArray(configTypes) && configTypes.length > 0) {
        // Backend returns [{value, label}, ...] — prepend 'all' sentinel
        const typeValues: string[] = ['all', ...configTypes.map((t: any) => t.value || t.label || t)];
        setDeviceTypes(typeValues);
      }
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setDevices([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const isolateDevice = useCallback(async (deviceId: string) => {
    try {
      await api.apiRequest(`/devices/${deviceId}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'isolated' }),
      });
      setDevices(prev => prev.map(d => d.id === deviceId ? { ...d, status: 'isolated' } : d));
      setSelected(prev => prev?.id === deviceId ? { ...prev, status: 'isolated' } : prev);
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Device isolated: ${deviceId.slice(0, 8)}`, level: 'warn' }
      }));
    } catch (e) {
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Isolation failed: ${(e as Error).message}`, level: 'error' }
      }));
    }
  }, []);

  const releaseDevice = useCallback(async (deviceId: string) => {
    try {
      await api.apiRequest(`/devices/${deviceId}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'online' }),
      });
      setDevices(prev => prev.map(d => d.id === deviceId ? { ...d, status: 'online' } : d));
      setSelected(prev => prev?.id === deviceId ? { ...prev, status: 'online' } : prev);
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Device released: ${deviceId.slice(0, 8)}`, level: 'ok' }
      }));
    } catch (e) {
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Release failed: ${(e as Error).message}`, level: 'error' }
      }));
    }
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const filtered = useMemo(() => devices.filter(d => {
    const q = search.toLowerCase();
    const matchSearch = !q || d.hostname?.toLowerCase().includes(q) || d.ip?.includes(q) || d.mac?.toLowerCase().includes(q) || d.os?.toLowerCase().includes(q);
    const matchType = typeFilter === 'all' || d.type === typeFilter;
    const matchRisk = riskFilter === 'all' || getRiskLevel(d.risk_score ?? 0) === riskFilter;
    return matchSearch && matchType && matchRisk;
  }), [devices, search, typeFilter, riskFilter]);

  const RISK_LEVELS: RiskLevel[] = ['all', 'critical', 'high', 'medium', 'low'];

  const RISK_BADGE_COLORS: Record<RiskLevel, string> = {
    all: 'bg-sky-950 text-sky-500 border-sky-800',
    critical: 'bg-red-950/60 text-red-400 border-red-800/50',
    high: 'bg-orange-950/60 text-orange-400 border-orange-800/50',
    medium: 'bg-yellow-950/60 text-yellow-400 border-yellow-800/50',
    low: 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50',
  };

  return (
    <TeamShell
      team="blue"
      title="ASSET REGISTRY & DEVICE INVENTORY"
      subtitle="Network-wide device discovery — hostname, IP, OS, risk posture, service map"
    >
      <div className="p-6 space-y-5">
        {/* Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-700" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search hostname, IP, OS…"
              className="w-full bg-sky-950/20 border border-sky-900/30 rounded-lg pl-9 pr-4 py-2 text-sm font-mono text-sky-300 placeholder-sky-900 focus:outline-none focus:border-sky-600/60 focus:ring-1 focus:ring-sky-600/20 transition-all"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-sky-700 hover:text-sky-400">
                <X size={13} />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={13} className="text-sky-700" />
            {/* Type Filter — live from /api/v1/config/device-types */}
            {deviceTypes.map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`text-[10px] font-mono px-2.5 py-1 rounded border tracking-widest transition-all ${typeFilter === t ? 'bg-sky-900/60 text-sky-300 border-sky-700' : 'text-sky-700 border-sky-900/30 hover:border-sky-700/50'}`}
              >
                {t.toUpperCase()}
              </button>
            ))}
            <span className="w-px h-4 bg-sky-900/40" />
            {/* Risk Filter */}
            {RISK_LEVELS.map(r => (
              <button
                key={r}
                onClick={() => setRiskFilter(r)}
                className={`text-[10px] font-mono px-2.5 py-1 rounded border tracking-widest transition-all ${riskFilter === r ? `${RISK_BADGE_COLORS[r]} opacity-100` : 'text-sky-800 border-sky-900/20 hover:border-sky-700/30'}`}
              >
                {r.toUpperCase()}
              </button>
            ))}
            <button
              onClick={fetchDevices}
              disabled={refreshing}
              className="ml-2 text-sky-700 hover:text-sky-400 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
            <AlertTriangle size={14} className="text-red-400 shrink-0" />
            <p className="text-xs font-mono text-red-400">{error}</p>
          </div>
        )}

        {/* Summary Strip */}
        {!loading && (
          <div className="flex items-center gap-4 text-[10px] font-mono text-sky-700">
            <span className="text-sky-500">{filtered.length}</span> of {devices.length} devices
            {(['critical','high','medium','low'] as RiskLevel[]).map(lvl => {
              const cnt = devices.filter(d => getRiskLevel(d.risk_score ?? 0) === lvl).length;
              return cnt > 0 ? (
                <span key={lvl} className={`px-1.5 py-0.5 rounded border text-[9px] ${RISK_BADGE_COLORS[lvl]}`}>
                  {cnt} {lvl}
                </span>
              ) : null;
            })}
          </div>
        )}

        {/* Table */}
        <div className="rounded-xl border border-sky-900/30 bg-[#00091A] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-sky-900/30 text-sky-700 text-[10px] tracking-widest uppercase">
                  <th className="px-4 py-3 text-left">Hostname</th>
                  <th className="px-4 py-3 text-left">IP Address</th>
                  <th className="px-4 py-3 text-left">MAC</th>
                  <th className="px-4 py-3 text-left">OS</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Risk</th>
                  <th className="px-4 py-3 text-left">Last Seen</th>
                  <th className="px-4 py-3 text-left"></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-sky-950/30">
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-3 bg-sky-950 rounded animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-16 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <Shield size={32} className="text-sky-900" />
                        <p className="text-sky-800 text-[11px] tracking-widest">
                          {devices.length === 0 ? 'NO DEVICES DISCOVERED' : 'NO DEVICES MATCH FILTER'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filtered.map(device => {
                    const style = riskStyle(device.risk_score ?? 0);
                    const isSelected = selected?.id === device.id;
                    return (
                      <tr
                        key={device.id}
                        onClick={() => setSelected(isSelected ? null : device)}
                        className={`border-b border-sky-950/30 cursor-pointer transition-colors hover:bg-sky-950/20 ${isSelected ? 'bg-sky-950/30 border-sky-800/30' : ''}`}
                      >
                        <td className="px-4 py-3 text-sky-200 font-semibold">{device.hostname || '—'}</td>
                        <td className="px-4 py-3 text-sky-500 tabular-nums">{device.ip}</td>
                        <td className="px-4 py-3 text-sky-700 tabular-nums">{device.mac || '—'}</td>
                        <td className="px-4 py-3 text-sky-500">{device.os || '—'}</td>
                        <td className="px-4 py-3">
                          <span className="flex items-center gap-1.5 text-sky-400">
                            <TypeIcon type={device.type} />
                            {device.type || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-12 h-1.5 bg-sky-950 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${style.bg}`} style={{ width: `${device.risk_score ?? 0}%` }} />
                            </div>
                            <span className={`font-black tabular-nums ${style.text}`}>{device.risk_score ?? '—'}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sky-700">{device.last_seen || '—'}</td>
                        <td className="px-4 py-3">
                          <ChevronRight size={14} className={`transition-transform ${isSelected ? 'text-sky-400 rotate-90' : 'text-sky-800'}`} />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Detail Sidebar */}
      {selected && (
        <>
          <div className="fixed inset-0 bg-black/40 z-30" onClick={() => setSelected(null)} />
          <DeviceDetail
            device={selected}
            onClose={() => setSelected(null)}
            onIsolate={isolateDevice}
            onRelease={releaseDevice}
          />
        </>
      )}
    </TeamShell>
  );
}
