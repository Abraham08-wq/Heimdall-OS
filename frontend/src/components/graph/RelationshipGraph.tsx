'use client';

import dynamic from 'next/dynamic';
import { useRef, useEffect, useState } from 'react';
import { api } from '@/lib/api';

import { useCommand } from '@/context/CommandContext';

// Dynamic import to avoid SSR issues with canvas
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="text-center text-gray-500 mt-20 font-mono">Initializing Graph Engine...</div>
});

interface GraphData {
    nodes: any[];
    links: any[];
}

export default function RelationshipGraph({ entityId }: { entityId: string }) {
    const [dimensions, setDimensions] = useState({ w: 800, h: 600 });
    const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
    const containerRef = useRef<HTMLDivElement>(null);
    const { setSelectedTarget, setInterceptOpen } = useCommand();

    useEffect(() => {
        if (containerRef.current) {
            setDimensions({
                w: containerRef.current.clientWidth,
                h: containerRef.current.clientHeight
            });
        }

        const loadGraph = async () => {
            try {
                const data = await api.getGraphNeighborhood(entityId);
                setGraphData(data);
            } catch (err) {
                console.error("Failed to load graph data", err);
            }
        };

        if (entityId) {
            loadGraph();
        }

    }, [entityId]);

    return (
        <div ref={containerRef} className="w-full h-full">
            <ForceGraph2D
                width={dimensions.w}
                height={dimensions.h}
                graphData={graphData}
                nodeLabel="id"
                nodeColor={(node: any) => {
                    if (node.id === entityId) return '#00f3ff'; // Target
                    if (node.group === 3) return '#ff003c'; // Alert
                    return '#ffffff';
                }}
                linkColor={() => 'rgba(255,255,255,0.2)'}
                backgroundColor="#000000"
                nodeCanvasObject={(node: any, ctx, globalScale) => {
                    const label = node.id;
                    const fontSize = 12 / globalScale;
                    const isTarget = node.id === entityId;
                    const isTraceActive = node.active_trace === true; // Neo4j property

                    // Draw Node
                    const size = isTarget ? 8 : 6;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                    ctx.fillStyle = isTarget ? '#00f3ff' : (node.group === 3 ? '#ff003c' : '#ffffff');
                    ctx.fill();

                    // Trace Pulse Effect
                    if (isTraceActive) {
                        const time = Date.now();
                        const pulse = (Math.sin(time / 200) + 1) / 2; // 0 to 1
                        const pulseSize = size + (pulse * 10);

                        ctx.beginPath();
                        ctx.arc(node.x, node.y, pulseSize, 0, 2 * Math.PI, false);
                        ctx.strokeStyle = `rgba(255, 0, 60, ${1 - pulse})`;
                        ctx.lineWidth = 2 / globalScale;
                        ctx.stroke();

                        // Range Circle
                        ctx.beginPath();
                        ctx.arc(node.x, node.y, pulseSize * 2, 0, 2 * Math.PI, false);
                        ctx.strokeStyle = `rgba(255, 0, 60, ${0.2 * (1 - pulse)})`;
                        ctx.stroke();
                    }

                    // Label
                    ctx.font = `${fontSize}px Sans-Serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                    ctx.fillText(label, node.x, node.y + size + fontSize);
                }}
                onNodeClick={(node: any) => {
                    setSelectedTarget(node.id);
                    // Optional: auto-open modal or just select
                    // setInterceptOpen(true); 
                }}
            />
        </div>
    );
}
