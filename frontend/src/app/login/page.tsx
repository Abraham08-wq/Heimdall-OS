'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '@/components/providers/AuthProvider';
import { AlertCircle, ArrowRight, Cpu, Eye, EyeOff, Lock, ShieldCheck, Sparkles, Wifi } from 'lucide-react';
import { api } from '@/lib/api';

const BOOT_LINES = [
    'NEXUS CYBER INTELLIGENCE PLATFORM v5.0',
    'Initializing Zero-Trust Authentication Engine...',
    'Verifying HSM key escrow... OK',
    'Loading threat intelligence context... OK',
    'Establishing encrypted session tunnel... OK',
    'READY — Operator authentication required.',
];

export default function LoginPage() {
    const { login } = useAuth();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    // No typing animation: show boot lines immediately
    const bootLines = BOOT_LINES;
    const typedBootLines = bootLines;
    const FAST_LOGIN = process.env.NEXT_PUBLIC_FAST_LOGIN === 'true';

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            const response = await api.login(username, password);
            await login(response.access_token);
        } catch (err: any) {
            setError('AUTHENTICATION FAILED — Invalid credentials or policy violation.');
        } finally {
            setIsLoading(false);
        }
    };


    return (
        <div className="relative isolate flex min-h-[calc(100vh-6rem)] items-center justify-center overflow-hidden py-6 font-sans">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.14),_transparent_38%),linear-gradient(180deg,_rgba(15,23,42,0.95),_rgba(2,6,23,1))]" />
            <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: 'linear-gradient(rgba(148,163,184,0.9) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.9) 1px, transparent 1px)', backgroundSize: '44px 44px' }} />

            <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                className="relative z-10 w-full max-w-6xl px-4"
            >
                <div className="grid gap-6 rounded-[2rem] bg-gradient-to-r from-teal-500 to-indigo-500 p-[1px] shadow-[0_30px_120px_rgba(15,23,42,0.65)]">
                    <div className="grid gap-6 rounded-[2rem] border border-white/10 bg-slate-950/90 p-6 backdrop-blur-xl lg:grid-cols-[1.05fr_0.95fr] lg:p-8">
                        <section className="space-y-6">
                            <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-[0.35em] text-slate-400">
                                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-emerald-300">System Online</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Neo4j</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Postgres</span>
                                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">TLS</span>
                            </div>

                            <div>
                                <p className="text-[10px] uppercase tracking-[0.5em] text-teal-300/80">ProjectXY</p>
                                <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                                    Tactical intelligence login for the operator surface.
                                </h1>
                                <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400 sm:text-base">
                                    Secure session initialization, live telemetry, and real-time mission control in a single consolidated view.
                                </p>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                                <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-[0.35em] text-slate-500">
                                    <Cpu size={12} className="text-teal-300" />
                                    System Diagnostics
                                </div>
                                <div className="space-y-1 font-mono text-sm leading-6 text-slate-300">
                                    {typedBootLines.map((line, index) => (
                                        <motion.div
                                            key={line}
                                            initial={{ opacity: 0, x: -6 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ type: 'spring', stiffness: 300, damping: 30, delay: index * 0.02 }}
                                            className="flex gap-2"
                                        >
                                            <span className="text-emerald-400">✓</span>
                                            <span>{line}</span>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>
                        </section>

                        <section className="flex items-center">
                            <div className="w-full rounded-[1.5rem] bg-gradient-to-b from-white/10 to-white/5 p-[1px] shadow-[0_20px_80px_rgba(15,23,42,0.45)]">
                                <div className="rounded-[1.45rem] border border-white/10 bg-slate-950/95 p-5 sm:p-6">
                                    <div className="mb-5 flex items-center justify-between gap-3">
                                        <div>
                                            <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">Operator Authentication</p>
                                            <h2 className="mt-1 text-lg font-semibold text-white">Authenticate to continue</h2>
                                        </div>
                                        <div className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-[10px] uppercase tracking-[0.3em] text-emerald-300">
                                            <Wifi size={12} />
                                            Encrypted
                                        </div>
                                    </div>

                                    <form onSubmit={handleSubmit} className="space-y-4">
                                        <label className="block space-y-2">
                                            <span className="text-[10px] uppercase tracking-[0.35em] text-slate-400">Operative ID (Email)</span>
                                            <input
                                                id="username"
                                                type="email"
                                                required
                                                value={username}
                                                onChange={(event) => setUsername(event.target.value)}
                                                placeholder="admin@projectxy.com"
                                                className="w-full rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3 text-sm text-white outline-none transition focus:ring-2 focus:ring-teal-500/50"
                                            />
                                        </label>

                                        <label className="block space-y-2">
                                            <span className="text-[10px] uppercase tracking-[0.35em] text-slate-400">Authentication Code</span>
                                            <div className="relative">
                                                <input
                                                    id="password"
                                                    type={showPassword ? 'text' : 'password'}
                                                    required
                                                    value={password}
                                                    onChange={(event) => setPassword(event.target.value)}
                                                    placeholder="••••••••••••"
                                                    className="w-full rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3 pr-12 text-sm text-white outline-none transition focus:ring-2 focus:ring-teal-500/50"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setShowPassword((current) => !current)}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 transition hover:text-white"
                                                >
                                                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                                                </button>
                                            </div>
                                        </label>

                                        {error ? (
                                            <div className="flex items-start gap-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                                                <AlertCircle size={16} className="mt-0.5 shrink-0 text-rose-300" />
                                                <span>{error}</span>
                                            </div>
                                        ) : null}

                                        <motion.button
                                            type="submit"
                                            disabled={isLoading}
                                            whileHover={isLoading ? undefined : { scale: 1.02 }}
                                            whileTap={isLoading ? undefined : { scale: 0.98 }}
                                            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-teal-500 to-indigo-500 px-4 py-3.5 text-sm font-semibold text-white shadow-[0_18px_45px_rgba(45,212,191,0.25)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
                                        >
                                            {isLoading ? 'Authenticating...' : 'Authenticate'}
                                            {!isLoading ? <ArrowRight size={16} /> : null}
                                        </motion.button>
                                    </form>

                                    <div className="mt-5 flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-400">
                                        <ShieldCheck size={14} className="text-teal-300" />
                                        All sessions are encrypted, authenticated, and logged.
                                    </div>
                                </div>
                            </div>
                        </section>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
