import React from 'react';
import { Activity } from 'lucide-react';
import { clsx } from 'clsx';

interface TacticalFeedProps {
    feed: any[];
}

export const TacticalFeed: React.FC<TacticalFeedProps> = ({ feed }) => {
    return (
        <div className="glass-panel p-0 rounded-none border border-gray-800 bg-black/60 backdrop-blur-md flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-gray-800 bg-black/80 flex justify-between items-center">
                <h3 className="text-xs font-bold text-gray-400 tracking-[0.2em] flex items-center gap-2">
                    <Activity size={14} /> TACTICAL FEED
                </h3>
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {feed.length === 0 && <div className="text-gray-600 text-xs text-center py-4">Waiting for intel...</div>}
                {feed.map((item, i) => (
                    <div key={i} className="border-l-2 border-gray-800 pl-3 py-1 relative group hover:bg-white/5 transition-colors">
                        <div className={clsx("absolute left-[-2px] top-0 bottom-0 w-[2px] transition-colors",
                            item.source === 'SENTINEL' ? 'group-hover:bg-cyan-500' :
                                item.source === 'NEMESIS' ? 'group-hover:bg-red-500' : 'group-hover:bg-gray-500'
                        )}></div>

                        <div className="flex justify-between items-start mb-1">
                            <span className={clsx("text-[10px] font-bold px-1 rounded",
                                item.source === 'SENTINEL' ? 'bg-cyan-900/30 text-cyan-400' :
                                    item.source === 'NEMESIS' ? 'bg-red-900/30 text-red-500' : 'bg-gray-800 text-gray-400'
                            )}>{item.source}</span>
                            <span className="text-[10px] text-gray-600">{item.timestamp}</span>
                        </div>
                        <p className="text-xs text-gray-300 leading-relaxed font-sans">{item.message}</p>
                    </div>
                ))}
            </div>

            {/* Command Line Input Simulation */}
            <div className="p-2 bg-black border-t border-gray-800">
                <div className="flex items-center gap-2 text-xs font-mono text-gray-500">
                    <span>&gt;</span>
                    <span className="animate-pulse">_</span>
                </div>
            </div>
        </div>
    );
};
