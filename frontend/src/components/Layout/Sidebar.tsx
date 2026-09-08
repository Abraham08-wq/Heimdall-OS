'use client';
import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import clsx from 'clsx';
import {
  Terminal, Zap, Crosshair,
  Shield, Search, Cpu, ShieldCheck,
  LayoutDashboard, Network, Globe, Activity, Eye, KeyRound,
  Map, ThermometerSun, Database, Command,
} from 'lucide-react';

// ── Team Section Definitions ──────────────────────────────────────────────────

const RED_TEAM = {
  label: 'RED TEAM',
  dot: 'bg-red-500',
  headerColor: 'text-red-600',
  topBorder: 'border-red-900/60',
  activeBg: 'bg-red-950/40 border-red-700 text-red-400',
  hoverBg: 'hover:bg-red-950/20 hover:text-red-500',
  items: [
    { name: 'Ghost Shell',      path: '/ghost',            icon: Terminal,  },
    { name: 'Exploit Workbench',path: '/redteam/exploits', icon: Zap,       },
    { name: 'Red Team Ops',     path: '/redteam',          icon: Crosshair, },
  ],
};

const BLUE_TEAM = {
  label: 'BLUE TEAM',
  dot: 'bg-sky-500',
  headerColor: 'text-sky-600',
  topBorder: 'border-sky-900/50',
  activeBg: 'bg-sky-950/40 border-sky-600 text-sky-400',
  hoverBg: 'hover:bg-sky-950/20 hover:text-sky-400',
  items: [
    { name: 'SOC Command',    path: '/defense',       icon: Shield,      },
    { name: 'Threat Hunt',    path: '/defense/hunt',  icon: Search,      },
    { name: 'Guardian IoT',   path: '/guardian',      icon: Cpu,         },
    { name: 'AI Firewall',    path: '/firewall',      icon: ShieldCheck, badge: 'LIVE' },
  ],
};

const PURPLE_TEAM = {
  label: 'PURPLE TEAM',
  dot: 'bg-purple-500',
  headerColor: 'text-purple-600',
  topBorder: 'border-purple-900/50',
  activeBg: 'bg-purple-950/40 border-purple-600 text-purple-400',
  hoverBg: 'hover:bg-purple-950/20 hover:text-purple-400',
  items: [
    { name: 'Situation Room',    path: '/',                       icon: LayoutDashboard },
    { name: 'Intel Graph',       path: '/entities',               icon: Network         },
    { name: 'Intelligence Map',  path: '/intelligence',           icon: Globe           },
    { name: 'Anomaly Matrix',    path: '/anomalies',              icon: Activity        },
    { name: 'Autonomous SOC',    path: '/intelligence/soc',       icon: Eye             },
    { name: 'Adversarial Intel', path: '/intelligence/adversarial', icon: Command       },
    { name: 'Immutable Ledger',  path: '/ledger',                 icon: KeyRound        },
  ],
};

const PLATFORM = {
  label: 'PLATFORM',
  dot: 'bg-slate-500',
  headerColor: 'text-slate-500',
  topBorder: 'border-slate-800',
  activeBg: 'bg-slate-800/50 border-slate-600 text-slate-300',
  hoverBg: 'hover:bg-slate-800/30 hover:text-slate-400',
  items: [
    { name: 'Device Registry',       path: '/devices',        icon: Map            },
    { name: 'Threat Heatmaps',       path: '/heatmaps',       icon: ThermometerSun },
    { name: 'Infrastructure Grid',   path: '/infrastructure', icon: Database       },
  ],
};

const SECTIONS = [RED_TEAM, BLUE_TEAM, PURPLE_TEAM, PLATFORM];

// ── Component ─────────────────────────────────────────────────────────────────

const Sidebar = () => {
  const pathname = usePathname();

  return (
    <aside className="
      fixed left-0 top-0 h-screen z-40
      w-14 lg:w-56
      bg-[#080810] border-r border-slate-800/60
      flex flex-col overflow-y-auto overflow-x-hidden
      scrollbar-thin scrollbar-thumb-slate-800
    ">
      {/* Logo */}
      <div className="flex items-center gap-3 px-3 py-4 border-b border-slate-800/60">
        <div className="
          w-8 h-8 rounded-lg flex-shrink-0
          bg-gradient-to-br from-purple-600 via-sky-500 to-red-500
          flex items-center justify-center
          shadow-[0_0_12px_rgba(168,85,247,0.4)]
        ">
          <ShieldCheck size={16} className="text-white" />
        </div>
        <div className="hidden lg:block">
          <p className="text-[11px] font-black tracking-widest text-white">PROJECTXY</p>
          <p className="text-[9px] tracking-[0.2em] text-slate-500 font-mono">COGNITIVE SHIELD</p>
        </div>
      </div>

      {/* Team Sections */}
      <nav className="flex-1 py-2">
        {SECTIONS.map((section) => {
          return (
            <div key={section.label} className={clsx('border-t', section.topBorder, 'mt-1 pt-1')}>
              {/* Section header */}
              <div className="flex items-center gap-2 px-3 py-1.5 mb-0.5">
                <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', section.dot)} />
                <span className={clsx(
                  'hidden lg:block text-[8px] font-black tracking-[0.25em] uppercase',
                  section.headerColor
                )}>
                  {section.label}
                </span>
              </div>

              {/* Nav items */}
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = item.path === '/'
                  ? pathname === '/'
                  : pathname === item.path || pathname.startsWith(item.path + '/');

                return (
                  <Link
                    key={item.path + item.name}
                    href={item.path}
                    prefetch={false}
                    className={clsx(
                      'flex items-center gap-3 mx-1.5 px-2 py-2 rounded-md transition-all duration-150 border-l-2',
                      isActive
                        ? [section.activeBg, 'border-l-2']
                        : ['text-slate-600 border-transparent', section.hoverBg]
                    )}
                  >
                    <Icon size={15} className="flex-shrink-0" />
                    <span className="hidden lg:flex items-center gap-1.5 text-[11px] font-medium tracking-wide flex-1 min-w-0">
                      <span className="truncate">{item.name}</span>
                      {'badge' in item && (
                        <span className="ml-auto text-[7px] font-black tracking-widest bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 px-1 py-px rounded animate-pulse flex-shrink-0">
                          {(item as any).badge}
                        </span>
                      )}
                    </span>
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-800/60 px-3 py-3 mt-auto">
        <div className="hidden lg:flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[9px] font-mono text-slate-600">SHIELD ACTIVE</span>
        </div>
        <div className="lg:hidden flex justify-center">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
