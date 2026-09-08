'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import {
    Activity,
    ChevronDown,
    Command,
    LayoutDashboard,
    Shield,
    ShieldAlert,
    ShieldCheck,
    Siren,
    Skull,
    Sparkles,
    ThermometerSun,
    Network,
    Globe,
    Layers3,
    Lock,
    LogOut,
    Search,
    Brain,
    Bot,
    ClipboardCheck,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/components/providers/AuthProvider';
import { CommandPalette } from '@/components/ui/CommandPalette';

type NavItem = {
    label: string;
    href: string;
    description: string;
    icon: typeof LayoutDashboard;
};

type NavGroup = {
    label: string;
    accent: string;
    icon: typeof Layers3;
    items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
    {
        label: 'Intelligence',
        accent: 'from-cyan-400/20 to-sky-500/10 border-cyan-400/20',
        icon: Activity,
        items: [
            {
                label: 'Situation Room',
                href: '/',
                description: 'Live executive overview',
                icon: LayoutDashboard,
            },
            {
                label: 'Intel Graph',
                href: '/entities',
                description: 'Relationship graph and entities',
                icon: Network,
            },
            {
                label: 'Intelligence Map',
                href: '/intelligence',
                description: 'Collection and enrichment view',
                icon: Globe,
            },
            {
                label: 'Anomaly Matrix',
                href: '/anomalies',
                description: 'UEBA and detection feed',
                icon: Activity,
            },
            {
                label: 'Threat Heatmaps',
                href: '/heatmaps',
                description: 'Spatial risk concentration',
                icon: ThermometerSun,
            },
            {
                label: 'Adversarial Intel',
                href: '/intelligence/adversarial',
                description: 'STIX/TAXII · EAC threat landscape',
                icon: Brain,
            },
            {
                label: 'Autonomous SOC',
                href: '/intelligence/soc',
                description: 'SOAR playbooks · incident triage',
                icon: Bot,
            },
            {
                label: 'Compliance Engine',
                href: '/intelligence/compliance',
                description: 'DPA 2019 · CBK · ISO 27001',
                icon: ClipboardCheck,
            },
        ],
    },
    {
        label: 'Offensive',
        accent: 'from-rose-500/20 to-red-500/10 border-rose-500/20',
        icon: Skull,
        items: [
            {
                label: 'Red Team Ops',
                href: '/redteam',
                description: 'Attack simulation command center',
                icon: Skull,
            },
            {
                label: 'Exploit Workbench',
                href: '/redteam/exploits',
                description: 'Payload and chain workspace',
                icon: Siren,
            },
            {
                label: 'Ghost Shell',
                href: '/ghost',
                description: 'Stealth execution console',
                icon: ShieldAlert,
            },
        ],
    },
    {
        label: 'Infrastructure',
        accent: 'from-indigo-500/20 to-slate-500/10 border-indigo-400/20',
        icon: Layers3,
        items: [
            {
                label: 'Infrastructure Grid',
                href: '/dashboard',
                description: 'System runtime and node status',
                icon: Layers3,
            },
            {
                label: 'Device Registry',
                href: '/devices',
                description: 'Endpoint posture and control plane',
                icon: Globe,
            },
            {
                label: 'Recon Pipeline',
                href: '/recon',
                description: 'Collection and scanning orchestration',
                icon: Activity,
            },
        ],
    },
    {
        label: 'Defensive',
        accent: 'from-emerald-400/20 to-teal-500/10 border-emerald-400/20',
        icon: ShieldCheck,
        items: [
            {
                label: 'Blue Team SOC',
                href: '/defense',
                description: 'Monitoring and response dashboard',
                icon: Shield,
            },
            {
                label: 'Threat Hunt',
                href: '/defense/hunt',
                description: 'Hunt and validation workflows',
                icon: Search,
            },
            {
                label: 'Guardian',
                href: '/guardian',
                description: 'Policy and control orchestration',
                icon: Lock,
            },
            {
                label: 'Immutable Ledger',
                href: '/ledger',
                description: 'Cryptographic audit history',
                icon: Sparkles,
            },
        ],
    },
];

function getActiveGroup(pathname: string) {
    return NAV_GROUPS.find((group) => group.items.some((item) => pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))))?.label ?? 'Intelligence';
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { user, logout, isLoading } = useAuth();
    const [openGroup, setOpenGroup] = useState(getActiveGroup(pathname));
    const isAuthRoute = pathname.startsWith('/login');

    useEffect(() => {
        setOpenGroup(getActiveGroup(pathname));
    }, [pathname]);

    const activeLabel = useMemo(() => {
        for (const group of NAV_GROUPS) {
            const found = group.items.find((item) => pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href)));
            if (found) {
                return found.label;
            }
        }

        return 'Situation Room';
    }, [pathname]);

    if (isAuthRoute) {
        return <>{children}</>;
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-teal-400/30 selection:text-white">
            <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,_rgba(20,184,166,0.12),_transparent_35%),linear-gradient(180deg,_rgba(15,23,42,0.92),_rgba(2,6,23,1))]" />
            <div className="relative flex min-h-screen">
                <aside className="fixed left-0 top-0 z-40 hidden h-screen w-80 flex-col border-r border-white/10 bg-white/5 backdrop-blur-md lg:flex">
                    <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-400 to-indigo-500 text-sm font-black text-slate-950 shadow-[0_0_24px_rgba(45,212,191,0.35)]">
                            XY
                        </div>
                        <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-slate-200">ProjectXY</p>
                            <p className="text-[10px] uppercase tracking-[0.25em] text-slate-400">Tactical Intelligence Interface</p>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto px-4 py-4">
                        {NAV_GROUPS.map((group) => {
                            const isOpen = openGroup === group.label;
                            const GroupIcon = group.icon;

                            return (
                                <div key={group.label} className={clsx('mb-3 rounded-2xl border bg-gradient-to-br p-2', group.accent)}>
                                    <button
                                        type="button"
                                        onClick={() => setOpenGroup((current) => (current === group.label ? '' : group.label))}
                                        className="flex w-full items-center justify-between rounded-xl px-3 py-3 text-left transition hover:bg-white/5"
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/5 text-slate-200">
                                                <GroupIcon size={18} />
                                            </span>
                                            <div>
                                                <p className="text-sm font-semibold tracking-wide text-white">{group.label}</p>
                                                <p className="text-[11px] text-slate-400">{group.items.length} operational views</p>
                                            </div>
                                        </div>
                                        <motion.span
                                            animate={{ rotate: isOpen ? 180 : 0 }}
                                            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                        >
                                            <ChevronDown size={16} className="text-slate-400" />
                                        </motion.span>
                                    </button>

                                    <AnimatePresence initial={false}>
                                        {isOpen ? (
                                            <motion.div
                                                key={group.label}
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: 'auto', opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                                className="overflow-hidden"
                                            >
                                                <div className="space-y-1 px-1 pb-1 pt-2">
                                                    {group.items.map((item) => {
                                                        const ItemIcon = item.icon;
                                                        const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));

                                                        return (
                                                            <Link
                                                                key={item.href}
                                                                href={item.href}
                                                                prefetch={false}
                                                                className={clsx(
                                                                    'flex items-start gap-3 rounded-xl border px-3 py-3 transition-all',
                                                                    isActive
                                                                        ? 'border-teal-400/40 bg-teal-400/10 shadow-[0_0_24px_rgba(45,212,191,0.12)]'
                                                                        : 'border-transparent text-slate-300 hover:border-white/10 hover:bg-white/5'
                                                                )}
                                                            >
                                                                <span className={clsx('mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg', isActive ? 'bg-teal-400/20 text-teal-300' : 'bg-white/5 text-slate-300')}>
                                                                    <ItemIcon size={16} />
                                                                </span>
                                                                <span className="min-w-0 flex-1">
                                                                    <span className="block text-sm font-medium text-white">{item.label}</span>
                                                                    <span className="block text-[11px] leading-4 text-slate-400">{item.description}</span>
                                                                </span>
                                                            </Link>
                                                        );
                                                    })}
                                                </div>
                                            </motion.div>
                                        ) : null}
                                    </AnimatePresence>
                                </div>
                            );
                        })}
                    </div>

                    <div className="border-t border-white/10 px-5 py-4">
                        <div className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-sm">
                            <div className="min-w-0">
                                <p className="text-[10px] uppercase tracking-[0.32em] text-slate-500">Session</p>
                                <p className="truncate text-sm font-medium text-white">{isLoading ? 'Verifying operator...' : user?.email ?? 'Unauthenticated'}</p>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] text-teal-300">
                                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(74,222,128,0.7)]" />
                                Live
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => void logout()}
                            className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm font-medium text-slate-200 transition hover:border-teal-400/40 hover:bg-teal-400/10"
                        >
                            <LogOut size={16} />
                            Logout
                        </button>
                    </div>
                </aside>

                <div className="flex min-h-screen flex-1 flex-col lg:pl-80">
                    <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/70 backdrop-blur-md">
                        <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={() => window.dispatchEvent(new Event('projectxy:open-command-palette'))}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-teal-400/40 hover:bg-teal-400/10"
                                >
                                    <Command size={14} />
                                    Cmd+K
                                </button>
                                <div>
                                    <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">Active Module</p>
                                    <h1 className="text-lg font-semibold text-white">{activeLabel}</h1>
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <div className="hidden rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 sm:block">
                                    Spring-driven UI · React Query caching
                                </div>
                                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
                                    {user?.role ?? 'guest'}
                                </div>
                            </div>
                        </div>
                    </header>

                    <main className="relative flex-1 px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
                        {children}
                    </main>
                </div>
            </div>

            <CommandPalette />
        </div>
    );
}