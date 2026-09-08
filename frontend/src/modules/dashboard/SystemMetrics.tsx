import React from 'react';
import { Cpu } from 'lucide-react';
import { api } from '@/lib/api';

export const SystemMetrics: React.FC = () => {
    const [mounted, setMounted] = React.useState(false);
    const [metrics, setMetrics] = React.useState<any>(null);

    React.useEffect(() => {
        setMounted(true);
        const fetchMetrics = async () => {
            try {
                const data = await api.getStats();
                setMetrics(data);
            } catch (err) {
                console.error("Metrics polling failed", err);
            }
        };
        fetchMetrics();
        const interval = setInterval(fetchMetrics, 5000);
        return () => clearInterval(interval);
    }, []);

    const displayMetrics = [
        { key: 'CPU', value: metrics?.cpu },
        { key: 'MEM', value: metrics?.mem },
        { key: 'NET', value: metrics?.net },
        { key: 'I/O', value: metrics?.io }
    ];

    return (
        <div className="flex-1 glass-panel p-4 rounded-none border border-gray-800 bg-black/40 backdrop-blur-md flex flex-col">
            <h3 className="text-xs font-bold text-gray-500 tracking-[0.2em] mb-4 flex items-center gap-2">
                <Cpu size={14} /> SYSTEM METRICS
            </h3>
            <div className="flex-1 grid grid-cols-2 gap-2">
                {displayMetrics.map(metric => (
                    <div key={metric.key} className="bg-black/50 border border-gray-800 p-2 flex flex-col justify-center items-center gap-1 group hover:border-cyan-500/50 transition-colors">
                        <div className="w-8 h-8 rounded-full border-2 border-gray-700 group-hover:border-cyan-500 flex items-center justify-center text-[10px] text-gray-500 group-hover:text-cyan-400 relative">
                            {metric.key}
                            <div className="absolute inset-0 rounded-full border-t-2 border-cyan-500 animate-spin opacity-0 group-hover:opacity-100"></div>
                        </div>
                        <span className="text-lg font-bold text-gray-300">
                            {mounted && metric.value !== undefined ? `${metric.value}%` : '--%'}
                        </span>
                    </div>
                ))}
            </div>

            <div className="mt-4 border-t border-gray-800 pt-3">
                <h4 className="text-[10px] text-cyan-500 font-bold mb-2 tracking-widest">SECURITY HARDENING REPORT</h4>
                <ul className="text-[10px] text-gray-400 space-y-1 font-mono">
                    <li className="flex justify-between"><span>Audit Ledger:</span> <span className="text-emerald-500">SEALED (Merkle)</span></li>
                    <li className="flex justify-between"><span>AI Gatekeeper:</span> <span className="text-emerald-500">ACTIVE</span></li>
                    <li className="flex justify-between"><span>WebSocket Sync:</span> <span className="text-emerald-500">REDIS PUB/SUB</span></li>
                    <li className="flex justify-between"><span>Tenant Isolation:</span> <span className="text-emerald-500">STRICT (org_id)</span></li>
                    <li className="flex justify-between"><span>eBPF Handoff:</span> <span className="text-amber-500">BLUEPRINTED</span></li>
                </ul>
            </div>
        </div>
    );
};
