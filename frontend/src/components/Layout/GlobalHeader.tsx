"use client";

import React, { useEffect } from 'react';
import { useUIStore } from '@/store/uiStore';
import { Activity, Terminal } from 'lucide-react';
import { clsx } from 'clsx';

const GlobalHeader = () => {
    const { securityPulse, toggleIntercept } = useUIStore();

    // Keyboard shortcut for Omni-Probe (Ctrl+Space)
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.code === 'Space') {
                e.preventDefault();
                toggleIntercept();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [toggleIntercept]);

    return (
        <header className="h-16 bg-[#0a0a0a]/80 backdrop-blur-md border-b border-[#1f1f1f] flex items-center justify-between px-6 fixed top-0 right-0 left-0 z-30 lg:left-64 transition-all">
            {/* Left: Breadcrumbs or Status */}
            <div className="flex items-center gap-4">
                <div className="flex flex-col">
                    <span className="text-xs text-gray-500 uppercase tracking-widest">Global Threat Level</span>
                    <div className="flex items-center gap-2">
                        <Activity size={16} className={clsx(
                            securityPulse < 50 ? "text-red-500" : "text-green-500"
                        )} />
                        <span className={clsx(
                            "font-mono font-bold",
                            securityPulse < 50 ? "text-red-500" : "text-green-500"
                        )}>{securityPulse}%</span>
                    </div>
                </div>
            </div>

            {/* Right: Omni-Probe Trigger */}
            <button
                onClick={() => toggleIntercept()}
                className="group flex items-center gap-2 bg-[#1f1f1f] hover:bg-red-900/20 border border-gray-700 hover:border-red-500/50 px-4 py-2 rounded-full transition-all"
            >
                <Terminal size={12} className="text-gray-400 group-hover:text-red-400" />
                <span className="text-xs font-mono text-gray-300 group-hover:text-red-300">OMNI-PROBE</span>
                <span className="ml-2 text-[10px] px-1 bg-gray-800 rounded text-gray-500">CTRL+SPC</span>
            </button>
        </header>
    );
};

export default GlobalHeader;
