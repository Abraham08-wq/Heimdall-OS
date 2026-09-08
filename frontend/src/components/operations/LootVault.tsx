"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";

interface LootItem {
  id: string;
  source: string;
  loot_type: string;
  content: string;
  created_at: string;
}

export default function LootVault() {
  const [lootItems, setLootItems] = useState<LootItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchLoot = async () => {
    try {
      setLoading(true);
      // In a real environment, this connects to the actual API backend
      const res = await fetch("/api/v1/ops/loot", {
          credentials: 'include',
          headers: {
            "Accept": "application/json"
          }
      });
      if (res.ok) {
        const data = await res.json();
        setLootItems(data);
      }
    } catch (e) {
      console.error("Failed to fetch loot", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLoot();
    // Poll for new loot every 10 seconds during an active operation
    const interval = setInterval(fetchLoot, 10000);
    return () => clearInterval(interval);
  }, []);

  const getTypeStyle = (type: string) => {
    switch (type) {
      case "AWS_KEY": return "text-alert bg-alert/10 border-alert/30";
      case "STRIPE_KEY": return "text-purple-400 bg-purple-400/10 border-purple-400/30";
      case "SSH_PRIVATE_KEY": return "text-blue-400 bg-blue-400/10 border-blue-400/30";
      case "GENERIC_PASSWORD": return "text-yellow-400 bg-yellow-400/10 border-yellow-400/30";
      default: return "text-primary bg-primary/10 border-primary/30";
    }
  };

  return (
    <div className="industrial-panel flex flex-col h-full bg-surface">
      <div className="flex justify-between items-center px-4 py-2 border-b border-surface-border bg-[#121214]">
        <h2 className="text-sm tracking-[0.2em] font-bold text-muted">LOOT VAULT // AUTOMATED EXTRACTION</h2>
        <button 
            onClick={fetchLoot}
            className="text-xs font-mono text-primary flex items-center space-x-2 px-2 py-1 hover:bg-white/[0.05] rounded transition"
            disabled={loading}
        >
          <span className={`w-2 h-2 bg-primary ${loading ? 'animate-pulse' : ''}`}></span>
          <span>{loading ? "SYNCING..." : "LIVE SYNC"}</span>
        </button>
      </div>
      
      <div className="flex-1 overflow-auto p-4 custom-scrollbar">
        {lootItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted opacity-50 font-mono text-sm space-y-4">
                <div className="w-12 h-12 border border-dashed border-muted rounded-full flex items-center justify-center">
                    <span className="text-xl">Ø</span>
                </div>
                <p>NO LOOT EXTRACTED. AWAITING TELEMETRY...</p>
            </div>
        ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {lootItems.map((item) => (
                <div key={item.id} className="border border-surface-border bg-[#121214] p-4 flex flex-col space-y-3 shadow-md hover:border-primary/50 transition duration-300">
                    <div className="flex justify-between items-start">
                        <span className={`text-[10px] font-bold tracking-widest px-2 py-0.5 border ${getTypeStyle(item.loot_type)} rounded uppercase`}>
                            {item.loot_type}
                        </span>
                        <span className="text-[10px] font-mono text-muted">
                            {format(new Date(item.created_at), 'HH:mm:ss')}
                        </span>
                    </div>
                    
                    <div className="font-mono text-sm text-white break-all bg-black p-2 rounded border border-white/5 select-all">
                        {item.loot_type === 'SSH_PRIVATE_KEY' 
                            ? item.content.slice(0, 100) + '...' // Truncate long keys for presentation
                            : item.content
                        }
                    </div>
                    
                    <div className="flex items-center text-[11px] font-mono text-muted mt-auto pt-2 border-t border-surface-border/50">
                        <span className="text-success mr-2">SOURCE:</span> 
                        {item.source || "UNKNOWN_NODE"}
                    </div>
                </div>
            ))}
            </div>
        )}
      </div>
    </div>
  );
}
