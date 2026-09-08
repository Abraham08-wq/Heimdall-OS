import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api'; // Import the api singleton

interface SystemStats {
  blocked_requests: number;
  total_requests: number;
  pii_events: number;
  avg_threat_score: number;
  pipeline: string;
  cpu: number;
  mem: number;
  net: number;
  io: number;
}

/**
 * SOVEREIGN BOARDROOM UI BLUEPRINT
 * "A God View of the Internet"
 * Combines Kinetic Graph Visualization, Global Risk Pulses, Financial Value metrics,
 * and the Context-Aware Action Terminal.
 */

export default function SovereignBoardroom() {
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  const [terminalHistory, setTerminalHistory] = useState([
    { context: "system", message: "Sovereign Enterprise System Online..." },
    { context: "intel", message: "Connecting to backend..." }
  ]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const stats = await api.getStats();
      setSystemStats(stats);
      if (loading) { // Only add this message on initial load
        setTerminalHistory(prev => [...prev, { context: "system", message: "System stats loaded." }]);
      }
    } catch (err) {
      setError('Failed to fetch system stats.');
      setTerminalHistory(prev => [...prev, { context: "error", message: "Error: Could not connect to stats service." }]);
    } finally {
      if (loading) setLoading(false);
    }
  }, [loading]);

  useEffect(() => {
    fetchStats(); // Fetch on initial render
    const interval = setInterval(fetchStats, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleTerminalCommand = async (command: string) => {
    setTerminalHistory(prev => [...prev, { context: "user", message: `> ${command}` }]);
    
    try {
        if (command.startsWith('DE-MASK')) {
            const alias = command.split(' ')[1];
            if (!alias) {
              setTerminalHistory(prev => [...prev, { context: "error", message: `Usage: DE-MASK <alias>` }]);
              return;
            }
            setTerminalHistory(prev => [...prev, { context: "intel", message: `[Neural Sync] De-Masking ${alias}...` }]);
            const results = await api.searchOSINT(alias);
            setTerminalHistory(prev => [...prev, { context: "intel", message: `Found ${results.length} OSINT records.` }]);
        } else if (command.startsWith('QUARANTINE')) {
            const node = command.split(' ')[1];
            if (!node) {
              setTerminalHistory(prev => [...prev, { context: "error", message: `Usage: QUARANTINE <node_ip>` }]);
              return;
            }
            setTerminalHistory(prev => [...prev, { context: "action", message: `[Shield Protocol] Spawning Shadow Sandbox for ${node}...` }]);
            await api.quarantineNode(node);
            setTerminalHistory(prev => [...prev, { context: "action", message: `Node ${node} successfully quarantined.` }]);
        } else if (command === 'SIMULATE_FAILURE') {
            setTerminalHistory(prev => [...prev, { context: "system", message: `[Simulation] Simulating critical node failure...` }]);
            const scenario = await api.generateScenario('hard');
            setTerminalHistory(prev => [...prev, { context: "system", message: `Scenario ${scenario.id || 'generated'}.` }]);
        } else {
            setTerminalHistory(prev => [...prev, { context: "error", message: `Unknown command: ${command}` }]);
        }
    } catch (err) {
        setTerminalHistory(prev => [...prev, { context: "error", message: `Command failed: ${(err as Error).message}` }]);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-50 p-6 overscroll-none overflow-hidden space-x-6">
      
      {/* LEFT COLUMN: THE GOD VIEW & ACTION TERMINAL */}
      <div className="flex-1 flex flex-col space-y-6 overflow-hidden">
        
        {/* Kinetic Visualization (Neo4j Graph Proxy) */}
        <Card className="flex-[2] bg-slate-900 border-slate-800 relative overflow-hidden shadow-2xl">
          <CardHeader>
            <CardTitle className="text-emerald-400 font-mono text-sm uppercase tracking-widest flex items-center">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-2"></span>
              The God View (Kinetic Link Particles)
            </CardTitle>
          </CardHeader>
          <CardContent className="absolute inset-0 top-16 flex items-center justify-center p-0">
            <div className="relative w-full h-full bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-800 via-slate-900 to-slate-950 opacity-80 grid place-items-center">
               <span className="text-slate-500/50 uppercase font-mono tracking-[0.2em] text-sm">Interactive WebGL Graph Render Space</span>
            </div>
          </CardContent>
        </Card>

        {/* The Action Terminal */}
        <Card className="flex-1 bg-black border-slate-800 flex flex-col font-mono shadow-inner shadow-slate-900/50">
          <CardHeader className="bg-slate-900/50 border-b border-slate-800 py-3">
            <CardTitle className="text-slate-300 text-xs tracking-wider">CONTEXT-AWARE SHELL // SOVEREIGN TERMINAL</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 p-4 overflow-y-auto min-h-0 flex flex-col text-sm space-y-2">
            {terminalHistory.map((item, idx) => (
              <div key={idx} className={
                item.context === 'error' ? 'text-rose-400' : 
                item.context === 'system' ? 'text-slate-400' : 
                item.context === 'action' ? 'text-amber-400 font-bold' : 
                'text-emerald-400'
              }>
                {item.message}
              </div>
            ))}
            <div className="flex items-center mt-auto pt-4">
              <span className="text-slate-500 mr-2">SYS_ADMIN@HQ:~#</span>
              <input 
                 type="text" 
                 className="flex-1 bg-transparent outline-none text-emerald-300 border-none placeholder-slate-700" 
                 placeholder="Type DE-MASK <alias> or QUARANTINE <ip>..."
                 onKeyDown={(e) => {
                   if (e.key === 'Enter' && e.currentTarget.value) {
                     handleTerminalCommand(e.currentTarget.value);
                     e.currentTarget.value = '';
                   }
                 }}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* RIGHT COLUMN: EXECUTIVE BOARDROOM (FINANCIAL RISK) */}
      <div className="w-96 flex flex-col space-y-6">
        <Card className="bg-slate-900 border-slate-800 h-full flex flex-col shadow-2xl shadow-emerald-900/10">
          <CardHeader className="border-b border-slate-800/60 pb-4">
            <CardTitle className="text-slate-100 text-lg uppercase tracking-wider font-semibold">The Boardroom Panel</CardTitle>
            <p className="text-xs text-slate-500 font-mono mt-2">Real-Time System & Security Stats</p>
          </CardHeader>
          
          <CardContent className="flex-1 flex flex-col p-6 space-y-6">
            {loading && <div className="text-center p-8 text-gray-400 animate-pulse">Loading Live Stats...</div>}
            {error && <div className="text-center p-8 text-rose-400">{error}</div>}
            {systemStats && (
                <>
                {/* Metric 1 */}
                <div className="flex flex-col space-y-2">
                  <span className="text-xs uppercase font-mono text-slate-400 tracking-wider">Blocked Requests</span>
                  <span className="text-4xl font-light text-emerald-400 font-mono tracking-tight">
                      {systemStats.blocked_requests.toLocaleString()}
                  </span>
                  <span className="text-xs text-emerald-500/70">Out of {systemStats.total_requests.toLocaleString()} total requests</span>
                </div>

                <div className="w-full h-px bg-slate-800/50" />

                {/* Metric 2 */}
                <div className="flex flex-col space-y-2">
                  <span className="text-xs uppercase font-mono text-slate-400 tracking-wider">PII Events Scrubbed</span>
                  <span className="text-4xl font-light text-amber-400 font-mono tracking-tight">
                      {systemStats.pii_events.toLocaleString()}
                  </span>
                  <span className="text-xs text-amber-500/70">Avg. Threat Score: {systemStats.avg_threat_score}</span>
                </div>

                <div className="w-full h-px bg-slate-800/50" />

                {/* System Health */}
                <div className="flex flex-col space-y-4">
                    <div className="flex justify-between items-center">
                        <span className="text-xs uppercase font-mono text-slate-400">System Health</span>
                        <span className={`text-xs font-mono font-bold px-2 py-1 rounded ${systemStats.pipeline === "Active" ? "text-green-400 bg-green-500/10" : "text-rose-400 bg-rose-500/10"}`}>{systemStats.pipeline}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                        <div><span className="text-slate-400">CPU:</span> <span className="text-cyan-300">{systemStats.cpu}%</span></div>
                        <div><span className="text-slate-400">MEM:</span> <span className="text-cyan-300">{systemStats.mem}%</span></div>
                        <div><span className="text-slate-400">NET:</span> <span className="text-cyan-300">{systemStats.net}%</span></div>
                        <div><span className="text-slate-400"> I/O:</span> <span className="text-cyan-300">{systemStats.io}%</span></div>
                    </div>
                </div>

                <div className="mt-auto pt-6">
                  <button disabled className="w-full py-3 bg-slate-800 text-slate-400 font-mono text-xs uppercase tracking-widest rounded border border-slate-700 hover:bg-slate-700 transition-colors shadow-lg">
                      Generate Board Report
                  </button>
                </div>
            </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
