import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Network, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

export default function LateralMovementGraph() {
    const [graphData, setGraphData] = useState<{ nodes: any[], links: any[] }>({ nodes: [], links: [] });
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

    useEffect(() => {
        const fetchGraphData = async () => {
            setIsLoading(true);
            try {
                const data = await api.getGraph();
                if (data && data.nodes && data.links) {
                    setGraphData(data);
                } else {
                    console.warn("Fetched graph data is not in the expected format:", data);
                    setGraphData({ nodes: [], links: [] });
                }
            } catch (err) {
                console.error("Error fetching graph data:", err);
                setError("Failed to load Kill Chain graph.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchGraphData();
    }, []);

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

    const renderContent = () => {
        if (isLoading) {
            return <div className="text-slate-400 font-mono text-center animate-pulse">Loading Live Intel...</div>;
        }
        if (error) {
            return <div className="text-red-500 font-mono text-center">{error}</div>;
        }
        if (dimensions.width > 0 && graphData.nodes.length > 0) {
            return (
                <ForceGraph2D
                    graphData={graphData}
                    width={dimensions.width}
                    height={dimensions.height}
                    nodeAutoColorBy="group"
                    nodeRelSize={8}
                    linkColor={() => "rgba(239, 68, 68, 0.6)"}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    nodeCanvasObject={(node: any, ctx, globalScale) => {
                        const label = node.label || node.id;
                        const fontSize = 12 / globalScale;
                        ctx.font = `${fontSize}px Sans-Serif`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

                        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);

                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillStyle = node.risk === 'FATAL' ? '#ff4f4f' : '#ff9900';
                        ctx.fillText(label, node.x, node.y);

                        node.__bckgDimensions = bckgDimensions;
                    }}
                />
            );
        }
        return <div className="text-slate-500 font-mono text-center">No active threats detected.</div>;
    };

    return (
        <div className="bg-slate-900 border border-red-900/50 rounded-lg p-4 overflow-hidden shadow-2xl h-[400px] flex flex-col relative">
            <div className="flex items-center justify-between z-10 p-2">
                <h3 className="text-red-500 font-mono text-xl tracking-wider uppercase flex items-center">
                    <Network className="w-5 h-5 mr-2 text-red-500" />
                    Lateral Movement Detection
                </h3>
                {graphData.nodes.length > 0 && (
                    <span className="flex items-center text-xs text-red-400 bg-red-950 px-2 py-1 rounded border border-red-800">
                        <AlertTriangle className="w-3 h-3 mr-1 animate-pulse" />
                        ACTIVE KILL CHAIN
                    </span>
                )}
            </div>

            <div ref={containerRef} className="flex-1 w-full relative grid place-items-center">
                {renderContent()}
            </div>
        </div>
    );
}
