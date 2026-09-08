import React from "react";

export default function NodeStatusGrid() {
  const nodes = [
    { id: "SEC-01", ip: "10.0.1.27", status: "ONLINE", load: "12%", ping: "14ms" },
    { id: "SEC-02", ip: "10.0.1.28", status: "ONLINE", load: "8%", ping: "22ms" },
    { id: "SEC-03", ip: "10.0.1.55", status: "OFFLINE", load: "--", ping: "--" },
    { id: "SEC-04", ip: "10.0.1.99", status: "EXECUTING", load: "94%", ping: "18ms" },
  ];

  return (
    <div className="industrial-panel flex flex-col h-full bg-surface">
      <div className="px-4 py-3 border-b border-surface-border bg-[#121214] flex justify-between items-center">
        <h2 className="text-sm tracking-[0.2em] font-bold text-muted uppercase">Execution Nodes</h2>
        <span className="text-xs font-mono text-primary border border-primary/30 px-2 py-0.5 bg-primary/10">3 / 4 ACTIVE</span>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="text-muted border-b border-surface-border uppercase tracking-widest text-[10px]">
              <th className="pb-3 font-normal">Node ID</th>
              <th className="pb-3 font-normal">Internal IP</th>
              <th className="pb-3 font-normal">Ping</th>
              <th className="pb-3 font-normal">Status</th>
            </tr>
          </thead>
          <tbody className="font-mono text-[13px]">
            {nodes.map((node, i) => (
              <tr key={node.id} className={`border-b border-surface-border/50 hover:bg-white/[0.02] transition-colors ${i % 2 === 0 ? 'bg-transparent' : 'bg-[#0c0c0e]'}`}>
                <td className="py-3 font-bold text-white">{node.id}</td>
                <td className="py-3 text-muted">{node.ip}</td>
                <td className="py-3 text-primary">{node.ping}</td>
                <td className="py-3">
                    <span className={`px-2 py-1 flex items-center w-fit border ${
                        node.status === 'ONLINE' ? 'text-success border-success/30 bg-success/10' : 
                        node.status === 'OFFLINE' ? 'text-alert border-alert/30 bg-alert/10' : 
                        'text-warning border-warning/30 bg-warning/10 animate-pulse'
                    }`}>
                        <span className={`w-1.5 h-1.5 mr-2 bg-current block ${node.status === 'ONLINE' && 'animate-blink'}`}></span>
                        {node.status}
                    </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
