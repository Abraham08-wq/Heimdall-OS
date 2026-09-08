import React, { useState, useEffect } from 'react';
import { ShieldAlert, Terminal } from 'lucide-react';
import { clsx } from 'clsx';

interface DefensiveAction {
    action: string;
    target: string;
    status: 'EXECUTED' | 'PENDING_USER' | 'FAILED';
    timestamp: string;
}

interface DefensiveActionsPanelProps {
    actions: DefensiveAction[];
}

export const DefensiveActionsPanel: React.FC<DefensiveActionsPanelProps> = ({ actions }) => {
    return (
        <div className="flex flex-col h-full w-full bg-slate-950/80 backdrop-blur-md border border-slate-800 rounded-lg overflow-hidden font-mono relative">
            {/* Header */}
            <div className="p-3 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center z-10">
                <h3 className="text-xs font-bold text-slate-300 tracking-widest flex items-center gap-2">
                    <ShieldAlert size={14} className="text-emerald-500" /> DEFENSIVE ACTIONS
                </h3>
                <div className="flex gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                </div>
            </div>

            {/* Actions Feed / Virtual Terminal */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2 z-10 custom-scrollbar">
                {actions.length === 0 && (
                    <div className="text-slate-600 text-xs text-center py-8">
                        No defensive mitigations actively deployed.
                    </div>
                )}
                {actions.map((act, i) => (
                    <div key={i} className="flex flex-col gap-1 p-2 bg-slate-900/30 border-l-2 border-emerald-500/50 hover:bg-slate-800/50 transition-colors group">
                        <div className="flex justify-between items-center">
                            <span suppressHydrationWarning className="text-[10px] text-slate-500">{act.timestamp}</span>
                            <span className={clsx(
                                "text-[9px] font-bold px-1.5 py-0.5 rounded",
                                act.status === 'EXECUTED' ? 'bg-emerald-900/30 text-emerald-400' :
                                    act.status === 'PENDING_USER' ? 'bg-amber-900/30 text-amber-400' :
                                        'bg-rose-900/30 text-rose-500'
                            )}>
                                {act.status}
                            </span>
                        </div>
                        <div className="flex gap-2 items-start">
                            <Terminal size={12} className="text-slate-600 mt-1 shrink-0" />
                            <p className="text-xs text-slate-300">
                                <span className="font-bold text-emerald-500">{act.action}</span> applied to <span className="text-slate-400">{act.target}</span>
                            </p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Terminal glow effect */}
            <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-emerald-900/10 to-transparent pointer-events-none z-0"></div>
        </div >
    );
};
