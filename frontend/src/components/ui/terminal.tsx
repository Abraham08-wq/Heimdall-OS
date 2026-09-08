'use client';
// ui/terminal.tsx — Terminal display component stub
// Used by SovereignBoardroom for the Context-Aware Action Terminal panel
import React, { useEffect, useRef } from 'react';

interface TerminalLine {
  type?: 'info' | 'success' | 'warning' | 'error' | 'command';
  text: string;
  ts?: string;
}

interface TerminalProps {
  lines?: TerminalLine[];
  children?: React.ReactNode;
  className?: string;
  title?: string;
}

const LINE_COLORS: Record<string, string> = {
  info: 'text-slate-300',
  success: 'text-emerald-400',
  warning: 'text-amber-400',
  error: 'text-rose-400',
  command: 'text-cyan-400',
};

export function Terminal({ lines = [], children, className = '', title = 'TERMINAL' }: TerminalProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [lines]);

  return (
    <div className={`rounded-xl border border-white/10 bg-[#0a0a0a] font-mono text-xs overflow-hidden ${className}`}>
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-white/5">
        <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        <span className="ml-2 text-[10px] uppercase tracking-widest text-slate-500">{title}</span>
      </div>
      {/* Content */}
      <div className="h-48 overflow-y-auto p-4 space-y-0.5">
        {lines.length > 0
          ? lines.map((line, i) => (
              <div key={i} className={`${LINE_COLORS[line.type || 'info'] ?? 'text-slate-300'}`}>
                {line.ts && <span className="text-slate-600 mr-2">[{line.ts}]</span>}
                {line.text}
              </div>
            ))
          : children}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
