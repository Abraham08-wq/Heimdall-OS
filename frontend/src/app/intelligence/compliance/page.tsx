'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ClipboardCheck, RefreshCw, Shield, AlertTriangle, CheckCircle2,
    FileText, Plus, Upload, Lock, ChevronRight, TrendingUp, AlertCircle
} from 'lucide-react';

const API = '/api/v1/intel';

interface Framework { id: string; name: string; authority: string; jurisdiction: string; mandatory: boolean; control_count: number; }
interface PostureEntry { framework_name: string; jurisdiction: string; mandatory: boolean; score_percent: number; controls_total: number; controls_assessed: number; controls_compliant: number; controls_failing: string[]; posture: string; }
interface Gap { framework: string; framework_name: string; control_id: string; control_title: string; status: string; current_score: number; max_score: number; priority_score: number; mandatory_framework: boolean; evidence_required: string[]; evidence_count: number; remediation: string; }
interface AuditEntry { seq: number; timestamp: string; event_type: string; entity: string; user: string; hash: string; }

const POSTURE_STYLE: Record<string, string> = {
    COMPLIANT: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    PARTIALLY_COMPLIANT: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
    NON_COMPLIANT: 'text-red-400 border-red-500/30 bg-red-500/10',
};

const FW_COLORS: Record<string, string> = {
    KE_DPA_2019: 'from-green-500/20 to-emerald-500/10 border-green-500/20',
    CBK_CYBERSECURITY_2023: 'from-red-500/20 to-rose-500/10 border-red-500/20',
    ISO_27001_2022: 'from-blue-500/20 to-indigo-500/10 border-blue-500/20',
    GDPR: 'from-purple-500/20 to-violet-500/10 border-purple-500/20',
    PCI_DSS_V4: 'from-orange-500/20 to-amber-500/10 border-orange-500/20',
};

export default function ComplianceEnginePage() {
    const [tab, setTab] = useState<'posture' | 'gaps' | 'assess' | 'audit'>('posture');
    const [frameworks, setFrameworks] = useState<Framework[]>([]);
    const [posture, setPosture] = useState<Record<string, PostureEntry>>({});
    const [gaps, setGaps] = useState<Gap[]>([]);
    const [auditLog, setAuditLog] = useState<{ entries: AuditEntry[]; integrity: string } | null>(null);
    const [loading, setLoading] = useState(false);
    const [collecting, setCollecting] = useState(false);
    const [showGapFilter, setShowGapFilter] = useState('ALL');

    // Assess form state
    const [assessForm, setAssessForm] = useState({ framework_id: 'KE_DPA_2019', control_id: 'DPA-01', status: 'COMPLIANT', score: 80, reviewer: 'auditor@projectxy.io', notes: '' });
    const [assessResult, setAssessResult] = useState<string | null>(null);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [fw, pos, g, al] = await Promise.all([
                fetch(`${API}/compliance/frameworks`).then(r => r.ok ? r.json() : null),
                fetch(`${API}/compliance/posture`).then(r => r.ok ? r.json() : null),
                fetch(`${API}/compliance/gaps`).then(r => r.ok ? r.json() : null),
                fetch(`${API}/compliance/audit-log?limit=20`).then(r => r.ok ? r.json() : null),
            ]);
            if (fw) setFrameworks(fw.frameworks ?? []);
            if (pos) setPosture(pos);
            if (g) setGaps(g.gaps ?? []);
            if (al) setAuditLog(al);
        } catch { } finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const collectEvidence = async () => {
        setCollecting(true);
        try {
            await fetch(`${API}/compliance/collect-evidence`, { method: 'POST' });
            setTimeout(fetchAll, 3000);
        } catch { } finally { setCollecting(false); }
    };

    const submitAssessment = async () => {
        try {
            const r = await fetch(`${API}/compliance/assess`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...assessForm }),
            });
            if (r.ok) { setAssessResult('✓ Assessment recorded successfully'); await fetchAll(); }
            else setAssessResult('Error: ' + (await r.text()));
        } catch (e: unknown) { setAssessResult('Error: ' + String(e)); }
    };

    const filteredGaps = showGapFilter === 'ALL' ? gaps
        : showGapFilter === 'MANDATORY' ? gaps.filter(g => g.mandatory_framework)
            : gaps.filter(g => g.framework === showGapFilter);

    const overallScore = Object.values(posture).length > 0
        ? Math.round(Object.values(posture).reduce((acc, p) => acc + p.score_percent, 0) / Object.values(posture).length)
        : 0;

    const compliantCount = Object.values(posture).filter(p => p.posture === 'COMPLIANT').length;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500/30 to-teal-600/20 border border-emerald-500/20">
                        <ClipboardCheck size={22} className="text-emerald-300" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Compliance Engine</h1>
                        <p className="text-sm text-slate-400">Kenya DPA 2019 · CBK 2023 · ISO 27001 · GDPR · PCI-DSS v4</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button onClick={collectEvidence} disabled={collecting}
                        className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50 transition-all">
                        <Upload size={14} className={collecting ? 'animate-bounce' : ''} />
                        {collecting ? 'Collecting…' : 'Auto-Collect Evidence'}
                    </button>
                    <button onClick={fetchAll} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 hover:bg-white/10 transition-all">
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* Overall Score */}
            <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-teal-500/5 p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs uppercase tracking-widest text-slate-500 mb-1">Overall Compliance Posture</p>
                        <div className="flex items-end gap-4">
                            <p className="text-6xl font-black text-emerald-400">{overallScore}%</p>
                            <div>
                                <p className="text-slate-300 font-medium">{compliantCount}/{frameworks.length} frameworks compliant</p>
                                <p className="text-slate-500 text-sm">{gaps.filter(g => g.mandatory_framework && g.priority_score >= 16).length} critical gaps require immediate action</p>
                            </div>
                        </div>
                    </div>
                    <div className="relative h-24 w-24">
                        <svg viewBox="0 0 36 36" className="h-24 w-24 -rotate-90">
                            <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                            <motion.circle cx="18" cy="18" r="15.9" fill="none" stroke="#34d399"
                                strokeWidth="3" initial={{ strokeDasharray: '0 100' }}
                                animate={{ strokeDasharray: `${overallScore} 100` }}
                                transition={{ duration: 1.2, ease: 'easeOut' }}
                                strokeLinecap="round" />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <Shield size={24} className="text-emerald-400" />
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 rounded-2xl border border-white/10 bg-white/5 p-1">
                {(['posture', 'gaps', 'assess', 'audit'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`flex-1 rounded-xl py-2 text-sm font-medium capitalize transition-all ${tab === t ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200'}`}>
                        {t === 'assess' ? 'Assess Control' : t === 'audit' ? 'Audit Trail' : t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                ))}
            </div>

            <AnimatePresence mode="wait">

                {/* POSTURE */}
                {tab === 'posture' && (
                    <motion.div key="pos" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="grid gap-4 lg:grid-cols-2">
                        {Object.entries(posture).map(([fwId, fw], i) => (
                            <motion.div key={fwId} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.07 }}
                                className={`rounded-2xl border bg-gradient-to-br p-5 ${FW_COLORS[fwId] ?? 'from-slate-500/10 to-transparent border-slate-500/20'}`}>
                                <div className="flex items-start justify-between mb-4">
                                    <div>
                                        <p className="font-semibold text-white">{fw.framework_name}</p>
                                        <p className="text-xs text-slate-400 mt-0.5">{fw.jurisdiction}</p>
                                        {fw.mandatory && <span className="mt-1 inline-flex rounded border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-bold text-red-400 uppercase">Mandatory</span>}
                                    </div>
                                    <span className={`rounded-xl border px-3 py-1 text-xs font-bold ${POSTURE_STYLE[fw.posture] ?? ''}`}>{fw.posture.replace(/_/g, ' ')}</span>
                                </div>
                                <div className="mb-3">
                                    <div className="flex justify-between mb-1">
                                        <span className="text-xs text-slate-500">Score</span>
                                        <span className="text-xs font-bold text-white">{fw.score_percent}%</span>
                                    </div>
                                    <div className="h-2 rounded-full bg-white/5">
                                        <motion.div initial={{ width: 0 }} animate={{ width: `${fw.score_percent}%` }} transition={{ duration: 0.9, ease: 'easeOut', delay: i * 0.1 }}
                                            className={`h-2 rounded-full ${fw.score_percent >= 85 ? 'bg-emerald-500' : fw.score_percent >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`} />
                                    </div>
                                </div>
                                <div className="flex gap-4 text-xs text-slate-500">
                                    <span>{fw.controls_total} controls</span>
                                    <span className="text-emerald-400">{fw.controls_compliant} compliant</span>
                                    <span>{fw.controls_assessed} assessed</span>
                                    {fw.controls_failing.length > 0 && <span className="text-red-400">{fw.controls_failing.length} failing</span>}
                                </div>
                            </motion.div>
                        ))}
                    </motion.div>
                )}

                {/* GAPS */}
                {tab === 'gaps' && (
                    <motion.div key="gaps" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        <div className="flex items-center gap-3 flex-wrap">
                            {['ALL', 'MANDATORY', ...frameworks.map(f => f.id)].map(f => (
                                <button key={f} onClick={() => setShowGapFilter(f)}
                                    className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${showGapFilter === f ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300' : 'border-white/10 bg-white/5 text-slate-400 hover:text-slate-200'}`}>
                                    {f === 'ALL' ? 'All Gaps' : f === 'MANDATORY' ? '⚠ Mandatory Only' : f.replace(/_/g, ' ')}
                                </button>
                            ))}
                            <span className="ml-auto text-xs text-slate-500">{filteredGaps.length} gaps</span>
                        </div>
                        <div className="space-y-3">
                            {filteredGaps.map((gap, i) => (
                                <motion.div key={`${gap.framework}-${gap.control_id}`} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                                    className={`rounded-2xl border p-5 ${gap.mandatory_framework && gap.priority_score >= 16 ? 'border-red-500/20 bg-red-500/5' : 'border-white/10 bg-white/5'} hover:border-emerald-500/20 transition-all`}>
                                    <div className="flex items-start justify-between mb-3">
                                        <div>
                                            <div className="flex items-center gap-2 flex-wrap mb-1">
                                                <span className="text-xs font-mono text-emerald-400">{gap.framework}:{gap.control_id}</span>
                                                {gap.mandatory_framework && <span className="rounded border border-red-500/20 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-bold text-red-400">MANDATORY</span>}
                                                {gap.priority_score >= 16 && <span className="rounded border border-orange-500/20 bg-orange-500/10 px-1.5 py-0.5 text-[9px] font-bold text-orange-400">CRITICAL GAP</span>}
                                            </div>
                                            <p className="font-semibold text-white">{gap.control_title}</p>
                                        </div>
                                        <div className="text-right text-xs">
                                            <p className="text-slate-300 font-bold">{gap.current_score}/{gap.max_score}</p>
                                            <p className="text-slate-500">Priority: {gap.priority_score}</p>
                                        </div>
                                    </div>
                                    <div className="rounded-xl border border-yellow-500/10 bg-yellow-500/5 p-3 mb-3">
                                        <div className="flex items-start gap-2">
                                            <AlertCircle size={12} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                                            <p className="text-xs text-yellow-300">{gap.remediation}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3 flex-wrap">
                                        <p className="text-xs text-slate-500">Evidence required:</p>
                                        {gap.evidence_required.map(e => (
                                            <span key={e} className={`rounded border px-2 py-0.5 text-[10px] ${gap.evidence_count > 0 ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' : 'border-slate-500/20 bg-slate-500/10 text-slate-400'}`}>
                                                {gap.evidence_count > 0 && '✓ '}{e}
                                            </span>
                                        ))}
                                    </div>
                                </motion.div>
                            ))}
                            {filteredGaps.length === 0 && (
                                <div className="py-16 text-center">
                                    <CheckCircle2 size={40} className="mx-auto mb-3 text-emerald-600" />
                                    <p className="text-slate-400">No gaps found for selected filter</p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}

                {/* ASSESS */}
                {tab === 'assess' && (
                    <motion.div key="assess" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="max-w-2xl space-y-5">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                            <div className="flex items-center gap-2 mb-5">
                                <Plus size={16} className="text-emerald-400" />
                                <p className="font-semibold text-white">Submit Control Assessment</p>
                            </div>
                            <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Framework</label>
                                        <select value={assessForm.framework_id} onChange={e => setAssessForm(f => ({ ...f, framework_id: e.target.value }))}
                                            className="w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500/50 focus:outline-none">
                                            {frameworks.map(fw => <option key={fw.id} value={fw.id}>{fw.id}</option>)}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Control ID</label>
                                        <input value={assessForm.control_id} onChange={e => setAssessForm(f => ({ ...f, control_id: e.target.value }))}
                                            className="w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500/50 focus:outline-none"
                                            placeholder="e.g. DPA-01" />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Status</label>
                                        <select value={assessForm.status} onChange={e => setAssessForm(f => ({ ...f, status: e.target.value }))}
                                            className="w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500/50 focus:outline-none">
                                            {['COMPLIANT', 'NON_COMPLIANT', 'PARTIAL', 'NOT_ASSESSED'].map(s => <option key={s} value={s}>{s}</option>)}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Score (0-100)</label>
                                        <input type="number" min={0} max={100} value={assessForm.score} onChange={e => setAssessForm(f => ({ ...f, score: Number(e.target.value) }))}
                                            className="w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500/50 focus:outline-none" />
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Reviewer</label>
                                    <input value={assessForm.reviewer} onChange={e => setAssessForm(f => ({ ...f, reviewer: e.target.value }))}
                                        className="w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500/50 focus:outline-none"
                                        placeholder="reviewer@company.com" />
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-400 mb-2 uppercase tracking-widest">Notes</label>
                                    <textarea value={assessForm.notes} onChange={e => setAssessForm(f => ({ ...f, notes: e.target.value }))}
                                        className="w-full h-20 rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none resize-none"
                                        placeholder="Assessment notes, findings, observations…" />
                                </div>
                                <button onClick={submitAssessment}
                                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-3 text-sm font-semibold text-white hover:opacity-90 transition-all">
                                    <Shield size={16} /> Submit Assessment
                                </button>
                                {assessResult && (
                                    <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                        className={`rounded-xl border px-4 py-3 text-sm ${assessResult.startsWith('✓') ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}>
                                        {assessResult}
                                    </motion.p>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* AUDIT TRAIL */}
                {tab === 'audit' && (
                    <motion.div key="audit" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-4">
                        {auditLog && (
                            <div className={`flex items-center gap-3 rounded-2xl border p-4 ${auditLog.integrity === 'VALID' ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
                                <Lock size={16} className={auditLog.integrity === 'VALID' ? 'text-emerald-400' : 'text-red-400'} />
                                <div>
                                    <p className="text-sm font-semibold text-white">Hash Chain Integrity: {auditLog.integrity}</p>
                                    <p className="text-xs text-slate-400">SHA-256 chained entries · tamper-evident · {auditLog.entries.length} entries shown</p>
                                </div>
                            </div>
                        )}
                        <div className="space-y-2">
                            {(auditLog?.entries ?? []).map((entry, i) => (
                                <motion.div key={entry.seq} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                                    className="flex items-start gap-4 rounded-xl border border-white/5 bg-white/5 px-4 py-3 font-mono text-xs">
                                    <span className="text-slate-600">#{entry.seq}</span>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-3 flex-wrap">
                                            <span className="text-emerald-400 font-semibold">{entry.event_type}</span>
                                            <span className="text-slate-300">{entry.entity}</span>
                                            <span className="text-slate-500">by {entry.user}</span>
                                        </div>
                                        <p className="text-slate-600 mt-0.5 truncate">{entry.hash}</p>
                                    </div>
                                    <span className="text-slate-600 flex-shrink-0">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                                </motion.div>
                            ))}
                            {!auditLog?.entries?.length && (
                                <div className="py-16 text-center text-slate-600">
                                    <FileText size={40} className="mx-auto mb-3" />
                                    <p>No audit entries yet. Assess a control to create entries.</p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
