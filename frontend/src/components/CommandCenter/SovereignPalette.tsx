'use client';

/**
 * ProjectXY — Unified Sovereign Command Palette
 * ==============================================
 * Single global Cmd+K (or Ctrl+K) palette. Replaces any per-component
 * palette implementations. Registered once at the Providers level.
 *
 * Categories: Navigation | System Actions | Intelligence | Quick Settings
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Shield, Terminal, Network, Globe,
  Activity, KeyRound, Map, ThermometerSun, Zap, Crosshair,
  ShieldCheck, Cpu, Search, Eye, Power, Lock, Unlock,
  RefreshCw, AlertTriangle, Database, Wifi, WifiOff, X,
} from 'lucide-react';
import { apiRequest } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

type PaletteItemCategory = 'navigate' | 'action' | 'intelligence' | 'system';

interface PaletteItem {
  id: string;
  label: string;
  description?: string;
  category: PaletteItemCategory;
  icon: React.ReactNode;
  keywords?: string[];
  action: () => Promise<void> | void;
}

// ── Context ────────────────────────────────────────────────────────────────

interface PaletteCtx {
  open: () => void;
  close: () => void;
}

const PaletteContext = React.createContext<PaletteCtx>({ open: () => {}, close: () => {} });
export const usePalette = () => React.useContext(PaletteContext);

// ── Category styling ───────────────────────────────────────────────────────

const CATEGORY_LABEL: Record<PaletteItemCategory, string> = {
  navigate:     'NAVIGATION',
  action:       'SYSTEM ACTIONS',
  intelligence: 'INTELLIGENCE',
  system:       'PLATFORM',
};

const CATEGORY_DOT: Record<PaletteItemCategory, string> = {
  navigate:     'bg-sky-500',
  action:       'bg-red-500',
  intelligence: 'bg-purple-500',
  system:       'bg-slate-500',
};

// ── Toast helper ───────────────────────────────────────────────────────────

function fireToast(msg: string, level: 'ok' | 'err' | 'warn' = 'ok') {
  window.dispatchEvent(new CustomEvent('projectxy:toast', { detail: { msg, level } }));
}

// ── Provider component ─────────────────────────────────────────────────────

export function SovereignPaletteProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen]     = useState(false);
  const [query, setQuery]       = useState('');
  const [selected, setSelected] = useState(0);
  const [toast, setToast]       = useState<{ msg: string; level: string } | null>(null);
  const inputRef  = useRef<HTMLInputElement>(null);
  const router    = useRouter();

  const open  = useCallback(() => { setIsOpen(true);  setQuery(''); setSelected(0); }, []);
  const close = useCallback(() => { setIsOpen(false); setQuery(''); }, []);

  // Toast events
  useEffect(() => {
    const handler = (e: Event) => {
      const { msg, level } = (e as CustomEvent).detail;
      setToast({ msg, level });
      setTimeout(() => setToast(null), 3000);
    };
    window.addEventListener('projectxy:toast', handler);
    return () => window.removeEventListener('projectxy:toast', handler);
  }, []);

  // Global keyboard
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
        setQuery('');
        setSelected(0);
      }
      if (e.key === 'Escape' && isOpen) close();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, close]);

  // Auto-focus input
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 50);
  }, [isOpen]);

  // ── Command definitions ──────────────────────────────────────────────────

  const nav = (path: string) => () => { close(); router.push(path); };

  const ITEMS: PaletteItem[] = [
    // — Navigation —
    { id: 'nav-dashboard',  label: 'Situation Room',      description: 'Live incident command center',   category: 'navigate',     icon: <LayoutDashboard size={15} />, action: nav('/') },
    { id: 'nav-defense',    label: 'SOC Command Center',  description: 'Blue team — defensive posture',  category: 'navigate',     icon: <Shield size={15} />,          action: nav('/defense') },
    { id: 'nav-hunt',       label: 'Threat Hunt',         description: 'Semantic adversarial search',    category: 'navigate',     icon: <Search size={15} />,          action: nav('/defense/hunt') },
    { id: 'nav-firewall',   label: 'AI Firewall',         description: '5-layer cognitive shield LIVE',  category: 'navigate',     icon: <ShieldCheck size={15} />,     action: nav('/firewall'), keywords: ['firewall', 'ai', 'shield'] },
    { id: 'nav-guardian',   label: 'Guardian IoT',        description: 'IoT device security oversight',  category: 'navigate',     icon: <Cpu size={15} />,             action: nav('/guardian') },
    { id: 'nav-intel',      label: 'Intelligence Map',    description: 'Entity relationship graph',      category: 'intelligence', icon: <Globe size={15} />,           action: nav('/intelligence') },
    { id: 'nav-entities',   label: 'Intel Graph',         description: 'Threat actor network',           category: 'intelligence', icon: <Network size={15} />,         action: nav('/entities') },
    { id: 'nav-anomalies',  label: 'Anomaly Matrix',      description: 'Behavioral anomaly detection',   category: 'intelligence', icon: <Activity size={15} />,        action: nav('/anomalies') },
    { id: 'nav-soc',        label: 'Autonomous SOC',      description: 'AI threat hunting + simulation', category: 'intelligence', icon: <Eye size={15} />,             action: nav('/intelligence/soc') },
    { id: 'nav-adversarial',label: 'Adversarial Intel',   description: 'APT landscape + actor tracking', category: 'intelligence', icon: <AlertTriangle size={15} />,   action: nav('/intelligence/adversarial') },
    { id: 'nav-ghost',      label: 'Ghost Shell',         description: 'Covert red team operations',     category: 'navigate',     icon: <Terminal size={15} />,        action: nav('/ghost') },
    { id: 'nav-exploits',   label: 'Exploit Workbench',   description: 'Offensive payload development',  category: 'navigate',     icon: <Zap size={15} />,             action: nav('/redteam/exploits') },
    { id: 'nav-redteam',    label: 'Red Team Ops',        description: 'Offensive operations center',    category: 'navigate',     icon: <Crosshair size={15} />,       action: nav('/redteam') },
    { id: 'nav-ledger',     label: 'Immutable Ledger',    description: 'WORM audit blockchain',          category: 'navigate',     icon: <KeyRound size={15} />,        action: nav('/ledger') },
    { id: 'nav-devices',    label: 'Asset Recovery',      description: 'Registered device inventory',   category: 'system',       icon: <Map size={15} />,             action: nav('/devices') },
    { id: 'nav-heatmaps',   label: 'Threat Heatmaps',     description: 'MITRE ATT&CK coverage grid',    category: 'intelligence', icon: <ThermometerSun size={15} />,  action: nav('/heatmaps') },
    { id: 'nav-infra',      label: 'Infrastructure Grid', description: 'Asset topology & health',        category: 'system',       icon: <Database size={15} />,        action: nav('/infrastructure') },
    // — System Actions —
    {
      id: 'act-lockdown',
      label: 'Emergency Lockdown',
      description: 'Revoke all sessions, isolate all devices (SUPERUSER)',
      category: 'action',
      icon: <Lock size={15} />,
      keywords: ['lockdown', 'emergency', 'kill'],
      action: async () => {
        close();
        const reason = window.prompt('Lockdown reason (required):');
        if (!reason) return;
        try {
          await apiRequest('/intel/command/emergency-lockdown', {
            method: 'POST',
            params: { reason },
          });
          fireToast('🚨 SYSTEM LOCKDOWN ACTIVATED', 'err');
        } catch (e: any) {
          fireToast(`Lockdown failed: ${e?.message ?? e}`, 'err');
        }
      },
    },
    {
      id: 'act-soc-hunt',
      label: 'Start SOC Threat Hunting',
      description: 'Activate autonomous AI threat hunting cycle',
      category: 'action',
      icon: <Search size={15} />,
      action: async () => {
        close();
        try {
          await apiRequest('/intel/soc/start-hunting', { method: 'POST' });
          fireToast('SOC threat hunting activated', 'ok');
        } catch (e: any) {
          fireToast(`SOC hunt failed: ${e?.message ?? e}`, 'err');
        }
      },
    },
    {
      id: 'act-revoke-all',
      label: 'Revoke All Sessions',
      description: 'Force logout all active users (ADMIN)',
      category: 'action',
      icon: <WifiOff size={15} />,
      keywords: ['revoke', 'logout', 'sessions', 'kick'],
      action: async () => {
        close();
        if (!window.confirm('Revoke ALL user sessions?')) return;
        try {
          await apiRequest('/intel/command/emergency-lockdown', {
            method: 'POST',
            params: { reason: 'Manual session revocation via palette' },
          });
          fireToast('All sessions revoked', 'warn');
        } catch (e: any) {
          fireToast(`Revocation failed: ${e?.message ?? e}`, 'err');
        }
      },
    },
    {
      id: 'act-system-status',
      label: 'System Status',
      description: 'Live health check of all backend services',
      category: 'system',
      icon: <Activity size={15} />,
      action: async () => {
        close();
        try {
          const data = await apiRequest<Record<string, any>>('/intel/command/system-status');
          const lines = Object.entries(data)
            .filter(([k]) => k !== 'timestamp')
            .map(([k, v]) => `${k}: ${v}`)
            .join('\n');
          window.alert(`System Status\n\n${lines}`);
        } catch (e: any) {
          fireToast(`Status check failed: ${e?.message ?? e}`, 'err');
        }
      },
    },
    {
      id: 'act-reload',
      label: 'Refresh Dashboard',
      description: 'Force reload all dashboard data',
      category: 'system',
      icon: <RefreshCw size={15} />,
      action: () => { close(); window.location.reload(); },
    },
  ];

  // ── Filtering ──────────────────────────────────────────────────────────

  const filtered = query.trim()
    ? ITEMS.filter(item => {
        const q = query.toLowerCase();
        return (
          item.label.toLowerCase().includes(q) ||
          (item.description ?? '').toLowerCase().includes(q) ||
          (item.keywords ?? []).some(k => k.toLowerCase().includes(q))
        );
      })
    : ITEMS;

  // ── Grouping ───────────────────────────────────────────────────────────

  const groups: [PaletteItemCategory, PaletteItem[]][] = [];
  const seen = new Set<PaletteItemCategory>();
  const ordered: PaletteItemCategory[] = ['navigate', 'action', 'intelligence', 'system'];

  for (const cat of ordered) {
    const items = filtered.filter(i => i.category === cat);
    if (items.length > 0) { groups.push([cat, items]); seen.add(cat); }
  }

  // Flat index for keyboard navigation
  const flatItems = groups.flatMap(([, items]) => items);
  const clampedSel = Math.min(selected, flatItems.length - 1);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected(s => Math.min(s + 1, flatItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected(s => Math.max(s - 1, 0));
    } else if (e.key === 'Enter' && flatItems[clampedSel]) {
      flatItems[clampedSel].action();
    }
  };

  const execute = (item: PaletteItem) => {
    Promise.resolve(item.action()).catch(console.error);
  };

  return (
    <PaletteContext.Provider value={{ open, close }}>
      {children}

      {/* ── Toast ──────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            key="palette-toast"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className={`fixed top-4 right-4 z-[400] rounded-xl border px-4 py-2.5 text-sm backdrop-blur-md
              ${toast.level === 'err'
                ? 'border-red-500/30 bg-red-950/70 text-red-200'
                : toast.level === 'warn'
                ? 'border-amber-500/30 bg-amber-950/70 text-amber-200'
                : 'border-emerald-500/30 bg-emerald-950/70 text-emerald-200'}`}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Palette modal ──────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              key="palette-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={close}
              className="fixed inset-0 z-[300] bg-black/70 backdrop-blur-sm"
            />

            {/* Panel */}
            <motion.div
              key="palette-panel"
              initial={{ opacity: 0, scale: 0.96, y: -16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: -8 }}
              transition={{ type: 'spring', stiffness: 400, damping: 32 }}
              className="fixed left-1/2 top-[14%] z-[310] w-full max-w-xl -translate-x-1/2
                         rounded-2xl border border-slate-700/60 bg-[#0c0c16]/95 shadow-2xl
                         overflow-hidden backdrop-blur-2xl"
            >
              {/* Search bar */}
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-800/60">
                <Search size={15} className="text-slate-500 shrink-0" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={e => { setQuery(e.target.value); setSelected(0); }}
                  onKeyDown={handleKey}
                  placeholder="Search commands, navigate, execute actions…"
                  className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-600 outline-none"
                  spellCheck={false}
                />
                <kbd
                  onClick={close}
                  className="text-[9px] tracking-widest text-slate-600 border border-slate-800 rounded px-1.5 py-0.5 cursor-pointer hover:text-slate-400"
                >
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-[420px] overflow-y-auto py-2 custom-scrollbar">
                {groups.length === 0 && (
                  <div className="py-8 text-center text-[11px] text-slate-600 tracking-widest">
                    NO COMMANDS MATCH "{query.toUpperCase()}"
                  </div>
                )}

                {(() => {
                  let globalIdx = 0;
                  return groups.map(([cat, items]) => (
                    <div key={cat} className="mb-2">
                      <div className="flex items-center gap-2 px-4 py-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${CATEGORY_DOT[cat]}`} />
                        <span className="text-[8px] font-black tracking-[0.25em] text-slate-600">
                          {CATEGORY_LABEL[cat]}
                        </span>
                      </div>
                      {items.map(item => {
                        const idx = globalIdx++;
                        const isActive = idx === clampedSel;
                        return (
                          <button
                            key={item.id}
                            onMouseEnter={() => setSelected(idx)}
                            onClick={() => execute(item)}
                            className={`w-full text-left flex items-center gap-3 px-4 py-2.5 transition-all
                              ${isActive
                                ? 'bg-white/[0.06] text-white'
                                : 'text-slate-400 hover:text-white'}`}
                          >
                            <span className={`shrink-0 ${isActive ? 'text-white' : 'text-slate-600'}`}>
                              {item.icon}
                            </span>
                            <span className="flex-1 min-w-0">
                              <span className="block text-sm font-medium">{item.label}</span>
                              {item.description && (
                                <span className="block text-[10px] text-slate-600 truncate">
                                  {item.description}
                                </span>
                              )}
                            </span>
                            {item.category === 'action' && (
                              <span className="shrink-0 text-[8px] tracking-widest text-red-600 border border-red-900 rounded px-1.5 py-px">
                                EXEC
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ));
                })()}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-800/60 bg-slate-950/40">
                <div className="flex items-center gap-4 text-[9px] text-slate-700">
                  <span><kbd className="bg-slate-800 rounded px-1">↑↓</kbd> navigate</span>
                  <span><kbd className="bg-slate-800 rounded px-1">↵</kbd> execute</span>
                  <span><kbd className="bg-slate-800 rounded px-1">ESC</kbd> close</span>
                </div>
                <span className="text-[8px] text-slate-700 tracking-widest">
                  PROJECTXY SOVEREIGN COMMAND
                </span>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </PaletteContext.Provider>
  );
}
