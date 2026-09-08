import React, { useRef, useState, useEffect } from 'react';
import { Activity, Crosshair } from 'lucide-react';
import dynamic from 'next/dynamic';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-full text-cyan-500 font-mono animate-pulse">INITIALIZING NETWORK DISPLAY...</div>
}) as any;

interface GlobalOpsMapProps {
    globeRef: any;
    graphData: any;
    attackArcs: any[];
    onNavigateToDevices: () => void;
    onNodeClick?: (node: any) => void;
}

export const GlobalOpsMap: React.FC<GlobalOpsMapProps> = ({ globeRef, graphData, attackArcs, onNavigateToDevices, onNodeClick }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    useEffect(() => {
        if (!containerRef.current) return;
        const resizeObserver = new ResizeObserver((entries) => {
            for (let entry of entries) {
                setDimensions({
                    width: entry.contentRect.width,
                    height: entry.contentRect.height
                });
            }
        });
        resizeObserver.observe(containerRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    return (
        <div ref={containerRef} className="lg:col-span-2 relative h-full rounded-xl overflow-hidden border border-gray-800 bg-black z-10 group">
            <div className="absolute top-4 left-4 z-20 pointer-events-none">
                <h1 className="text-2xl font-bold font-mono text-white tracking-tighter">GLOBAL OPS</h1>
                <div className="flex items-center gap-2 text-red-500 text-xs font-bold animate-pulse">
                    <Activity size={12} /> LIVE MONITORING
                </div>
            </div>

            <div className="absolute top-4 right-4 z-20 pointer-events-auto">
                <button
                    onClick={onNavigateToDevices}
                    className="bg-red-600/20 hover:bg-red-600/40 border border-red-500 text-red-500 px-4 py-2 rounded text-xs font-bold tracking-widest backdrop-blur-sm transition-all flex items-center gap-2"
                >
                    <Crosshair size={14} /> ASSET RECOVERY
                </button>
            </div>

            {/* @ts-ignore */}
            {dimensions.width > 0 && (
                <ForceGraph2D
                    ref={globeRef}
                    graphData={graphData}
                    width={dimensions.width}
                    height={dimensions.height}
                    nodeLabel={(node: any) => `${node.name} ${node.os ? `[${node.os}]` : ''}`}
                    nodeColor={(node: any) => {
                        if (node.isScanning) return 'rgba(168, 85, 247, 0.8)'; // Purple for Omni-Probe scanning
                        return node.val > 8 ? '#ff0000' : '#00ffff';
                    }}
                    nodeRelSize={4}
                    linkColor={() => 'rgba(0,255,255,0.2)'}
                    backgroundColor="#000000"
                    enableNodeDrag={false}
                    warmupTicks={100}
                    cooldownTicks={0}
                    onEngineStop={() => globeRef?.current?.zoomToFit(400)}
                    onNodeClick={(node: any) => {
                        console.log("Focus:", node);
                        if (onNodeClick) {
                            onNodeClick(node);
                        }
                    }}
                    nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                        // Custom rendering for Omni-Probe radar effect
                        const size = node.val || 4;
                        if (node.isScanning) {
                            // Omni-Probe Scanning Animation
                            const time = Date.now() / 200;
                            const scanRadius = size * 3 * (1 + Math.sin(time));
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, scanRadius, 0, 2 * Math.PI, false);
                            ctx.strokeStyle = `rgba(168, 85, 247, ${Math.max(0, 1 - Math.sin(time))})`; // Fading purple ring
                            ctx.lineWidth = 2 / globalScale;
                            ctx.stroke();
                        }

                        ctx.beginPath();
                        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                        ctx.fillStyle = node.isScanning ? '#a855f7' : (node.val > 8 ? '#ff0000' : '#00ffff');
                        ctx.fill();

                        // Label rendering for Omni-Probe discovered OS/Ports
                        if (node.os && globalScale > 2) {
                            const label = `${node.name} [${node.os}]`;
                            const fontSize = 10 / globalScale;
                            ctx.font = `${fontSize}px Inter, monospace`;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillStyle = '#f8fafc';
                            ctx.fillText(label, node.x, node.y + size + (4 / globalScale));
                        }
                    }}
                />
            )}

            {/* Omni-Probe Active Sweep Indicator */}
            {graphData?.nodes?.some((n: any) => n.isScanning) && (
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 pointer-events-none w-full h-full flex items-center justify-center overflow-hidden mix-blend-screen">
                    <div className="w-[800px] h-[800px] rounded-full border border-purple-500/30 bg-[conic-gradient(from_0deg,transparent_0deg,transparent_270deg,rgba(168,85,247,0.2)_360deg)] animate-[spin_2s_linear_infinite]"></div>
                </div>
            )}

            {/* Decorative Hud Elements */}
            <div className="absolute bottom-4 left-4 z-20 pointer-events-none flex gap-1">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-1 w-8 bg-purple-900/50 pulse-glow"></div>
                ))}
            </div>
            <div className="absolute bottom-8 left-4 z-20 pointer-events-none font-mono text-[10px] text-purple-400 font-bold tracking-widest uppercase">
                {graphData?.nodes?.some((n: any) => n.isScanning) ? 'OMNI-PROBE SWEEP ACTIVE...' : 'OMNI-PROBE STANDBY'}
            </div>
            <div className="absolute top-1/2 left-4 w-1 h-32 bg-gradient-to-b from-transparent via-cyan-500/50 to-transparent"></div>
            <div className="absolute top-1/2 right-4 w-1 h-32 bg-gradient-to-b from-transparent via-red-500/50 to-transparent"></div>
        </div>
    );
};
