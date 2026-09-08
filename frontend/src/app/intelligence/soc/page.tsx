'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Bot, AlertTriangle, CheckCircle2, Clock, RefreshCw,
    Zap, Shield, Play, ChevronRight, Activity, TrendingUp, Users, Timer
} from 'lucide-react';

const API = '/api/v1/intel';
const CONFIG_API = '/api/v1/config';

interface Incident { id: string; status: string; severity: string; source: string; description: string; technique?: string; category?: string; threat_name?: string; entity_id: string; playbooks_executed: string[]; narrative?: string; created_at: string; mttr_seconds?: number; }
interface SOCMetrics { alerts_processed: number; incidents_created: number; playbooks_executed: number; auto_contained: number; escalated_to_human: number; open_incidents: number; critical_incidents: number; avg_mttr_seconds: number; playbook_count: number; correlation_rules: number; }
interface Playbook { id: string; name: string; action_count: number; auto_execute: boolean; escalate_after_minutes: number; }
interface SimType { value: string; label: string; description?: string; severity?: string; technique?: string; }

const SEV_STYLES: Record<string, string> = {
    CRITICAL: 'text-red-400 border-red-500/30 bg-red-500/10',
    HIGH: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
    MEDIUM: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
    LOW: 'text-slate-400 border-slate-500/20 bg-slate-500/10',
};
const STATUS_STYLES: Record<string, string> = {
    OPEN: 'text-red-400 bg-red-500/10',
    INVESTIGATING: 'text-yellow-400 bg-yellow-500/10',
    CONTAINED: 'text-cyan-400 bg-cyan-500/10',
    RESOLVED: 'text-emerald-400 bg-emerald-500/10',
    FALSE_POSITIVE: 'text-slate-400 bg-slate-500/10',
};

// Fallback types if the backend config endpoint is not yet populated
const DEFAULT_SIM_TYPES: SimType[] = [
    { value: 'ransomware_detected', label: 'Ransomware', description: 'CRITICAL · T1486 · P0 escalation', severity: 'CRITICAL' },
    { value: 'lateral_movement', label: 'Lateral Movement', description: 'CRITICAL · T1021 · Honeypot deploy', severity: 'CRITICAL' },
    { value: 'credential_dump', label: 'Credential Dump', description: 'CRITICAL · T1003 · Host isolation', severity: 'CRITICAL' },
    { value: 'mobile_money_fraud', label: 'Mobile Money Fraud', description: 'CRITICAL · KE-001 · M-PESA pattern', severity: 'CRITICAL' },
    { value: 'prompt_injection', label: 'Prompt Injection', description: 'HIGH · Prompt injection · Session revoke', severity: 'HIGH' },
];

export default function AutonomousSOCPage() {
    const [tab, setTab] = useState<'dashboard' | 'incidents' | 'playbooks' | 'simulate'>('dashboard');
    const [metrics, setMetrics] = useState<SOCMetrics | null>(null);
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
    const [simulationTypes, setSimulationTypes] = useState<SimType[]>(DEFAULT_SIM_TYPES);
    const [loading, setLoading] = useState(false);
    const [simulating, setSimulating] = useState<string | null>(null);
    const [simResult, setSimResult] = useState<{ threat_type: string; incident: Incident | null; playbook_result: Record<string, unknown> | null } | null>(null);
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [simError, setSimError] = useState<string | null>(null);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [m, i, p, simTypes] = await Promise.all([
                fetch(`${API}/soc/metrics`).then(r => r.ok ? r.json() : null),
                fetch(`${API}/soc/incidents?limit=30`).then(r => r.ok ? r.json() : null),
                fetch(`${API}/soc/playbooks`).then(r => r.ok ? r.json() : null),
                // ✅ Dynamic simulation types from backend config_entries table
                fetch(`${CONFIG_API}/simulation-types`).then(r => r.ok ? r.json() : null),
            ]);
            if (m) setMetrics(m);
            if (i) setIncidents(i.incidents ?? []);
            if (p) setPlaybooks(p.playbooks ?? []);
            if (simTypes && Array.isArray(simTypes) && simTypes.length > 0) {
                // Backend returns { value, label, description } objects
                setSimulationTypes(simTypes);
            }
        } catch (e: any) {
            setFetchError(e?.message ?? 'Failed to load SOC data');
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchAll(); const id = setInterval(fetchAll, 30000); return () => clearInterval(id); }, [fetchAll]);

    const simulate = async (type: string) => {
        setSimulating(type); setSimResult(null); setSimError(null);
        try {
            const r = await fetch(`${API}/soc/simulate?threat_type=${type}`, { method: 'POST', credentials: 'include' });
            if (r.ok) { const d = await r.json(); setSimResult(d); await fetchAll(); }
            else { const e = await r.json().catch(() => ({})); setSimError(e.detail ?? `Simulation failed: HTTP ${r.status}`); }
        } catch (e: any) {
            setSimError(e?.message ?? 'Simulation failed');
        } finally { setSimulating(null); }
    };

    const filteredIncidents = statusFilter === 'ALL' ? incidents : incidents.filter(i => i.status === statusFilter);

    const mttrDisplay = (s?: number) => {
        if (!s) return '—';
        if (s < 60) return `${s}s`;
        if (s < 3600) return `${Math.round(s / 60)}m`;
        return `${(s / 3600).toFixed(1)}h`;
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/30 to-cyan-600/20 border border-blue-500/20">
                        <Bot size={22} className="text-blue-300" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Autonomous SOC</h1>
                        <p className="text-sm text-slate-400">AI-driven incident triage · SOAR playbooks · Multi-stage correlation</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {metrics && (
                        <div className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-xs font-semibold ${metrics.open_incidents > 0 ? 'border-red-500/30 bg-red-500/10 text-red-400' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'}`}>
                            <span className={`h-2 w-2 rounded-full animate-pulse ${metrics.open_incidents > 0 ? 'bg-red-400' : 'bg-emerald-400'}`} />
                            {metrics.open_incidents > 0 ? `${metrics.open_incidents} OPEN` : 'ALL CLEAR'}
                        </div>
                    )}
                    <button onClick={fetchAll} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 hover:bg-white/10 transition-all">
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* Error banner */}
            {fetchError && (
                <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
                    <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
                    <p className="text-sm text-red-300">{fetchError}</p>
                    <button onClick={() => { setFetchError(null); fetchAll(); }} className="ml-auto text-xs text-red-400 hover:text-red-200 underline">Retry</button>
                </div>
            )}
            {simError && (
                <div className="flex items-center gap-3 rounded-xl border border-orange-500/30 bg-orange-500/10 px-4 py-3">
                    <AlertTriangle size={14} className="text-orange-400 flex-shrink-0" />
                    <p className="text-sm text-orange-300">{simError}</p>
                    <button onClick={() => setSimError(null)} className="ml-auto text-xs text-orange-400 hover:text-orange-200">✕</button>
                </div>
            )}

            {/* Metrics Row */}
            {metrics && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
                    {[
                        { label: 'Alerts', value: metrics.alerts_processed, color: 'text-slate-300' },
                        { label: 'Incidents', value: metrics.incidents_created, color: 'text-orange-400' },
                        { label: 'Playbooks', value: metrics.playbooks_executed, color: 'text-blue-400' },
                        { label: 'Auto-Contained', value: metrics.auto_contained, color: 'text-emerald-400' },
                        { label: 'Escalated', value: metrics.escalated_to_human, color: 'text-yellow-400' },
                        { label: 'Open', value: metrics.open_incidents, color: 'text-red-400' },
                        { label: 'Critical', value: metrics.critical_incidents, color: 'text-rose-400' },
                        { label: 'Avg MTTR', value: mttrDisplay(metrics.avg_mttr_seconds), color: 'text-cyan-400' },
                    ].map(m => (
                        <div key={m.label} className="rounded-2xl border border-white/10 bg-white/5 p-3 text-center">
                            <p className="text-[10px] uppercase tracking-widest text-slate-500">{m.label}</p>
                            <p className={`text-2xl font-black mt-1 ${m.color}`}>{m.value}</p>
                        </div>
                    ))}
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1">
                {(['dashboard', 'incidents', 'playbooks', 'simulate'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`flex-1 rounded-xl py-2 text-sm font-medium capitalize transition-all ${tab === t ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'text-slate-400 hover:text-slate-200'}`}>
                        {t === 'dashboard' ? 'Overview' : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                ))}
            </div>

            <AnimatePresence mode="wait">

                {/* DASHBOARD */}
                {tab === 'dashboard' && (
                    <motion.div key="dash" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="grid gap-6 lg:grid-cols-2">
                        {/* Open Incidents Feed */}
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <Activity size={16} className="text-red-400" />
                                    <p className="font-semibold text-white">Live Incident Feed</p>
                                </div>
                                <span className="text-xs text-slate-500">Auto-refresh 30s</span>
                            </div>
                            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                {incidents.slice(0, 8).map(inc => (
                                    <div key={inc.id} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/5 p-3">
                                        <span className={`mt-0.5 flex-shrink-0 rounded-lg border px-1.5 py-0.5 text-[9px] font-bold ${SEV_STYLES[inc.severity] ?? ''}`}>{inc.severity}</span>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium text-white truncate">{inc.id}</p>
                                            <p className="text-xs text-slate-400 truncate">{inc.description || inc.threat_name || inc.technique || 'Unknown event'}</p>
                                        </div>
                                        <span className={`flex-shrink-0 rounded-lg px-2 py-0.5 text-[10px] font-semibold ${STATUS_STYLES[inc.status] ?? ''}`}>{inc.status}</span>
                                    </div>
                                ))}
                                {incidents.length === 0 && (
                                    <div className="py-8 text-center text-slate-600">
                                        <CheckCircle2 size={32} className="mx-auto mb-2 text-emerald-700" />
                                        <p>No active incidents</p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* SOC Health */}
                        <div className="space-y-4">
                            <div className="rounded-2xl border border-blue-500/20 bg-gradient-to-br from-blue-500/10 to-transparent p-5">
                                <div className="flex items-center gap-2 mb-4">
                                    <Shield size={16} className="text-blue-400" />
                                    <p className="font-semibold text-white">SOC Operational Health</p>
                                </div>
                                <div className="space-y-3">
                                    {[
                                        { label: 'Auto-Containment Rate', value: metrics ? (metrics.alerts_processed > 0 ? Math.round(metrics.auto_contained / Math.max(metrics.incidents_created, 1) * 100) : 0) : 0, color: 'bg-emerald-500' },
                                        { label: 'Escalation Rate', value: metrics ? (metrics.incidents_created > 0 ? Math.round(metrics.escalated_to_human / Math.max(metrics.incidents_created, 1) * 100) : 0) : 0, color: 'bg-orange-500' },
                                    ].map(m => (
                                        <div key={m.label}>
                                            <div className="flex justify-between mb-1">
                                                <p className="text-xs text-slate-400">{m.label}</p>
                                                <p className="text-xs font-bold text-white">{m.value}%</p>
                                            </div>
                                            <div className="h-2 rounded-full bg-white/5">
                                                <motion.div initial={{ width: 0 }} animate={{ width: `${m.value}%` }} transition={{ duration: 0.8, ease: 'easeOut' }}
                                                    className={`h-2 rounded-full ${m.color}`} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center">
                                    <Timer size={20} className="text-cyan-400 mx-auto mb-2" />
                                    <p className="text-2xl font-black text-cyan-400">{mttrDisplay(metrics?.avg_mttr_seconds)}</p>
                                    <p className="text-xs text-slate-500 mt-1">Avg MTTR</p>
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center">
                                    <Users size={20} className="text-blue-400 mx-auto mb-2" />
                                    <p className="text-2xl font-black text-blue-400">{metrics?.playbook_count ?? 7}</p>
                                    <p className="text-xs text-slate-500 mt-1">Playbooks</p>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* INCIDENTS */}
                {tab === 'incidents' && (
                    <motion.div key="inc" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="flex gap-2 flex-wrap">
                            {(['ALL', 'OPEN', 'INVESTIGATING', 'CONTAINED', 'RESOLVED', 'FALSE_POSITIVE'] as const).map(s => (
                                <button key={s} onClick={() => setStatusFilter(s)}
                                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${statusFilter === s ? 'border-blue-500/40 bg-blue-500/20 text-blue-300' : 'border-white/10 bg-white/5 text-slate-400 hover:text-slate-200'}`}>
                                    {s}
                                </button>
                            ))}
                        </div>
                        <div className="space-y-3">
                            {filteredIncidents.map((inc, i) => (
                                <motion.div key={inc.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                                    className="rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-blue-500/20 transition-all">
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <span className={`rounded-lg border px-2 py-1 text-xs font-bold ${SEV_STYLES[inc.severity] ?? ''}`}>{inc.severity}</span>
                                            <code className="text-sm font-mono text-blue-300">{inc.id}</code>
                                        </div>
                                        <span className={`rounded-lg px-3 py-1 text-xs font-semibold ${STATUS_STYLES[inc.status] ?? ''}`}>{inc.status}</span>
                                    </div>
                                    <p className="text-sm text-slate-300 mb-3">{inc.description || 'No description'}</p>
                                    <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                                        {inc.technique && <span className="rounded border border-orange-500/20 bg-orange-500/10 px-2 py-0.5 text-orange-300 font-mono">{inc.technique}</span>}
                                        {inc.threat_name && <span className="rounded border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-cyan-300">{inc.threat_name}</span>}
                                        {inc.entity_id && <span>Entity: {inc.entity_id}</span>}
                                        <span>Created: {new Date(inc.created_at).toLocaleTimeString()}</span>
                                        {inc.mttr_seconds && <span>MTTR: {mttrDisplay(inc.mttr_seconds)}</span>}
                                        {inc.playbooks_executed?.length > 0 && <span className="text-blue-400">{inc.playbooks_executed.length} playbook(s) run</span>}
                                    </div>
                                    {inc.narrative && (
                                        <div className="mt-3 rounded-xl border border-white/5 bg-white/5 p-3 text-xs text-slate-400 italic">
                                            {inc.narrative}
                                        </div>
                                    )}
                                </motion.div>
                            ))}
                            {filteredIncidents.length === 0 && (
                                <div className="py-16 text-center text-slate-600">
                                    <CheckCircle2 size={40} className="mx-auto mb-3 text-emerald-700" />
                                    <p className="text-slate-400">No incidents with status: {statusFilter}</p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}

                {/* PLAYBOOKS */}
                {tab === 'playbooks' && (
                    <motion.div key="pb" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="grid gap-4 sm:grid-cols-2">
                        {playbooks.map((pb, i) => (
                            <motion.div key={pb.id} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }}
                                className="rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-blue-500/20 hover:bg-blue-500/5 transition-all">
                                <div className="flex items-start justify-between mb-3">
                                    <p className="font-semibold text-white">{pb.name}</p>
                                    <div className="flex gap-2">
                                        {pb.auto_execute && (
                                            <span className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-400">AUTO</span>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-4 text-xs text-slate-500">
                                    <span className="flex items-center gap-1"><Zap size={10} className="text-blue-400" />{pb.action_count} steps</span>
                                    <span className="flex items-center gap-1"><Clock size={10} className="text-orange-400" />
                                        {pb.escalate_after_minutes === 0 ? 'Immediate escalation' : `Escalate after ${pb.escalate_after_minutes}m`}
                                    </span>
                                </div>
                            </motion.div>
                        ))}
                    </motion.div>
                )}

                {/* SIMULATE */}
                {tab === 'simulate' && (
                    <motion.div key="sim" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-6">
                        <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/5 p-4 flex items-center gap-3">
                            <AlertTriangle size={16} className="text-yellow-400 flex-shrink-0" />
                            <p className="text-sm text-yellow-300">Simulation mode — events are real and trigger playbooks, but actions are logged only (no actual host isolation)</p>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {simulationTypes.map(sim => (
                                <button key={sim.value} onClick={() => simulate(sim.value)} disabled={simulating === sim.value}
                                    className="rounded-2xl border border-white/10 bg-white/5 p-5 text-left hover:border-blue-500/30 hover:bg-blue-500/5 transition-all disabled:opacity-50">
                                    <div className="flex items-center justify-between mb-3">
                                        <Play size={16} className="text-blue-400" />
                                        {simulating === sim.value && <span className="animate-spin text-blue-400">⟳</span>}
                                    </div>
                                    <p className="font-semibold text-white capitalize">{sim.label || sim.value.replace(/_/g, ' ')}</p>
                                    <p className="text-xs text-slate-500 mt-1">
                                        {sim.description || sim.severity || 'Triggers SOC playbook sequence'}
                                    </p>
                                </button>
                            ))}
                        </div>
                        {simResult && (
                            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6">
                                <div className="flex items-center gap-2 mb-4">
                                    <TrendingUp size={16} className="text-blue-400" />
                                    <p className="font-semibold text-white">Simulation Result — {simResult.threat_type.replace(/_/g, ' ')}</p>
                                </div>
                                {simResult.incident && (
                                    <div className="space-y-2 mb-4">
                                        <div className="flex items-center gap-3">
                                            <code className="text-sm font-mono text-blue-300">{simResult.incident.id}</code>
                                            <span className={`rounded-lg border px-2 py-0.5 text-xs font-bold ${SEV_STYLES[simResult.incident.severity] ?? ''}`}>{simResult.incident.severity}</span>
                                            <span className={`rounded-lg px-2 py-0.5 text-xs ${STATUS_STYLES[simResult.incident.status] ?? ''}`}>{simResult.incident.status}</span>
                                        </div>
                                        {simResult.incident.playbooks_executed?.length > 0 && (
                                            <p className="text-sm text-emerald-400">✓ Playbooks executed: {simResult.incident.playbooks_executed.join(', ')}</p>
                                        )}
                                    </div>
                                )}
                                {simResult.playbook_result && (
                                    <pre className="rounded-xl bg-slate-900/80 p-4 text-xs text-slate-300 overflow-x-auto">
                                        {JSON.stringify(simResult.playbook_result, null, 2)}
                                    </pre>
                                )}
                            </motion.div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
