'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import { Command as CommandMenu } from 'cmdk';
import { Search, Shield, Network, LayoutDashboard, ShieldAlert, ThermometerSun, Skull, Siren, Globe, SearchCheck, Lock, Layers3, Sparkles, Command as CommandIcon } from 'lucide-react';

type CommandItem = {
    label: string;
    description: string;
    href: string;
    icon: typeof CommandIcon;
    keywords: string[];
};

const COMMANDS: CommandItem[] = [
    { label: 'Situation Room', description: 'Open the executive threat overview', href: '/', icon: LayoutDashboard, keywords: ['dashboard', 'overview', 'situation', 'room'] },
    { label: 'Intel Graph', description: 'Navigate to the graph intelligence view', href: '/entities', icon: Network, keywords: ['graph', 'entities', 'intel'] },
    { label: 'Intelligence Map', description: 'Open enrichment and collection feeds', href: '/intelligence', icon: Globe, keywords: ['map', 'collection', 'feeds'] },
    { label: 'Anomaly Matrix', description: 'Inspect anomaly detection results', href: '/anomalies', icon: SearchCheck, keywords: ['anomaly', 'matrix', 'detections'] },
    { label: 'Red Team Ops', description: 'Open offensive operations', href: '/redteam', icon: Skull, keywords: ['red', 'team', 'offensive'] },
    { label: 'Exploit Workbench', description: 'Jump to exploit payload workflows', href: '/redteam/exploits', icon: Siren, keywords: ['exploit', 'payload', 'workbench'] },
    { label: 'Blue Team SOC', description: 'Open defensive monitoring', href: '/defense', icon: Shield, keywords: ['blue', 'team', 'soc'] },
    { label: 'Threat Hunt', description: 'Open hunt and triage workflows', href: '/defense/hunt', icon: Search, keywords: ['hunt', 'defense', 'search'] },
    { label: 'Ghost Shell', description: 'Open the stealth shell', href: '/ghost', icon: ShieldAlert, keywords: ['ghost', 'shell', 'stealth'] },
    { label: 'Infrastructure Grid', description: 'Open node and runtime infrastructure', href: '/dashboard', icon: Layers3, keywords: ['infrastructure', 'nodes', 'runtime'] },
    { label: 'Recon Pipeline', description: 'Open recon collection and scanning', href: '/recon', icon: Globe, keywords: ['recon', 'scan', 'pipeline'] },
    { label: 'Asset Recovery', description: 'Inspect managed devices', href: '/devices', icon: Layers3, keywords: ['assets', 'devices', 'recovery'] },
    { label: 'Guardian', description: 'Open policy orchestration', href: '/guardian', icon: Lock, keywords: ['guardian', 'policy', 'control'] },
    { label: 'Threat Heatmaps', description: 'Review spatial risk density', href: '/heatmaps', icon: ThermometerSun, keywords: ['heatmap', 'heatmaps', 'spatial'] },
    { label: 'Immutable Ledger', description: 'Inspect audit and chain records', href: '/ledger', icon: Sparkles, keywords: ['ledger', 'audit', 'immutable'] },
];

function fuzzyScore(candidate: string, query: string) {
    const normalizedCandidate = candidate.toLowerCase();
    const normalizedQuery = query.toLowerCase().trim();

    if (!normalizedQuery) {
        return 1;
    }

    if (normalizedCandidate === normalizedQuery) {
        return 100;
    }

    if (normalizedCandidate.startsWith(normalizedQuery)) {
        return 90;
    }

    if (normalizedCandidate.includes(normalizedQuery)) {
        return 70;
    }

    let score = 0;
    let candidateIndex = 0;

    for (const char of normalizedQuery) {
        const nextIndex = normalizedCandidate.indexOf(char, candidateIndex);
        if (nextIndex === -1) {
            return 0;
        }

        score += nextIndex === candidateIndex ? 4 : 1;
        candidateIndex = nextIndex + 1;
    }

    return score;
}

export function CommandPalette() {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const router = useRouter();

    useEffect(() => {
        if (isOpen) {
            setQuery('');
        }
    }, [isOpen]);

    const filteredCommands = useMemo(() => {
        if (!query.trim()) {
            return COMMANDS;
        }

        return [...COMMANDS]
            .map((command) => ({ command, score: fuzzyScore([command.label, command.description, ...command.keywords].join(' '), query) }))
            .filter(({ score }) => score > 0)
            .sort((left, right) => right.score - left.score)
            .map(({ command }) => command);
    }, [query]);

    useEffect(() => {
        const handleShortcut = (event: KeyboardEvent) => {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                setIsOpen((current) => !current);
                return;
            }

            if (isOpen && event.key === 'Escape') {
                event.preventDefault();
                setIsOpen(false);
            }
        };

        const openPalette = () => setIsOpen(true);

        window.addEventListener('keydown', handleShortcut);
        window.addEventListener('projectxy:open-command-palette', openPalette as EventListener);

        return () => {
            window.removeEventListener('keydown', handleShortcut);
            window.removeEventListener('projectxy:open-command-palette', openPalette as EventListener);
        };
    }, [isOpen]);

    useEffect(() => {
        const handleRouteChange = () => setIsOpen(false);
        window.addEventListener('popstate', handleRouteChange);
        return () => window.removeEventListener('popstate', handleRouteChange);
    }, []);

    const runCommand = (href: string) => {
        router.push(href);
        setIsOpen(false);
        setQuery('');
    };

    return (
        <AnimatePresence>
            {isOpen ? (
                <CommandMenu.Dialog
                    open={isOpen}
                    onOpenChange={setIsOpen}
                    label="Command Palette"
                    shouldFilter={false}
                >
                    <motion.div
                    className="fixed inset-0 z-[300] flex items-start justify-center bg-slate-950/70 px-4 pt-[12vh] backdrop-blur-md"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    onMouseDown={() => setIsOpen(false)}
                >
                    <motion.div
                        className="w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-slate-950/85 shadow-[0_24px_80px_rgba(2,6,23,0.75),0_0_40px_rgba(45,212,191,0.14)] backdrop-blur-xl"
                        initial={{ scale: 0.96, y: 18, opacity: 0 }}
                        animate={{ scale: 1, y: 0, opacity: 1 }}
                        exit={{ scale: 0.98, y: 10, opacity: 0 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        onMouseDown={(event) => event.stopPropagation()}
                    >
                        <CommandMenu
                            value={query}
                            onValueChange={setQuery}
                            className="w-full"
                        >
                            <div className="flex items-center gap-3 border-b border-white/10 px-5 py-4">
                                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/5 text-teal-300">
                                    <Search size={18} />
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">Command Palette</p>
                                    <CommandMenu.Input
                                        autoFocus
                                        placeholder="Jump to a module or page..."
                                        className="mt-1 w-full bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
                                    />
                                </div>
                                <div className="hidden items-center gap-2 sm:flex">
                                    <kbd className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.25em] text-slate-400">Cmd K</kbd>
                                    <kbd className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.25em] text-slate-400">Esc</kbd>
                                </div>
                            </div>

                            <CommandMenu.List className="max-h-[60vh] overflow-y-auto p-3">
                                <div className="px-3 pb-2 text-[10px] uppercase tracking-[0.35em] text-slate-500">Navigation</div>
                                <CommandMenu.Empty className="rounded-2xl border border-white/10 bg-white/5 px-4 py-8 text-center text-sm text-slate-400">
                                    No matching modules.
                                </CommandMenu.Empty>

                                <div className="space-y-1">
                                    {filteredCommands.map((command) => {
                                        const Icon = command.icon;

                                        return (
                                            <CommandMenu.Item
                                                key={command.href}
                                                value={[command.label, command.description, ...command.keywords].join(' ')}
                                                onSelect={() => runCommand(command.href)}
                                                className="group flex w-full cursor-pointer items-start gap-3 rounded-2xl border border-transparent px-4 py-3 text-left transition data-[selected=true]:border-teal-400/40 data-[selected=true]:bg-teal-400/10"
                                            >
                                                <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-white/5 text-teal-300">
                                                    <Icon size={16} />
                                                </span>
                                                <span className="min-w-0 flex-1">
                                                    <span className="block text-sm font-medium text-white">{command.label}</span>
                                                    <span className="block text-xs text-slate-400">{command.description}</span>
                                                </span>
                                                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.24em] text-slate-400">
                                                    Open
                                                </span>
                                            </CommandMenu.Item>
                                        );
                                    })}
                                </div>
                            </CommandMenu.List>
                        </CommandMenu>
                    </motion.div>
                </motion.div>
                </CommandMenu.Dialog>
            ) : null}
        </AnimatePresence>
    );
}