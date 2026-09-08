import React from 'react';
import { Shield } from 'lucide-react';
import { clsx } from 'clsx';

interface SentinelStatusProps {
    status: any;
}

const getThreatColor = (level: string) => {
    switch (level) {
        case 'CRITICAL': return 'text-red-600 drop-shadow-[0_0_10px_rgba(220,38,38,0.8)]';
        case 'HIGH': return 'text-orange-500';
        case 'ELEVATED': return 'text-yellow-400';
        default: return 'text-green-500';
    }
};

export const SentinelStatus: React.FC<SentinelStatusProps> = ({ status }) => {
    return (
        <div className="glass-panel p-6 rounded-none border-l-4 border-l-cyan-500 bg-black/40 backdrop-blur-md relative overflow-hidden">
            <div className="absolute top-0 right-0 p-2 opacity-50"><Shield size={48} className="text-cyan-900" /></div>
            <h2 className="text-xs font-bold text-cyan-500 tracking-[0.2em] mb-4">SENTINEL A.I. STATUS</h2>

            <div className="flex flex-col items-center justify-center py-6 gap-2">
                <div className={clsx("text-4xl font-black tracking-widest animate-pulse", getThreatColor(status?.threat_level || 'LOW'))}>
                    {status?.threat_level || 'ANALYZING...'}
                </div>
                <div className="text-xs text-gray-500 uppercase">Current Threat Defcon</div>
            </div>

            <div className="space-y-4 mt-4 text-xs">
                <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                    <span className="text-gray-400">INTEGRITY</span>
                    <div className="flex items-center gap-2">
                        <div className="h-1 w-16 bg-gray-800 rounded-full overflow-hidden">
                            <div className="h-full bg-cyan-500" style={{ width: `${status?.integrity_score || 0}%` }}></div>
                        </div>
                        <span className="text-cyan-400">{status?.integrity_score || 0}%</span>
                    </div>
                </div>
                <div className="flex justify-between items-center border-b border-gray-800 pb-2">
                    <span className="text-gray-400">ACTIVE RELAYS</span>
                    <span className="text-green-400">{status?.active_defenses || 0} NODES</span>
                </div>
            </div>
        </div>
    );
};
