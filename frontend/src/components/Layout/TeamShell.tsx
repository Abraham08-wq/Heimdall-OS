'use client';
import React from 'react';
import clsx from 'clsx';

export type Team = 'red' | 'blue' | 'purple' | 'platform';

export interface TeamShellProps {
  team: Team;
  title: string;
  subtitle?: string;
  badge?: string;
  children: React.ReactNode;
  className?: string;
}

export const TEAM_CONFIG = {
  red: {
    primary: '#FF2D20',
    bg: 'bg-[#0D0000]',
    headerBg: 'bg-gradient-to-r from-red-950 via-[#1a0000] to-[#0D0000]',
    border: 'border-red-900/50',
    glow: 'shadow-[0_1px_0_rgba(255,45,32,0.4)]',
    titleColor: 'text-red-400',
    subtitleColor: 'text-red-700',
    badgeBg: 'bg-red-950 text-red-400 border border-red-800',
    divider: 'from-transparent via-red-700/50 to-transparent',
    label: 'RED TEAM',
    classification: 'OFFENSIVE OPERATIONS',
    fontMono: true,
  },
  blue: {
    primary: '#0EA5E9',
    bg: 'bg-[#00091A]',
    headerBg: 'bg-gradient-to-r from-sky-950 via-[#000d1f] to-[#00091A]',
    border: 'border-sky-900/40',
    glow: 'shadow-[0_1px_0_rgba(14,165,233,0.3)]',
    titleColor: 'text-sky-400',
    subtitleColor: 'text-sky-700',
    badgeBg: 'bg-sky-950 text-sky-400 border border-sky-800',
    divider: 'from-transparent via-sky-600/40 to-transparent',
    label: 'BLUE TEAM',
    classification: 'DEFENSIVE OPERATIONS',
    fontMono: false,
  },
  purple: {
    primary: '#A855F7',
    bg: 'bg-[#0D0018]',
    headerBg: 'bg-gradient-to-r from-purple-950 via-[#120020] to-[#0D0018]',
    border: 'border-purple-900/40',
    glow: 'shadow-[0_1px_0_rgba(168,85,247,0.3)]',
    titleColor: 'text-purple-400',
    subtitleColor: 'text-purple-600',
    badgeBg: 'bg-purple-950 text-purple-400 border border-purple-800',
    divider: 'from-transparent via-purple-600/40 to-transparent',
    label: 'PURPLE TEAM',
    classification: 'THREAT INTELLIGENCE',
    fontMono: false,
  },
  platform: {
    primary: '#64748B',
    bg: 'bg-slate-950',
    headerBg: 'bg-gradient-to-r from-slate-900 to-slate-950',
    border: 'border-slate-700/40',
    glow: 'shadow-[0_1px_0_rgba(100,116,139,0.2)]',
    titleColor: 'text-slate-300',
    subtitleColor: 'text-slate-500',
    badgeBg: 'bg-slate-800 text-slate-400 border border-slate-700',
    divider: 'from-transparent via-slate-600/30 to-transparent',
    label: 'PLATFORM',
    classification: 'SYSTEM OPERATIONS',
    fontMono: false,
  },
} as const;

export function getTeamColors(team: Team) {
  return TEAM_CONFIG[team];
}

export function TeamBadge({ team, text }: { team: Team; text: string }) {
  const cfg = TEAM_CONFIG[team];
  return (
    <span className={clsx('text-[9px] font-black tracking-[0.2em] px-2 py-0.5 rounded', cfg.badgeBg)}>
      {text}
    </span>
  );
}

export function TeamShell({ team, title, subtitle, badge, children, className }: TeamShellProps) {
  const cfg = TEAM_CONFIG[team];
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <div className={clsx('min-h-screen relative flex flex-col', cfg.bg, className)}>
      <div className={clsx('border-b flex-shrink-0', cfg.border, cfg.headerBg, cfg.glow)}>
        <div className="px-6 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-black tracking-[0.25em] text-slate-500 uppercase">
                {cfg.classification}
              </span>
              <span className="w-px h-3 bg-slate-700" />
              <span className={clsx('text-[8px] font-black tracking-[0.2em] px-1.5 py-0.5 rounded', cfg.badgeBg)}>
                {cfg.label}
              </span>
              {badge && (
                <span className={clsx('text-[8px] font-black tracking-[0.2em] px-1.5 py-0.5 rounded animate-pulse', cfg.badgeBg)}>
                  {badge}
                </span>
              )}
            </div>
            <span className="text-[9px] font-mono text-slate-600 tabular-nums">{ts}</span>
          </div>
          <div>
            <h1 className={clsx('text-xl font-bold tracking-tight', cfg.titleColor, cfg.fontMono && 'font-mono')}>
              {title}
            </h1>
            {subtitle && (
              <p className={clsx('text-[11px] mt-0.5 font-mono tracking-wide', cfg.subtitleColor)}>
                {subtitle}
              </p>
            )}
          </div>
        </div>
        <div className={clsx('h-px bg-gradient-to-r', cfg.divider)} />
      </div>
      <div className="flex-1 overflow-auto">
        {children}
      </div>
    </div>
  );
}

export default TeamShell;
