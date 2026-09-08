'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Brain, RefreshCw, Shield, AlertTriangle, Zap, Globe,
    ChevronRight, Radio, Database, Eye, Target, TrendingUp, Filter
} from 'lucide-react';

const API = '/api/v1/intel';

interface ThreatRule { id: string; name: string; severity: string; source: string; region?: string; action: string; techniques?: string[]; }
interface LandscapeThreat { id: string; name: string; region: string; severity: string; description: string; targets: string[]; techniques: string[]; indicators: string[]; }
interface ScanResult { threat_score: number; action: string; matches: { category: string; severity: string; technique?: string; threat_name?: string; region?: string }[]; total_matches: number; rules_active: number; }

const SEV_COLOR: Record<string, string> = {
    CRITICAL: 'text-red-400 bg-red-500/10 border-red-500/30',
    HIGH: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    MEDIUM: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    LOW: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
};
const ACTION_COLOR: Record<string, string> = {
    BLOCK: 'text-red-400', FLAG: 'text-yellow-400', PASS: 'text-emerald-400',
};

export default function AdversarialIntelPage() {
    const [tab, setTab] = useState<'landscape' | 'scanner' | 'rules' | 'stix'>('landscape');
    const [landscape, setLandscape] = useState<{ threats: LandscapeThreat[]; active_rules: number } | null>(null);
    const [rules, setRules] = useState<ThreatRule[]>([]);
    const [scanText, setScanText] = useState('');
    const [scanResult, setScanResult] = useState<ScanResult | null>(null);
    const [scanning, setScanning] = useState(false);
    const [stixStatus, setStixStatus] = useState<{ pulling: boolean; result: string | null }>({ pulling: false, result: null });
    const [loading, setLoading] = useState(false);
    const [filterSev, setFilterSev] = useState('ALL');

    const fetchLandscape = useCallback(async () => {
        setLoading(true);
        try {
            const r = await fetch(`${API}/adversarial/landscape`);
            if (r.ok) setLandscape(await r.json());
        } catch { } finally { setLoading(false); }
    }, []);

    const fetchRules = useCallback(async () => {
        try {
            const r = await fetch(`${API}/adversarial/rules`);
            if (r.ok) { const d = await r.json(); setRules(d.rules || []); }
        } catch { }
    }, []);

    useEffect(() => { fetchLandscape(); fetchRules(); }, [fetchLandscape, fetchRules]);

    const runScan = async () => {
        if (!scanText.trim()) return;
        setScanning(true); setScanResult(null);
        try {
            const r = await fetch(`${API}/adversarial/scan`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: scanText, entity_id: 'analyst-session' }),
            });
            if (r.ok) setScanResult(await r.json());
        } catch { } finally { setScanning(false); }
    };

    const triggerStix = async () => {
        setStixStatus({ pulling: true, result: null });
        try {
            const r = await fetch(`${API}/adversarial/stix/pull`, { method: 'POST' });
            const d = await r.json();
            setStixStatus({ pulling: false, result: d.message });
            setTimeout(fetchRules, 5000);
        } catch (e: unknown) {
            setStixStatus({ pulling: false, result: 'Pull failed: ' + String(e) });
        }
    };

    const filteredRules = filterSev === 'ALL' ? rules : rules.filter(r => r.severity === filterSev);
    const localRules = rules.filter(r => r.source === 'local_ke_threat_db');
    const mitreRules = rules.filter(r => r.source === 'mitre_attack_stix');

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500/30 to-indigo-600/20 border border-purple-500/20">
                        <Brain size={22} className="text-purple-300" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Adversarial Intelligence</h1>
                        <p className="text-sm text-slate-400">STIX/TAXII 2.1 · East African Threat Landscape · Dynamic Rule Engine</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className="rounded-xl border border-purple-500/20 bg-purple-500/10 px-4 py-2 text-xs font-mono text-purple-300">
                        {rules.length} active rules
                    </div>
                    <button onClick={fetchLandscape} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 hover:bg-white/10 transition-all">
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
                    </button>
                </div>
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                    { label: 'EAC Threats', value: landscape?.threats?.length ?? 7, icon: Target, color: 'text-red-400', bg: 'from-red-500/10 to-rose-500/5 border-red-500/20' },
                    { label: 'MITRE Rules', value: mitreRules.length, icon: Database, color: 'text-orange-400', bg: 'from-orange-500/10 to-amber-500/5 border-orange-500/20' },
                    { label: 'Local Rules', value: localRules.length, icon: Globe, color: 'text-cyan-400', bg: 'from-cyan-500/10 to-sky-500/5 border-cyan-500/20' },
                    { label: 'Total Active', value: rules.length || landscape?.active_rules || 0, icon: Shield, color: 'text-emerald-400', bg: 'from-emerald-500/10 to-teal-500/5 border-emerald-500/20' },
                ].map(m => (
                    <motion.div key={m.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                        className={`rounded-2xl border bg-gradient-to-br p-4 ${m.bg}`}>
                        <div className="flex items-center justify-between mb-2">
                            <p className="text-xs text-slate-400 uppercase tracking-widest">{m.label}</p>
                            <m.icon size={16} className={m.color} />
                        </div>
                        <p className={`text-3xl font-black ${m.color}`}>{m.value}</p>
                    </motion.div>
                ))}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1">
                {(['landscape', 'scanner', 'rules', 'stix'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`flex-1 rounded-xl py-2 text-sm font-medium capitalize transition-all ${tab === t ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'text-slate-400 hover:text-slate-200'}`}>
                        {t === 'stix' ? 'STIX Pull' : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                ))}
            </div>

            <AnimatePresence mode="wait">

                {/* LANDSCAPE TAB */}
                {tab === 'landscape' && (
                    <motion.div key="landscape" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-500/5 to-transparent p-5">
                            <div className="flex items-center gap-2 mb-1">
                                <Radio size={14} className="text-cyan-400 animate-pulse" />
                                <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">East African Threat Landscape</p>
                            </div>
                            <p className="text-xs text-slate-500">Based on KE-CIRT/CC advisories · INTERPOL Africa · Serianu Cyber Threat Intelligence 2023–2025</p>
                        </div>
                        <div className="grid gap-4 lg:grid-cols-2">
                            {(landscape?.threats ?? []).map((threat, i) => (
                                <motion.div key={threat.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
                                    className="rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all">
                                    <div className="flex items-start justify-between mb-3">
                                        <div>
                                            <p className="font-semibold text-white">{threat.name}</p>
                                            <p className="text-xs text-slate-400 mt-0.5">{threat.region}</p>
                                        </div>
                                        <span className={`rounded-lg border px-2 py-1 text-xs font-bold ${SEV_COLOR[threat.severity] ?? SEV_COLOR.LOW}`}>
                                            {threat.severity}
                                        </span>
                                    </div>
                                    <p className="text-sm text-slate-400 mb-3">{threat.description}</p>
                                    <div className="flex flex-wrap gap-1 mb-2">
                                        {threat.techniques.map(t => (
                                            <span key={t} className="rounded border border-orange-500/20 bg-orange-500/10 px-2 py-0.5 text-[10px] font-mono text-orange-300">{t}</span>
                                        ))}
                                    </div>
                                    <div className="flex flex-wrap gap-1">
                                        {threat.targets.map(t => (
                                            <span key={t} className="rounded border border-slate-500/20 bg-slate-500/10 px-2 py-0.5 text-[10px] text-slate-400">{t}</span>
                                        ))}
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* SCANNER TAB */}
                {tab === 'scanner' && (
                    <motion.div key="scanner" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                            <div className="flex items-center gap-2 mb-4">
                                <Eye size={16} className="text-purple-400" />
                                <p className="font-semibold text-white">Adversarial Pattern Scanner</p>
                            </div>
                            <textarea value={scanText} onChange={e => setScanText(e.target.value)}
                                placeholder="Paste text, prompt, email body, or user input to analyze for adversarial patterns…"
                                className="w-full h-36 rounded-xl border border-white/10 bg-slate-900/60 p-4 text-sm text-slate-200 placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none resize-none" />
                            <button onClick={runScan} disabled={scanning || !scanText.trim()}
                                className="mt-3 flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-40 transition-all">
                                <Zap size={14} className={scanning ? 'animate-pulse' : ''} />
                                {scanning ? 'Scanning…' : 'Run Adversarial Scan'}
                            </button>
                        </div>

                        {scanResult && (
                            <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                                className={`rounded-2xl border p-6 ${scanResult.action === 'BLOCK' ? 'border-red-500/40 bg-red-500/5' : scanResult.action === 'FLAG' ? 'border-yellow-500/40 bg-yellow-500/5' : 'border-emerald-500/40 bg-emerald-500/5'}`}>
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <div className={`text-4xl font-black ${ACTION_COLOR[scanResult.action]}`}>{scanResult.action}</div>
                                        <div>
                                            <p className="text-slate-300 text-sm">Threat Score: <span className="font-bold text-white">{(scanResult.threat_score * 100).toFixed(1)}%</span></p>
                                            <p className="text-slate-500 text-xs">{scanResult.total_matches} patterns matched · {scanResult.rules_active} rules active</p>
                                        </div>
                                    </div>
                                    {/* Score gauge */}
                                    <div className="relative h-16 w-16">
                                        <svg viewBox="0 0 36 36" className="h-16 w-16 -rotate-90">
                                            <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                                            <circle cx="18" cy="18" r="15.9" fill="none"
                                                stroke={scanResult.action === 'BLOCK' ? '#f87171' : scanResult.action === 'FLAG' ? '#facc15' : '#4ade80'}
                                                strokeWidth="3" strokeDasharray={`${scanResult.threat_score * 100} 100`} strokeLinecap="round" />
                                        </svg>
                                    </div>
                                </div>
                                {scanResult.matches.length > 0 && (
                                    <div className="space-y-2">
                                        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-2">Matched Patterns</p>
                                        {scanResult.matches.map((m, i) => (
                                            <div key={i} className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/5 px-4 py-3">
                                                <AlertTriangle size={14} className={SEV_COLOR[m.severity]?.split(' ')[0] ?? 'text-slate-400'} />
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium text-white">{m.threat_name ?? m.category}</p>
                                                    {m.region && <p className="text-xs text-slate-500">{m.region}</p>}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {m.technique && <span className="rounded border border-orange-500/20 bg-orange-500/10 px-2 py-0.5 text-[10px] font-mono text-orange-300">{m.technique}</span>}
                                                    <span className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold ${SEV_COLOR[m.severity] ?? ''}`}>{m.severity}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </motion.div>
                )}

                {/* RULES TAB */}
                {tab === 'rules' && (
                    <motion.div key="rules" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="flex items-center gap-3">
                            <Filter size={14} className="text-slate-400" />
                            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'] as const).map(s => (
                                <button key={s} onClick={() => setFilterSev(s)}
                                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${filterSev === s ? 'border-purple-500/40 bg-purple-500/20 text-purple-300' : 'border-white/10 bg-white/5 text-slate-400 hover:text-slate-200'}`}>
                                    {s}
                                </button>
                            ))}
                            <span className="ml-auto text-xs text-slate-500">{filteredRules.length} rules</span>
                        </div>
                        <div className="space-y-2">
                            {filteredRules.slice(0, 50).map((rule, i) => (
                                <motion.div key={rule.id} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.02 }}
                                    className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/5 px-4 py-3 hover:border-purple-500/20 hover:bg-purple-500/5 transition-all">
                                    <span className={`rounded-lg border px-2 py-0.5 text-[10px] font-bold ${SEV_COLOR[rule.severity] ?? SEV_COLOR.LOW}`}>{rule.severity}</span>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate">{rule.name}</p>
                                        <p className="text-xs text-slate-500">{rule.source === 'local_ke_threat_db' ? '🇰🇪 Kenya/EAC Threat DB' : '🌐 MITRE ATT&CK STIX'}</p>
                                    </div>
                                    <span className={`text-xs font-semibold ${ACTION_COLOR[rule.action] ?? 'text-slate-400'}`}>{rule.action}</span>
                                    <ChevronRight size={14} className="text-slate-600" />
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>
                )}

                {/* STIX PULL TAB */}
                {tab === 'stix' && (
                    <motion.div key="stix" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-500/10 to-transparent p-8 text-center">
                            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10 border border-indigo-500/20">
                                <Database size={28} className="text-indigo-400" />
                            </div>
                            <h2 className="text-xl font-bold text-white mb-2">Live STIX/TAXII Pull</h2>
                            <p className="text-sm text-slate-400 max-w-md mx-auto mb-6">
                                Pull live threat intelligence from MITRE ATT&CK TAXII 2.1 server.
                                Generates dynamic firewall rules from the full enterprise attack framework (~800 techniques).
                            </p>
                            <div className="flex items-center justify-center gap-4 flex-wrap mb-6">
                                {[['Source', 'MITRE ATT&CK TAXII 2.1'], ['Format', 'STIX 2.1 Bundle'], ['Coverage', '~800 techniques'], ['Update', 'On-demand pull']].map(([k, v]) => (
                                    <div key={k} className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-center">
                                        <p className="text-[10px] uppercase tracking-widest text-slate-500">{k}</p>
                                        <p className="text-sm font-medium text-white mt-1">{v}</p>
                                    </div>
                                ))}
                            </div>
                            <button onClick={triggerStix} disabled={stixStatus.pulling}
                                className="flex items-center gap-2 mx-auto rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-8 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all">
                                <TrendingUp size={16} className={stixStatus.pulling ? 'animate-pulse' : ''} />
                                {stixStatus.pulling ? 'Pulling from MITRE ATT&CK…' : 'Pull Live STIX Feed'}
                            </button>
                            {stixStatus.result && (
                                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                    className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                                    {stixStatus.result}
                                </motion.p>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">Local KE Rules</p>
                                <p className="text-4xl font-black text-cyan-400">{localRules.length}</p>
                                <p className="text-xs text-slate-500 mt-1">KE-CIRT/CC · INTERPOL Africa</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">MITRE Rules</p>
                                <p className="text-4xl font-black text-orange-400">{mitreRules.length}</p>
                                <p className="text-xs text-slate-500 mt-1">{mitreRules.length === 0 ? 'Pull to populate' : 'Techniques ingested'}</p>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
