'use client';

import React, { useEffect, useState, useCallback } from 'react';
import TeamShell from '@/components/Layout/TeamShell';
import { api } from '@/lib/api';
import {
  Cpu, Shield, AlertTriangle, Wifi, Camera, Activity,
  RefreshCw, ChevronDown, ChevronUp, Server, Router,
  Eye, Zap, TrendingUp, Circle
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
interface IoTDevice {
  id: string;
  name: string;
  ip: string;
  type: 'PLC' | 'HMI' | 'IP Camera' | 'Smart Sensor' | 'Industrial Router';
  last_seen: string;
  risk_score: number;
  status: 'online' | 'offline' | 'warning';
  vendor?: string;
  firmware?: string;
}

interface Vulnerability {
  id: string;
  device_id: string;
  cve_id: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  cvss_score: number;
  remediated: boolean;
}

// ─── Constants ────────────────────────────────────────────────────────────────
const DEVICE_TYPE_ICONS: Record<string, React.ReactNode> = {
  'PLC': <Cpu size={14} />,
  'HMI': <Eye size={14} />,
  'IP Camera': <Camera size={14} />,
  'Smart Sensor': <Zap size={14} />,
  'Industrial Router': <Router size={14} />,
};

const SEV_COLORS: Record<string, string> = {
  critical: 'text-red-400 bg-red-950/60 border border-red-800/50',
  high: 'text-orange-400 bg-orange-950/60 border border-orange-800/50',
  medium: 'text-yellow-400 bg-yellow-950/60 border border-yellow-800/50',
  low: 'text-green-400 bg-green-950/60 border border-green-800/50',
};

function riskColor(score: number): string {
  if (score >= 80) return 'text-red-400';
  if (score >= 50) return 'text-amber-400';
  return 'text-emerald-400';
}

function riskBg(score: number): string {
  if (score >= 80) return 'bg-red-500';
  if (score >= 50) return 'bg-amber-500';
  return 'bg-emerald-500';
}

// ─── Circular Gauge ───────────────────────────────────────────────────────────
function CircularGauge({ score }: { score: number }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  const color = score >= 80 ? '#FF2D20' : score >= 50 ? '#F59E0B' : '#10B981';

  return (
    <div className="relative flex items-center justify-center w-36 h-36">
      <svg className="absolute inset-0 -rotate-90" width="144" height="144" viewBox="0 0 144 144">
        <circle cx="72" cy="72" r={r} fill="none" stroke="#0f2a3f" strokeWidth="10" />
        <circle
          cx="72" cy="72" r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease', filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="z-10 flex flex-col items-center">
        <span className="text-3xl font-black tabular-nums" style={{ color }}>{score}</span>
        <span className="text-[10px] font-mono text-sky-700 tracking-widest mt-0.5">POSTURE</span>
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon, accent }: {
  label: string; value: string | number; icon: React.ReactNode; accent: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-sky-900/30 bg-gradient-to-br from-sky-950/40 to-[#00091A] p-5">
      <div className="absolute top-0 right-0 w-20 h-20 rounded-full blur-2xl opacity-20" style={{ background: accent }} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-mono text-sky-700 tracking-widest uppercase">{label}</p>
          <p className="text-3xl font-black text-sky-100 mt-1 tabular-nums">{value}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-sky-900/40 text-sky-400">{icon}</div>
      </div>
    </div>
  );
}

// ─── Device Type Breakdown ─────────────────────────────────────────────────
function DeviceBreakdown({ devices }: { devices: IoTDevice[] }) {
  const types = ['PLC', 'HMI', 'IP Camera', 'Smart Sensor', 'Industrial Router'];
  const counts = types.map(t => ({ type: t, count: devices.filter(d => d.type === t).length }));
  const max = Math.max(...counts.map(c => c.count), 1);

  return (
    <div className="space-y-2.5">
      {counts.map(({ type, count }) => (
        <div key={type} className="flex items-center gap-3">
          <div className="text-sky-600 w-4 shrink-0">{DEVICE_TYPE_ICONS[type]}</div>
          <span className="text-[11px] font-mono text-sky-500 w-32 truncate">{type}</span>
          <div className="flex-1 h-1.5 bg-sky-950 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-600 to-sky-400 transition-all duration-700"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <span className="text-[11px] font-mono text-sky-400 w-5 text-right">{count}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function GuardianPage() {
  const [devices, setDevices] = useState<IoTDevice[]>([]);
  const [vulns, setVulns] = useState<Vulnerability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<keyof IoTDevice>('risk_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selectedDevice, setSelectedDevice] = useState<IoTDevice | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [devData, vulnData] = await Promise.allSettled([
        api.apiRequest<IoTDevice[]>('/guardian/iot-devices'),
        api.apiRequest<Vulnerability[]>('/guardian/vulnerabilities'),
      ]);
      setDevices(devData.status === 'fulfilled' ? devData.value ?? [] : []);
      setVulns(vulnData.status === 'fulfilled' ? vulnData.value ?? [] : []);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const sorted = [...devices].sort((a, b) => {
    const av = a[sortField] as any, bv = b[sortField] as any;
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });

  const totalDevices = devices.length;
  const criticalVulns = vulns.filter(v => v.severity === 'critical' && !v.remediated).length;
  const avgRisk = devices.length ? Math.round(devices.reduce((s, d) => s + d.risk_score, 0) / devices.length) : 0;
  const postureScore = Math.max(0, 100 - avgRisk);
  const deviceVulns = (deviceId: string) => vulns.filter(v => v.device_id === deviceId);

  function toggleSort(field: keyof IoTDevice) {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  }

  const SortIcon = ({ field }: { field: keyof IoTDevice }) =>
    sortField === field
      ? (sortDir === 'desc' ? <ChevronDown size={12} /> : <ChevronUp size={12} />)
      : <ChevronDown size={12} className="opacity-20" />;

  return (
    <TeamShell
      team="blue"
      title="GUARDIAN IoT/OT DEFENSE PERIMETER"
      subtitle="Operational Technology Security Monitor — Real-time device posture assessment"
      badge="LIVE"
    >
      <div className="p-6 space-y-6">
        {/* Stat Cards + Gauge Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatCard label="Total Devices" value={loading ? '—' : totalDevices} icon={<Server size={18} />} accent="#0EA5E9" />
          <StatCard label="Critical Vulns" value={loading ? '—' : criticalVulns} icon={<AlertTriangle size={18} />} accent="#EF4444" />
          <StatCard label="Avg Risk Score" value={loading ? '—' : avgRisk} icon={<TrendingUp size={18} />} accent="#F59E0B" />
          <div className="rounded-xl border border-sky-900/30 bg-gradient-to-br from-sky-950/40 to-[#00091A] p-5 flex items-center justify-center">
            {loading ? (
              <div className="w-10 h-10 border-2 border-sky-600 border-t-transparent rounded-full animate-spin" />
            ) : (
              <CircularGauge score={postureScore} />
            )}
          </div>
        </div>

        {/* Middle row: Device Breakdown + Vuln Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-xl border border-sky-900/30 bg-[#00091A] p-5">
            <h3 className="text-[10px] font-mono text-sky-600 tracking-widest mb-4 uppercase">Device Type Breakdown</h3>
            {loading ? (
              <div className="space-y-2.5">{[1,2,3,4,5].map(i => (
                <div key={i} className="h-4 bg-sky-950 rounded animate-pulse" />
              ))}</div>
            ) : devices.length === 0 ? (
              <p className="text-sky-800 text-xs font-mono text-center py-4">No devices enrolled</p>
            ) : (
              <DeviceBreakdown devices={devices} />
            )}
          </div>

          <div className="lg:col-span-2 rounded-xl border border-sky-900/30 bg-[#00091A] p-5">
            <h3 className="text-[10px] font-mono text-sky-600 tracking-widest mb-4 uppercase">Vulnerability Distribution</h3>
            {loading ? (
              <div className="grid grid-cols-2 gap-3">{[1,2,3,4].map(i => (
                <div key={i} className="h-16 bg-sky-950 rounded animate-pulse" />
              ))}</div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {(['critical','high','medium','low'] as const).map(sev => {
                  const count = vulns.filter(v => v.severity === sev).length;
                  return (
                    <div key={sev} className={`rounded-lg p-3 text-center ${SEV_COLORS[sev]}`}>
                      <p className="text-2xl font-black tabular-nums">{count}</p>
                      <p className="text-[10px] font-mono uppercase tracking-widest mt-0.5 opacity-70">{sev}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Device Inventory Table */}
        <div className="rounded-xl border border-sky-900/30 bg-[#00091A] overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-sky-900/30">
            <h3 className="text-[10px] font-mono text-sky-600 tracking-widest uppercase">Device Inventory</h3>
            <button
              onClick={fetchData}
              disabled={refreshing}
              className="flex items-center gap-1.5 text-[10px] font-mono text-sky-600 hover:text-sky-400 transition-colors"
            >
              <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
              REFRESH
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 px-5 py-3 bg-red-950/30 border-b border-red-900/30">
              <AlertTriangle size={14} className="text-red-400" />
              <p className="text-xs font-mono text-red-400">{error} — showing cached/empty data</p>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-sky-900/20 text-sky-700">
                  {[
                    ['name', 'Device Name'],
                    ['ip', 'IP Address'],
                    ['type', 'Type'],
                    ['last_seen', 'Last Seen'],
                    ['risk_score', 'Risk Score'],
                  ].map(([field, label]) => (
                    <th
                      key={field}
                      className="px-4 py-3 text-left text-[10px] tracking-widest uppercase cursor-pointer select-none hover:text-sky-400 transition-colors"
                      onClick={() => toggleSort(field as keyof IoTDevice)}
                    >
                      <span className="flex items-center gap-1">
                        {label} <SortIcon field={field as keyof IoTDevice} />
                      </span>
                    </th>
                  ))}
                  <th className="px-4 py-3 text-left text-[10px] tracking-widest uppercase text-sky-700">Vulns</th>
                  <th className="px-4 py-3 text-left text-[10px] tracking-widest uppercase text-sky-700">Status</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-sky-950/50">
                      {Array.from({ length: 7 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-3 bg-sky-950 rounded animate-pulse" style={{ width: `${60 + Math.random() * 30}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : sorted.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Shield size={28} className="text-sky-900" />
                        <p className="text-sky-800 text-[11px] tracking-widest">NO DEVICES IN REGISTRY</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  sorted.map(device => {
                    const dv = deviceVulns(device.id);
                    const isSelected = selectedDevice?.id === device.id;
                    return (
                      <React.Fragment key={device.id}>
                        <tr
                          className={`border-b border-sky-950/40 cursor-pointer transition-colors hover:bg-sky-950/20 ${isSelected ? 'bg-sky-950/30' : ''}`}
                          onClick={() => setSelectedDevice(isSelected ? null : device)}
                        >
                          <td className="px-4 py-3 text-sky-300 font-semibold">{device.name}</td>
                          <td className="px-4 py-3 text-sky-500 tabular-nums">{device.ip}</td>
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-1.5 text-sky-400">
                              {DEVICE_TYPE_ICONS[device.type]}
                              {device.type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sky-600 tabular-nums">{device.last_seen}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1 bg-sky-950 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${riskBg(device.risk_score)}`} style={{ width: `${device.risk_score}%` }} />
                              </div>
                              <span className={`font-black tabular-nums ${riskColor(device.risk_score)}`}>{device.risk_score}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${dv.length > 0 ? 'bg-red-950/60 text-red-400' : 'bg-sky-950 text-sky-700'}`}>
                              {dv.length}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-1.5">
                              <Circle
                                size={7}
                                className={device.status === 'online' ? 'fill-emerald-400 text-emerald-400' : device.status === 'warning' ? 'fill-amber-400 text-amber-400' : 'fill-slate-600 text-slate-600'}
                              />
                              <span className={`text-[10px] tracking-widest ${device.status === 'online' ? 'text-emerald-400' : device.status === 'warning' ? 'text-amber-400' : 'text-slate-500'}`}>
                                {device.status?.toUpperCase() ?? 'UNKNOWN'}
                              </span>
                            </span>
                          </td>
                        </tr>
                        {isSelected && (
                          <tr className="border-b border-sky-900/30">
                            <td colSpan={7} className="px-6 py-4 bg-sky-950/10">
                              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <div>
                                  <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-1.5">DEVICE DETAILS</p>
                                  <div className="space-y-1 text-[11px]">
                                    <div className="flex gap-2"><span className="text-sky-700">Vendor:</span><span className="text-sky-300">{device.vendor ?? '—'}</span></div>
                                    <div className="flex gap-2"><span className="text-sky-700">Firmware:</span><span className="text-sky-300">{device.firmware ?? '—'}</span></div>
                                    <div className="flex gap-2"><span className="text-sky-700">MAC:</span><span className="text-sky-300 font-mono">—</span></div>
                                  </div>
                                </div>
                                <div className="sm:col-span-2">
                                  <p className="text-[10px] font-mono text-sky-700 tracking-widest mb-1.5">VULNERABILITIES ({dv.length})</p>
                                  {dv.length === 0 ? (
                                    <p className="text-sky-800 text-[11px]">No vulnerabilities found for this device.</p>
                                  ) : (
                                    <div className="space-y-1.5 max-h-36 overflow-y-auto pr-2">
                                      {dv.map(v => (
                                        <div key={v.id} className="flex items-center gap-2 text-[11px]">
                                          <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${SEV_COLORS[v.severity]}`}>{v.severity.toUpperCase()}</span>
                                          <span className="text-sky-600 font-mono">{v.cve_id}</span>
                                          <span className="text-sky-400 truncate">{v.title}</span>
                                          <span className="text-sky-700 ml-auto tabular-nums">CVSS {v.cvss_score}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </TeamShell>
  );
}
