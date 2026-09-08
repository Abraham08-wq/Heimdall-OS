import React, { useRef, useState, useEffect } from 'react';
import dynamic from 'next/dynamic';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-full text-cyan-500 font-mono animate-pulse">CALIBRATING KINETIC SENSORS...</div>
}) as any;

interface PulseGraphProps {
    graphData: any;
    onNodeClick?: (node: any) => void;
}

export const PulseGraph: React.FC<PulseGraphProps> = ({ graphData, onNodeClick }) => {
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

    const paintRing = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
        const { x, y } = node;
        const size = node.val || 4;
        const risk = node.risk_score || 0;

        // Base Node
        ctx.beginPath();
        ctx.arc(x, y, size, 0, 2 * Math.PI, false);
        ctx.fillStyle = risk > 80 ? '#ef4444' : risk > 40 ? '#f59e0b' : '#06b6d4';
        ctx.fill();

        // The Pulse (Kinetic Scaling based on Risk)
        if (risk > 50) {
            const time = Date.now() / 1000;
            const pulseRate = risk > 80 ? 8 : 3;
            const ringSize = size + (Math.sin(time * pulseRate) + 1) * (risk > 80 ? 4 : 2);

            ctx.beginPath();
            ctx.arc(x, y, ringSize, 0, 2 * Math.PI, false);
            ctx.strokeStyle = risk > 80 ? 'rgba(239, 68, 68, 0.4)' : 'rgba(245, 158, 11, 0.4)';
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
        }

        // Label
        const label = node.name || node.id;
        ctx.font = `${4 / globalScale}px Monospace`;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.textAlign = 'center';
        ctx.fillText(label, x, y + size + 2);
    };

    return (
        <div ref={containerRef} className="w-full h-full relative" style={{ minHeight: '400px' }}>
            {/* @ts-ignore */}
            {dimensions.width > 0 && (
                <ForceGraph2D
                    graphData={graphData}
                    width={dimensions.width}
                    height={dimensions.height}
                    nodeCanvasObject={paintRing}
                    nodeRelSize={4}
                    linkColor={() => 'rgba(6, 182, 212, 0.15)'}
                    backgroundColor="#000000"

                    // Kinetic Motion: Traffic Velocity Particles
                    linkDirectionalParticles={(link: any) => link.traffic_velocity ? Math.min(link.traffic_velocity, 10) : 0}
                    linkDirectionalParticleSpeed={(link: any) => link.traffic_velocity ? (link.traffic_velocity * 0.002) : 0.01}
                    linkDirectionalParticleWidth={2}
                    linkDirectionalParticleColor={(link: any) => link.is_exfiltration ? '#ef4444' : '#06b6d4'}

                    enableNodeDrag={true}
                    warmupTicks={50}
                    cooldownTicks={0}
                    onNodeClick={(node: any) => {
                        if (onNodeClick) onNodeClick(node);
                    }}
                />
            )}
        </div>
    );
};
