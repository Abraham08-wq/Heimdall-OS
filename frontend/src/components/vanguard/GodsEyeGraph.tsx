'use client'

import React, { useRef, useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { socketClient } from '@/lib/socket';
import { api } from '@/lib/api';

// Dynamically import force-graph to prevent SSR issues with canvas
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

interface GraphNode {
    id: string;
    group: number; // 1: Hostile, 2: Honeypot, 3: Internal Asset, 4: Digital Twin Sandbox
    val: number; // Node size (Risk score)
    name: string;
    type: string;
}

interface GraphLink {
    source: string;
    target: string;
    action: string;
}

interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
}

export const GodsEyeGraph = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Fetch initial graph state
    useEffect(() => {
        const fetchInitialGraph = async () => {
            setLoading(true);
            try {
                const data = await api.getGraph();
                if (data && data.nodes && data.links) {
                    setGraphData(data);
                } else {
                    // This case handles an empty but valid response
                    setGraphData({ nodes: [], links: [] });
                }
            } catch (err) {
                console.error("Failed to load initial graph state:", err);
                setError("Failed to load God's Eye graph data.");
            } finally {
                setLoading(false);
            }
        };
        fetchInitialGraph();
    }, []);


    // Listen for Real-Time Telemetry & Active Defense Actions
    useEffect(() => {
        if (!socketClient) return;
        setIsConnected(socketClient.isConnected());

        const handleGraphUpdate = (data: any) => {
            console.log("[GODS EYE] Receiving Telemetry payload...", data);
            setGraphData(prev => {
                const nodeMap = new Map(prev.nodes.map(n => [n.id, n]));
                if (data.nodes) {
                    data.nodes.forEach((n: GraphNode) => nodeMap.set(n.id, n));
                }

                const linkSet = new Set(prev.links.map(l => `${l.source}-${l.target}`));
                const newLinks = data.links ? data.links.filter((l: GraphLink) => !linkSet.has(`${l.source}-${l.target}`)) : [];

                return {
                    nodes: Array.from(nodeMap.values()),
                    links: [...prev.links, ...newLinks]
                };
            });
        };

        socketClient.subscribe('graph_update', handleGraphUpdate);
        socketClient.onConnect(() => setIsConnected(true));
        socketClient.onDisconnect(() => setIsConnected(false));


        return () => {
            socketClient.unsubscribe('graph_update', handleGraphUpdate);
        };
    }, []);

    const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        const label = node.name || node.id;
        const fontSize = 12 / globalScale;
        ctx.font = `${fontSize}px Inter, sans-serif`;

        let nodeColor = "#1e293b";
        let pulseGlow = false;

        if (node.group === 1) { nodeColor = "#ef4444"; pulseGlow = true; }
        else if (node.group === 2) { nodeColor = "#a855f7"; }
        else if (node.group === 3) { nodeColor = "#3b82f6"; }
        else if (node.group === 4) { nodeColor = "#eab308"; ctx.setLineDash([5, 5]); }

        if (pulseGlow) {
            const time = Date.now() / 300;
            const glowSize = node.val + Math.sin(time) * 2;
            ctx.beginPath();
            ctx.arc(node.x, node.y, glowSize, 0, 2 * Math.PI, false);
            ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
            ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false);
        ctx.fillStyle = nodeColor;
        ctx.fill();

        ctx.setLineDash([]);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#f8fafc';
        ctx.fillText(label, node.x, node.y + node.val + (4 / globalScale));
    }, []);

    const handleNodeClick = useCallback((node: any) => {
        if (node.group === 1) {
            console.log(`[VANGUARD SEC-OPS] Targeting Hostile Infra: ${node.id}`);
            alert(`TARGET LOCKED: ${node.name}\nInitiating Tier 2 AI Swarm Investigation...`);
            // api.triggerSwarmInvestigation(node.id);
        }
    }, []);

    return (
        <div className="relative w-full h-full min-h-[400px] bg-[#020617] rounded-xl border border-cyan-500/30 overflow-hidden shadow-[0_0_30px_rgba(6,182,212,0.1)] group">
            <div className="absolute inset-0 pointer-events-none z-50 opacity-10 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%] mix-blend-overlay"></div>

            <div className="absolute top-4 left-4 z-10 p-4 bg-slate-950/80 backdrop-blur-xl rounded-lg border border-slate-700/80 shadow-[0_0_20px_rgba(0,0,0,0.8)]">
                <h2 className="text-emerald-400 font-mono font-bold tracking-widest text-sm mb-1">
                    GODS EYE OMNI-GRAPH
                </h2>
                <div className="flex flex-col space-y-1 mt-3">
                    <div className="flex items-center text-xs text-slate-300">
                        <div className="w-3 h-3 rounded-full bg-blue-500 mr-2"></div> Internal Assets
                    </div>
                    <div className="flex items-center text-xs text-slate-300">
                        <div className="w-3 h-3 rounded-full bg-purple-500 mr-2"></div> Labyrinth (Honeypots)
                    </div>
                    <div className="flex items-center text-xs text-slate-300">
                        <div className="w-3 h-3 rounded-full bg-red-500 mr-2 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div> Hostile Infra
                    </div>
                    <div className="flex items-center text-xs text-slate-300">
                        <div className="w-3 h-3 rounded-full bg-yellow-500 mr-2 border-2 border-dashed border-slate-950"></div> Digital Twin Sandbox
                    </div>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-700">
                    <span className="text-xs text-slate-400 font-mono">
                        WS: {isConnected ? <span className="text-emerald-500">CONNECTED</span> : <span className="text-red-500">OFFLINE</span>}
                    </span>
                </div>
            </div>

            {loading && <div className="absolute inset-0 flex items-center justify-center text-slate-400 font-mono animate-pulse">Loading Live Topology...</div>}
            {error && <div className="absolute inset-0 flex items-center justify-center text-red-500 font-mono">{error}</div>}
            
            {!loading && !error && (
                <ForceGraph2D
                    graphData={graphData}
                    nodeCanvasObject={nodeCanvasObject}
                    onNodeClick={handleNodeClick}
                    backgroundColor="#020617"
                    linkColor={() => 'rgba(148, 163, 184, 0.4)'}
                    linkWidth={1.5}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    d3VelocityDecay={0.3}
                />
            )}
        </div>
    );
};
