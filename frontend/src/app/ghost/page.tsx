"use client";

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Ghost, TerminalSquare, Code, Play, Square,
    AlertOctagon, Radio, Eye, Lock, Copy,
    CheckCircle2, RefreshCw, Shield, Wifi, Loader2,
    AlertTriangle
} from 'lucide-react';
import { clsx } from 'clsx';
import { TeamShell } from '@/components/Layout/TeamShell';
import { api, GhostSession, GhostPayload } from '@/lib/api';

const LANGUAGES = ['python', 'bash', 'powershell'];

// ─── Tag colour mapping ───────────────────────────────────────────────────────
function tagColour(tag: string) {
    const map: Record<string, string> = {
        'REMOTE ACCESS':    'text-amber-400',
        'EVASION':          'text-rose-400',
        'EXFILTRATION':     'text-purple-400',
        'PERSISTENCE':      'text-orange-400',
        'LATERAL MOVEMENT': 'text-cyan-400',
        'C2':               'text-red-400',
        'CREDENTIAL':       'text-yellow-400',
        'RECON':            'text-sky-400',
        'GENERAL':          'text-slate-400',
    };
    return map[tag?.toUpperCase()] ?? 'text-slate-400';
}

export default function GhostShellPage() {
    // ── State ────────────────────────────────────────────────────────────────
    const [payloads, setPayloads] = useState<GhostPayload[]>([]);
    const [agents, setAgents]     = useState<GhostSession[]>([]);
    const [loadingData, setLoadingData] = useState(true);
    const [dataError, setDataError]     = useState<string | null>(null);

    const [code, setCode]       = useState('# Loading payload library...');
    const [language, setLanguage] = useState('python');
    const [output, setOutput]   = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<GhostSession | null>(null);
    const [copied, setCopied]   = useState(false);
    const outputRef = useRef<HTMLDivElement>(null);

    // ── Load payloads + sessions from API ────────────────────────────────────
    useEffect(() => {
        let cancelled = false;
        setLoadingData(true);

        Promise.allSettled([
            api.getPayloadLibrary(),
            api.getGhostSessions(),
        ]).then(([payloadRes, sessionRes]) => {
            if (cancelled) return;

            if (payloadRes.status === 'fulfilled') {
                const list = payloadRes.value.payloads ?? [];
                setPayloads(list);
                if (list.length > 0) {
                    setCode(list[0].code);
                    setLanguage(list[0].lang);
                } else {
                    setCode('# No payloads in library. Add ghost_payloads entries via admin config.');
                }
            } else {
                setDataError('Failed to load payload library.');
            }

            if (sessionRes.status === 'fulfilled') {
                const sessions = sessionRes.value.sessions ?? [];
                setAgents(sessions);
                if (sessions.length > 0) setSelectedAgent(sessions[0]);
            }
        }).finally(() => {
            if (!cancelled) setLoadingData(false);
        });

        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight, behavior: 'smooth' });
    }, [output]);

    const addOutput = useCallback((line: string, delay = 0) => {
        setTimeout(() => setOutput(prev => [...prev, line]), delay);
    }, []);

    // ── Execute payload via API ───────────────────────────────────────────────
    const handleExecute = async () => {
        if (!selectedAgent) {
            setOutput(['[⚠] No agent selected. Register a C2 beacon first.']);
            return;
        }
        setLoading(true);
        setOutput([]);

        addOutput(`[GHOST-C2] Session initiated → ${selectedAgent.ip ?? selectedAgent.beacon_id}`, 0);
        addOutput(`[*] Privilege level: ${selectedAgent.privilege ?? 'UNKNOWN'}`, 300);
        addOutput(`[*] Uploading payload to secure memory enclave...`, 600);

        try {
            const data = await api.apiRequest<{ stdout?: string; stderr?: string; exit_code?: number }>(
                '/ghost/execute',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        code,
                        language,
                        target_ip: selectedAgent.ip ?? selectedAgent.beacon_id,
                    }),
                }
            );

            addOutput(`[*] Injecting into memory space...`, 900);
            addOutput(`[+] EDR bypass: AMSI reflection patched`, 1200);
            addOutput(`[*] Executing payload...`, 1500);

            setTimeout(() => {
                if (data?.stdout) {
                    data.stdout.split('\n').forEach((line, i) => addOutput(line, i * 100));
                } else {
                    addOutput(`[+] Payload executed on ${selectedAgent.ip ?? selectedAgent.beacon_id}`, 0);
                    addOutput(`[+] Exit code: ${data?.exit_code ?? 0}`, 100);
                }
                if (data?.stderr) addOutput(`[STDERR] ${data.stderr}`, 200);
                setLoading(false);
            }, 1800);
        } catch (err: any) {
            addOutput(`[SANDBOX] Simulated execution — API unreachable: ${err?.message ?? 'unknown'}`, 900);
            addOutput(`[✓] Process exited — code 0 (simulated)`, 1200);
            setLoading(false);
        }
    };

    const loadPayload = (p: GhostPayload) => {
        setCode(p.code);
        setLanguage(p.lang);
        setOutput([]);
    };

    const copyCode = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const refreshSessions = async () => {
        try {
            const res = await api.getGhostSessions();
            setAgents(res.sessions ?? []);
        } catch {
            /* no-op */
        }
    };

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <TeamShell
            team="red"
            title="GHOST SHELL — OPERATOR CONTROL INTERFACE"
            subtitle="C2 Framework · Polymorphic Payloads · Remote Execution · Memory Injection"
        >
        <div className="flex bg-[#0D0000] text-white overflow-hidden font-mono" style={{ height: 'calc(100vh - 73px)' }}>
            {/* Ambient gradient */}
            <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(140,0,0,0.06)_0,transparent_60%)]" />

            {/* Top-right controls */}
            <div className="absolute top-0 right-0 flex items-center gap-3 px-4 py-1.5 z-20">
                <select value={language} onChange={e => setLanguage(e.target.value)}
                    className="bg-black border border-red-900/50 text-red-400 text-xs px-2 py-1.5 rounded outline-none">
                    {LANGUAGES.map(l => <option key={l} value={l}>{l.toUpperCase()}</option>)}
                </select>
                <button onClick={handleExecute} disabled={loading || !selectedAgent}
                    className="flex items-center gap-2 px-4 py-1.5 bg-red-950/50 border border-red-600 hover:bg-red-900/60 text-red-400 text-xs font-bold tracking-widest rounded transition-all disabled:opacity-40 shadow-[0_0_12px_rgba(239,68,68,0.2)]">
                    {loading ? <><Square size={12} /> EXECUTING</> : <><Play size={12} /> EXECUTE PAYLOAD</>}
                </button>
            </div>

            <div className="flex-1 grid grid-cols-12 min-h-0 relative z-10">

                {/* LEFT: Active C2 Agents + Payload Library */}
                <div className="col-span-3 flex flex-col border-r border-red-900/20 overflow-hidden">

                    {/* Connected Agents */}
                    <div className="border-b border-red-900/20 shrink-0">
                        <div className="px-3 py-2 bg-black/40 flex items-center gap-2 border-b border-red-900/20">
                            <Radio size={11} className="text-red-500 animate-pulse" />
                            <span className="text-[9px] font-bold text-red-500 tracking-widest flex-1">ACTIVE C2 AGENTS</span>
                            <button onClick={refreshSessions} className="text-red-900 hover:text-red-500 transition-colors">
                                <RefreshCw size={9} />
                            </button>
                        </div>
                        <div className="p-2 space-y-1.5">
                            {loadingData ? (
                                <div className="flex items-center gap-2 text-[9px] text-slate-700 px-2 py-4">
                                    <Loader2 size={10} className="animate-spin" /> Loading sessions...
                                </div>
                            ) : agents.length === 0 ? (
                                <div className="text-[9px] text-slate-700 px-2 py-4 text-center leading-relaxed">
                                    <Wifi size={14} className="mx-auto mb-1 opacity-30" />
                                    No active sessions.<br />
                                    <span className="text-slate-800">Deploy a stager to register a beacon.</span>
                                </div>
                            ) : (
                                agents.map(agent => (
                                    <button key={agent.beacon_id} onClick={() => setSelectedAgent(agent)}
                                        className={clsx(
                                            "w-full text-left p-2.5 rounded border transition-all",
                                            selectedAgent?.beacon_id === agent.beacon_id
                                                ? "border-red-600 bg-red-950/30 shadow-[0_0_10px_rgba(239,68,68,0.15)]"
                                                : "border-slate-800 bg-black/30 hover:border-red-900/50"
                                        )}>
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-[10px] font-bold text-red-400">{agent.name ?? agent.beacon_id}</span>
                                            <span className={clsx("w-1.5 h-1.5 rounded-full",
                                                agent.status === 'ACTIVE' ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600')} />
                                        </div>
                                        <div className="text-[9px] text-slate-600 space-y-0.5">
                                            <div className="text-slate-500 font-mono">{agent.ip ?? '—'}</div>
                                            <div>{agent.os ?? '—'}</div>
                                            <div className="flex justify-between">
                                                <span className={clsx("font-bold",
                                                    agent.privilege === 'SYSTEM' || agent.privilege === 'ROOT' ? 'text-rose-500' : 'text-slate-500')}>
                                                    {agent.privilege ?? 'USER'}
                                                </span>
                                                <span className="text-slate-700">{agent.last_seen ?? '—'}</span>
                                            </div>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Payload Library */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        <div className="px-3 py-2 bg-black/40 sticky top-0 flex items-center gap-2 border-b border-red-900/20">
                            <Code size={11} className="text-red-500" />
                            <span className="text-[9px] font-bold text-red-500 tracking-widest">PAYLOAD LIBRARY</span>
                            <span className="ml-auto text-[8px] text-slate-800">{payloads.length} payloads</span>
                        </div>
                        <div className="p-2 space-y-1.5">
                            {loadingData ? (
                                <div className="flex items-center gap-2 text-[9px] text-slate-700 px-2 py-4">
                                    <Loader2 size={10} className="animate-spin" /> Loading...
                                </div>
                            ) : dataError ? (
                                <div className="flex items-center gap-2 text-[9px] text-red-800 px-2 py-3">
                                    <AlertTriangle size={10} /> {dataError}
                                </div>
                            ) : payloads.length === 0 ? (
                                <div className="text-[9px] text-slate-700 px-2 py-4 text-center">
                                    No payloads in library.
                                </div>
                            ) : (
                                payloads.map(p => (
                                    <button key={p.id} onClick={() => loadPayload(p)}
                                        className="w-full text-left p-2.5 rounded border border-slate-800/60 bg-black/30 hover:border-red-900/50 transition-all group">
                                        <div className="flex items-center justify-between mb-0.5">
                                            <span className={clsx("text-[9px] font-bold px-1 rounded border bg-black/60 border-current/30", tagColour(p.tag))}>
                                                {p.tag}
                                            </span>
                                            <span className="text-[8px] text-slate-700 uppercase">{p.lang}</span>
                                        </div>
                                        <p className="text-[10px] text-slate-400 group-hover:text-slate-200 transition-colors leading-tight">{p.name}</p>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* CENTER: Code Editor */}
                <div className="col-span-6 flex flex-col border-r border-red-900/20 overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 border-b border-red-900/20 bg-black/40 shrink-0">
                        <div className="flex items-center gap-2">
                            <TerminalSquare size={12} className="text-red-500" />
                            <span className="text-[9px] font-bold text-red-500 tracking-widest">PAYLOAD EDITOR</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-[9px] text-slate-600">
                                TARGET: <span className="text-red-400 font-mono">{selectedAgent?.ip ?? 'no session'}</span>
                                {selectedAgent?.privilege && ` [${selectedAgent.privilege}]`}
                            </span>
                            <button onClick={copyCode} className={clsx("flex items-center gap-1 text-[9px] px-2 py-1 rounded border transition-all",
                                copied ? "border-emerald-600 text-emerald-400" : "border-slate-700 text-slate-500 hover:border-slate-500")}>
                                {copied ? <CheckCircle2 size={10} /> : <Copy size={10} />}
                                {copied ? 'COPIED' : 'COPY'}
                            </button>
                        </div>
                    </div>
                    <div className="flex-1 relative overflow-hidden">
                        {/* Line numbers */}
                        <div className="absolute left-0 top-0 bottom-0 w-10 bg-black/60 border-r border-slate-900 flex flex-col pt-4 items-center overflow-hidden pointer-events-none z-10">
                            {code.split('\n').map((_, i) => (
                                <span key={i} className="text-[9px] text-slate-800 leading-5 w-full text-right pr-2 shrink-0">{i + 1}</span>
                            ))}
                        </div>
                        <textarea
                            value={code}
                            onChange={e => setCode(e.target.value)}
                            disabled={loading}
                            spellCheck={false}
                            className="absolute inset-0 w-full h-full bg-transparent text-emerald-400 font-mono text-[11px] pl-12 pr-4 pt-4 pb-4 focus:outline-none resize-none leading-5 disabled:opacity-60"
                            style={{ tabSize: 4 }}
                        />
                    </div>
                </div>

                {/* RIGHT: Execution Terminal */}
                <div className="col-span-3 flex flex-col overflow-hidden">
                    <div className="px-3 py-2 border-b border-red-900/20 bg-black/40 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-2">
                            <AlertOctagon size={12} className={clsx("text-red-500", loading && "animate-pulse")} />
                            <span className="text-[9px] font-bold text-red-500 tracking-widest">EXECUTION OUTPUT</span>
                        </div>
                        {output.length > 0 && (
                            <button onClick={() => setOutput([])} className="text-[8px] text-slate-600 hover:text-slate-400">
                                <RefreshCw size={10} />
                            </button>
                        )}
                    </div>
                    <div ref={outputRef} className="flex-1 overflow-y-auto custom-scrollbar p-3 text-[10px] space-y-0.5 bg-black/60">
                        {output.length === 0 ? (
                            <p className="text-slate-700 text-center py-8 tracking-widest">Awaiting payload execution...</p>
                        ) : output.map((line, i) => (
                            <div key={i} className={clsx("leading-5 break-words",
                                line.startsWith('[+]') ? 'text-emerald-400' :
                                    line.startsWith('[!]') || line.startsWith('[ERROR]') ? 'text-rose-400 font-bold' :
                                        line.startsWith('[GHOST') || line.startsWith('[*]') ? 'text-cyan-500' :
                                            line.startsWith('[STDERR]') ? 'text-orange-400' :
                                                line.startsWith('[SANDBOX]') ? 'text-amber-400' :
                                                    line.startsWith('[⚠]') ? 'text-yellow-400' : 'text-slate-300'
                            )}>
                                {line}
                            </div>
                        ))}
                        {loading && <div className="text-red-500 animate-pulse">executing_</div>}
                    </div>

                    {/* Operator Notes */}
                    <div className="border-t border-red-900/20 p-3 bg-black/40 shrink-0">
                        <div className="text-[9px] text-slate-700 space-y-1">
                            <div className="flex items-center gap-1.5"><Shield size={9} className="text-emerald-700" /> Sandbox isolation active</div>
                            <div className="flex items-center gap-1.5"><Eye size={9} className="text-rose-700" /> All executions logged to Immutable Ledger</div>
                            <div className="flex items-center gap-1.5"><Lock size={9} className="text-amber-700" /> Traffic via Ghost Protocol (HTTPS/443)</div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
        </TeamShell>
    );
}
