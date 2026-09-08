'use client';

import dynamic from 'next/dynamic';
import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { api } from '@/lib/api';
import {
    Network, Search, X, Eye, ZapOff, Radio, Crosshair, Shield,
    Target, Copy, ChevronRight, ExternalLink, AlertTriangle
} from 'lucide-react';
import { clsx } from 'clsx';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => (
        <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
                <span className="text-cyan-600 text-xs font-mono tracking-widest animate-pulse">LOADING GRAPH ENGINE...</span>
            </div>
        </div>
    ),
});

// ─── Node type config ──────────────────────────────────────────────────────────

const NODE_CFG: Record<number, { label: string; color: string; glow: string }> = {
    1: { label: 'INTERNAL ASSET', color: '#00f3ff', glow: '#00f3ff' },
    2: { label: 'PROCESS', color: '#a78bfa', glow: '#a78bfa' },
    3: { label: 'THREAT ACTOR', color: '#ff003c', glow: '#ff003c' },
    4: { label: 'CVE / VULN', color: '#f97316', glow: '#f97316' },
    5: { label: 'HONEYPOT', color: '#10b981', glow: '#10b981' },
    6: { label: 'C2 INFRA', color: '#dc2626', glow: '#dc2626' },
    7: { label: 'IDENTITY', color: '#fbbf24', glow: '#fbbf24' },
};

const FILTER_OPTIONS = [
    { id: 'all', label: 'ALL' },
    { id: '1', label: 'ASSETS' },
    { id: '3', label: 'THREATS' },
    { id: '4', label: 'CVEs' },
    { id: '6', label: 'C2' },
    { id: '5', label: 'HONEYPOTS' },
    { id: '7', label: 'IDENTITIES' },
];

// ─── Simulated topology ────────────────────────────────────────────────────────

const buildSimGraph = () => ({
    nodes: [],
    links: [],
});

interface ContextMenu { x: number; y: number; node: any }

// ─── Component ─────────────────────────────────────────────────────────────────

export default function IntelGraphPage() {
    const containerRef = useRef<HTMLDivElement>(null);
    const graphRef = useRef<any>(null);
    const [dimensions, setDimensions] = useState({ w: 800, h: 600 });
    const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] });
    const [loading, setLoading] = useState(true);
    const [selectedNode, setSelectedNode] = useState<any>(null);
    const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
    const [activeFilter, setActiveFilter] = useState('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [activeAction, setActiveAction] = useState<string | null>(null);

    // ─── Visible graph (filtered) ─────────────────────────────────────────────

    const visibleData = useMemo(() => {
        const nodeIds = new Set(
            graphData.nodes
                .filter(n => {
                    if (activeFilter !== 'all' && String(n.group) !== activeFilter) return false;
                    if (searchQuery && !n.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
                    return true;
                })
                .map(n => n.id)
        );
        return {
            nodes: graphData.nodes.filter(n => nodeIds.has(n.id)),
            links: graphData.links.filter(l => {
                const s = typeof l.source === 'object' ? l.source.id : l.source;
                const t = typeof l.target === 'object' ? l.target.id : l.target;
                return nodeIds.has(s) && nodeIds.has(t);
            }),
        };
    }, [graphData, activeFilter, searchQuery]);

    // ─── HUD stats ────────────────────────────────────────────────────────────

    const threatCount = visibleData.nodes.filter(n => n.risk > 70).length;
    const criticalCount = visibleData.nodes.filter(n => n.risk > 90).length;

    // ─── Lifecycle (Resize) ───────────────────────────────────────────────────

    useEffect(() => {
        const update = () => {
            if (containerRef.current)
                setDimensions({ w: containerRef.current.clientWidth, h: containerRef.current.clientHeight });
        };
        update();
        window.addEventListener('resize', update);
        return () => window.removeEventListener('resize', update);
    }, []);

          // 📡 LIVE REAL-WORLD NEO4J POLL LOOP
    useEffect(() => {
        const fetchLiveGraph = async () => {
            try {
                // ✅ Uses the proxy-aware api singleton — no direct localhost:8000 calls.
                // The singleton handles auth headers and credentials automatically.
                const data = await api.getGraph();

                // Maps database models cleanly into React UI expected attributes
                const cleanNodes = (data.nodes || data.vertices || []).map((n: any) => ({
                    id: n.id,
                    name: n.name || `Asset: ${n.id}`,
                    group: n.group || 3,
                    val: n.val || 14,
                    risk: n.risk_score || n.risk || 100
                }));

                const cleanLinks = (data.links || data.edges || []).map((l: any) => ({
                    source: l.source,
                    target: l.target,
                    type: l.type || 'TARGETS'
                }));

                setGraphData({ nodes: cleanNodes, links: cleanLinks });
            } catch (err) {
                // 401 is handled by the api singleton (redirect to /login)
                console.error("Graph matrix synchronization failure:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchLiveGraph();
        // Poll every 15s — less aggressive, prevents overloading the backend
        const telemetryTicker = setInterval(fetchLiveGraph, 15_000);
        return () => clearInterval(telemetryTicker);
    }, []);


    // ─── Lifecycle (Context Menu Close) ───────────────────────────────────────

    useEffect(() => {
        const close = () => setContextMenu(null);
        window.addEventListener('click', close);
        return () => window.removeEventListener('click', close);
    }, []);

    // ─── Handlers ─────────────────────────────────────────────────────────────

    const handleNodeClick = useCallback((node: any) => {
        setContextMenu(null);
        setSelectedNode(node);
    }, []);

    const handleNodeRightClick = useCallback((node: any, evt: MouseEvent) => {
        evt.preventDefault();
        setContextMenu({ x: evt.clientX, y: evt.clientY, node });
    }, []);

    const handleAction = (action: string, node: any) => {
        setActiveAction(`${action} → ${node.name}`);
        setContextMenu(null);
        setTimeout(() => setActiveAction(null), 3500);
    };

    const nodeConnections = useMemo(() => {
        if (!selectedNode) return [];
        return graphData.links
            .filter(l => {
                const s = typeof l.source === 'object' ? l.source.id : l.source;
                const t = typeof l.target === 'object' ? l.target.id : l.target;
                return s === selectedNode.id || t === selectedNode.id;
            })
            .slice(0, 8)
            .map(l => {
                const s = typeof l.source === 'object' ? l.source.id : l.source;
                const t = typeof l.target === 'object' ? l.target.id : l.target;
                const otherId = s === selectedNode.id ? t : s;
                const other = graphData.nodes.find(n => n.id === otherId);
                return { other, type: l.type };
            });
    }, [selectedNode, graphData]);

    // ─── Canvas painter ───────────────────────────────────────────────────────

    const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, gScale: number) => {
        const cfg = NODE_CFG[node.group] ?? { color: '#ffffff', glow: '#ffffff' };
        const isSelected = selectedNode?.id === node.id;
        const isCritical = node.risk > 90;
        const isHighRisk = node.risk > 70;
        const size = (node.val ?? 6) * 0.65;

        // Outer pulse ring for critical nodes
        if (isCritical) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI);
            ctx.strokeStyle = `${cfg.color}35`;
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Glow
        ctx.shadowColor = isSelected ? '#ffffff' : cfg.glow;
        ctx.shadowBlur = isSelected ? 22 : isHighRisk ? 14 : 6;

        // Main dot
        ctx.beginPath();
        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
        ctx.fillStyle = isSelected ? '#ffffff' : cfg.color;
        ctx.fill();
        ctx.shadowBlur = 0;

        const fontSize = Math.max(10 / gScale, 2);

        // Label
        if (gScale > 0.7 || isHighRisk) {
            ctx.font = `bold ${fontSize}px monospace`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle = isHighRisk ? cfg.color : 'rgba(160,160,160,0.65)';
            ctx.fillText(node.name, node.x, node.y + size + 2);
        }

        // Risk badge
        if (isCritical && gScale > 0.65) {
            const badge = `${node.risk}`;
            ctx.font = `bold ${Math.max(8 / gScale, 2)}px monospace`;
            ctx.fillStyle = '#ff003c';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(badge, node.x, node.y - size - 1);
        }
    }, [selectedNode]);

    const paintNodeArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, (node.val ?? 6) * 0.65 + 5, 0, 2 * Math.PI);
        ctx.fill();
    }, []);

    const getLinkColor = useCallback((link: any) => {
        switch (link.type) {
            case 'TARGETS': return 'rgba(239,68,68,0.55)';
            case 'LATERAL_MOVE': return 'rgba(239,68,68,0.35)';
            case 'COMMUNICATES_TO': return 'rgba(234,179,8,0.28)';
            case 'COMPROMISES': return 'rgba(220,38,38,0.6)';
            default: return 'rgba(255,255,255,0.07)';
        }
    }, []);

    const getLinkWidth = useCallback((link: any) =>
        ['TARGETS', 'COMPROMISES', 'LATERAL_MOVE'].includes(link.type) ? 1.5 : 0.8, []);

    const getLinkParticles = useCallback((link: any) =>
        ['COMMUNICATES_TO', 'TARGETS', 'COMPROMISES'].includes(link.type) ? 2 : 0, []);

    // ─── Render ───────────────────────────────────────────────────────────────

    const graphWidth = selectedNode ? (dimensions.w - 320) : dimensions.w;

    return (
        <div className="flex flex-col h-full bg-[#050505] font-mono" onClick={() => setContextMenu(null)}>

            {/* ── Toolbar ── */}
            <div className="h-12 border-b border-[#181818] flex items-center justify-between px-5 bg-[#070707] shrink-0">
                <div className="flex items-center gap-3">
                    <Network className="text-cyan-500" size={16} />
                    <h1 className="text-[11px] font-bold tracking-widest text-gray-100 uppercase">Global Intelligence Graph</h1>
                    <span className="text-[8px] bg-emerald-950/60 border border-emerald-700 text-emerald-400 px-1.5 py-0.5 rounded font-bold tracking-widest animate-pulse">LIVE</span>
                </div>

                <div className="flex items-center gap-2">
                    {/* Search */}
                    <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-700" size={12} />
                        <input
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            placeholder="search nodes..."
                            className="bg-[#0f0f0f] border border-[#1c1c1c] rounded pl-7 pr-6 py-1 text-[11px] text-slate-300 placeholder-slate-800 focus:outline-none focus:border-cyan-700/60 w-44 transition-colors"
                        />
                        {searchQuery && (
                            <button onClick={() => setSearchQuery('')} className="absolute right-2 top-1/2 -translate-y-1/2">
                                <X size={10} className="text-slate-600 hover:text-slate-400" />
                            </button>
                        )}
                    </div>

                    {/* Filter tabs */}
                    <div className="flex items-center bg-[#0c0c0c] border border-[#1c1c1c] rounded overflow-hidden">
                        {FILTER_OPTIONS.map(f => (
                            <button
                                key={f.id}
                                onClick={() => setActiveFilter(f.id)}
                                className={clsx(
                                    'px-2.5 py-1 text-[9px] font-bold tracking-widest transition-all',
                                    activeFilter === f.id
                                        ? 'bg-cyan-950/50 text-cyan-400'
                                        : 'text-slate-700 hover:text-slate-500'
                                )}
                            >
                                {f.label}
                            </button>
                        ))}
                    </div>

                    {/* Reload */}
                    <button
                        onClick={() => { setLoading(true); setTimeout(() => { setGraphData(buildSimGraph()); setLoading(false); }, 300); }}
                        className="p-1.5 bg-[#0f0f0f] border border-[#1c1c1c] rounded hover:border-cyan-700/40 transition-colors"
                        title="Reload topology"
                    >
                        <Radio className="text-cyan-600" size={13} />
                    </button>
                </div>
            </div>

            {/* ── Action toast ── */}
            {activeAction && (
                <div className="fixed top-16 right-5 z-50 flex items-center gap-2 bg-[#0d1117] border border-cyan-700/60 text-cyan-400 px-3 py-2 rounded text-[10px] font-bold tracking-widest shadow-[0_0_24px_rgba(0,243,255,0.18)]">
                    <Crosshair size={11} />
                    EXECUTING: {activeAction}
                </div>
            )}

            {/* ── Main layout ── */}
            <div className="flex flex-1 overflow-hidden">

                {/* Graph canvas */}
                <div className="relative overflow-hidden" ref={containerRef} style={{ width: graphWidth, flexShrink: 0 }}>
                    {loading && (
                        <div className="absolute inset-0 flex items-center justify-center z-20 bg-black/75 backdrop-blur-sm">
                            <div className="flex flex-col items-center gap-4">
                                <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
                                <span className="font-mono text-cyan-500 text-xs animate-pulse tracking-widest">ESTABLISHING NEURAL LINK...</span>
                            </div>
                        </div>
                    )}

                    <ForceGraph2D
                        ref={graphRef}
                        width={graphWidth}
                        height={dimensions.h}
                        graphData={visibleData}
                        nodeLabel=""
                        backgroundColor="#050505"
                        onNodeClick={handleNodeClick}
                        onNodeRightClick={handleNodeRightClick}
                        linkColor={getLinkColor}
                        linkWidth={getLinkWidth}
                        linkDirectionalArrowLength={4}
                        linkDirectionalArrowRelPos={1}
                        linkDirectionalParticles={getLinkParticles}
                        linkDirectionalParticleWidth={2}
                        linkDirectionalParticleColor={(l: any) => l.type === 'TARGETS' ? '#ff003c' : '#00f3ff'}
                        nodeCanvasObject={paintNode}
                        nodePointerAreaPaint={paintNodeArea}
                        cooldownTicks={120}
                    />

                    {/* ── HUD — bottom-left ── */}
                    <div className="absolute bottom-4 left-4 pointer-events-none space-y-2">
                        {/* Metrics box */}
                        <div className="bg-black/88 border border-[#191919] rounded px-3 py-2.5 backdrop-blur-sm">
                            <div className="text-[8px] text-slate-700 tracking-widest font-bold mb-2">GRAPH INTEL</div>
                            {[
                                { k: 'NODES', v: visibleData.nodes.length, c: 'text-cyan-400' },
                                { k: 'LINKS', v: visibleData.links.length, c: 'text-cyan-400' },
                                { k: 'HIGH RISK', v: threatCount, c: 'text-orange-400' },
                                { k: 'CRITICAL', v: criticalCount, c: 'text-rose-400' },
                            ].map(m => (
                                <div key={m.k} className="flex justify-between gap-8 text-[10px] pb-0.5">
                                    <span className="text-slate-700">{m.k}</span>
                                    <span className={clsx('font-bold', m.c)}>{m.v}</span>
                                </div>
                            ))}
                        </div>

                        {/* Legend */}
                        <div className="bg-black/88 border border-[#191919] rounded px-3 py-2.5 backdrop-blur-sm">
                            <div className="text-[8px] text-slate-700 tracking-widest font-bold mb-2">NODE TYPES</div>
                            {Object.entries(NODE_CFG).map(([gid, cfg]) => (
                                <button
                                    key={gid}
                                    className="flex items-center gap-2 w-full mb-0.5 pointer-events-auto hover:opacity-80"
                                    onClick={() => setActiveFilter(activeFilter === gid ? 'all' : gid)}
                                >
                                    <div
                                        className="w-2 h-2 rounded-full shrink-0 transition-all"
                                        style={{
                                            backgroundColor: cfg.color,
                                            boxShadow: activeFilter === gid ? `0 0 8px ${cfg.glow}` : `0 0 4px ${cfg.glow}60`,
                                            opacity: activeFilter === 'all' || activeFilter === gid ? 1 : 0.3,
                                        }}
                                    />
                                    <span className={clsx('text-[9px] transition-colors', activeFilter === gid ? 'text-slate-300' : 'text-slate-600')}>
                                        {cfg.label}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Scanning pulse */}
                    <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
                        <div className="relative w-2 h-2">
                            <div className="absolute inset-0 rounded-full bg-cyan-500/40 animate-ping" />
                            <div className="w-2 h-2 rounded-full bg-cyan-500" />
                        </div>
                        <span className="text-[9px] text-cyan-700 tracking-widest">LIVE TOPOLOGY · NEO4J</span>
                    </div>

                    {/* Right-click hint */}
                    <div className="absolute bottom-4 right-4 pointer-events-none">
                        <span className="text-[8px] text-slate-800">Right-click any node for actions</span>
                    </div>
                </div>

                {/* ── Node Detail Panel ── */}
                {selectedNode && (
                    <div className="w-80 border-l border-[#181818] bg-[#070707] flex flex-col overflow-hidden flex-shrink-0">
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#161616]">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-2 h-2 rounded-full"
                                    style={{
                                        backgroundColor: NODE_CFG[selectedNode.group]?.color ?? '#fff',
                                        boxShadow: `0 0 8px ${NODE_CFG[selectedNode.group]?.glow ?? '#fff'}`,
                                    }}
                                />
                                <span className="text-[9px] font-bold text-slate-400 tracking-widest">
                                    {NODE_CFG[selectedNode.group]?.label ?? 'ENTITY'}
                                </span>
                            </div>
                            <button onClick={() => setSelectedNode(null)} className="p-1 hover:bg-[#1a1a1a] rounded transition-colors">
                                <X size={13} className="text-slate-600 hover:text-slate-400" />
                            </button>
                        </div>

                        {/* Entity name */}
                        <div className="px-4 py-3 border-b border-[#111]">
                            <h2 className="text-sm font-bold text-white break-all leading-tight">{selectedNode.name}</h2>
                            <p className="text-[8px] text-slate-700 mt-1 font-mono">UID: {selectedNode.id}</p>
                        </div>

                        {/* Risk gauge */}
                        <div className="px-4 py-3 border-b border-[#111]">
                            <div className="flex justify-between items-end mb-2">
                                <span className="text-[9px] text-slate-600 tracking-widest">COMPOSITE RISK SCORE</span>
                                <span className={clsx(
                                    'text-2xl font-black leading-none',
                                    (selectedNode.risk ?? 0) > 90 ? 'text-rose-400' :
                                        (selectedNode.risk ?? 0) > 70 ? 'text-orange-400' :
                                            (selectedNode.risk ?? 0) > 40 ? 'text-amber-400' : 'text-emerald-400'
                                )}>
                                    {selectedNode.risk ?? '?'}
                                    <span className="text-sm font-normal text-slate-600">/100</span>
                                </span>
                            </div>
                            <div className="h-1 bg-[#111] rounded-full overflow-hidden">
                                <div
                                    className={clsx(
                                        'h-full rounded-full transition-all duration-700',
                                        (selectedNode.risk ?? 0) > 90 ? 'bg-rose-500' :
                                            (selectedNode.risk ?? 0) > 70 ? 'bg-orange-400' :
                                                (selectedNode.risk ?? 0) > 40 ? 'bg-amber-400' : 'bg-emerald-500'
                                    )}
                                    style={{ width: `${selectedNode.risk ?? 0}%` }}
                                />
                            </div>
                            <div className="flex justify-between mt-1">
                                <span className="text-[8px] text-slate-800">0</span>
                                <span className={clsx('text-[8px] font-bold',
                                    (selectedNode.risk ?? 0) > 90 ? 'text-rose-600' :
                                        (selectedNode.risk ?? 0) > 70 ? 'text-orange-600' : 'text-slate-700'
                                )}>
                                    {(selectedNode.risk ?? 0) > 90 ? '⚠ CRITICAL THREAT' :
                                        (selectedNode.risk ?? 0) > 70 ? '⚠ HIGH RISK' :
                                            (selectedNode.risk ?? 0) > 40 ? 'ELEVATED' : 'LOW RISK'}
                                </span>
                                <span className="text-[8px] text-slate-800">100</span>
                            </div>
                        </div>

                        {/* Connected nodes */}
                        <div className="px-4 py-3 border-b border-[#111] flex-1 overflow-y-auto">
                            <div className="text-[9px] text-slate-700 tracking-widest font-bold mb-2">
                                GRAPH CONNECTIONS ({nodeConnections.length})
                            </div>
                            {nodeConnections.length === 0 ? (
                                <p className="text-[9px] text-slate-800">No connections in current view</p>
                            ) : (
                                <div className="space-y-1">
                                    {nodeConnections.map(({ other, type }, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center gap-2 text-[10px] group cursor-pointer"
                                            onClick={() => other && setSelectedNode(other)}
                                        >
                                            <ChevronRight size={9} className="text-slate-800 shrink-0" />
                                            <div
                                                className="w-1.5 h-1.5 rounded-full shrink-0"
                                                style={{ backgroundColor: NODE_CFG[other?.group]?.color ?? '#888' }}
                                            />
                                            <span className="text-cyan-500 group-hover:text-cyan-300 transition-colors truncate">
                                                {other?.name ?? '(unknown)'}
                                            </span>
                                            <span className="text-[8px] text-slate-800 ml-auto shrink-0 font-mono">{type}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Operator actions */}
                        <div className="px-4 py-3 border-t border-[#111]">
                            <div className="text-[9px] text-slate-700 tracking-widest font-bold mb-2">OPERATOR ACTIONS</div>
                            <div className="grid grid-cols-2 gap-1.5">
                                {[
                                    { icon: <Eye size={10} />, label: 'ENRICH', color: 'border-cyan-800   text-cyan-400   hover:bg-cyan-950/30' },
                                    { icon: <ZapOff size={10} />, label: 'ISOLATE', color: 'border-rose-900   text-rose-400   hover:bg-rose-950/30' },
                                    { icon: <Crosshair size={10} />, label: 'TRACE', color: 'border-amber-800  text-amber-400  hover:bg-amber-950/30' },
                                    { icon: <Shield size={10} />, label: 'BLOCK', color: 'border-orange-800 text-orange-400 hover:bg-orange-950/30' },
                                    { icon: <Target size={10} />, label: 'ADD REPORT', color: 'border-purple-800 text-purple-400 hover:bg-purple-950/30' },
                                    { icon: <Copy size={10} />, label: 'COPY IOC', color: 'border-slate-800  text-slate-400  hover:bg-slate-900/50' },
                                ].map(btn => (
                                    <button
                                        key={btn.label}
                                        onClick={() => handleAction(btn.label, selectedNode)}
                                        className={clsx(
                                            'flex items-center gap-1.5 px-2 py-1.5 rounded border text-[8px] font-bold tracking-widest transition-all',
                                            btn.color
                                        )}
                                    >
                                        {btn.icon} {btn.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="px-4 pb-3 pt-1">
                            <p className="text-[8px] text-slate-800">Click another node to pivot investigation</p>
                        </div>
                    </div>
                )}
            </div>

            {/* ── Right-click Context Menu ── */}
            {contextMenu && (
                <div
                    className="fixed z-50 bg-[#0c0c0c]/98 border border-slate-800 rounded shadow-[0_0_40px_rgba(0,0,0,0.95)] backdrop-blur-md min-w-[200px]"
                    style={{ left: contextMenu.x, top: contextMenu.y }}
                    onClick={e => e.stopPropagation()}
                >
                    <div className="px-3 py-2 border-b border-slate-900">
                        <div className="text-[8px] text-slate-600 tracking-widest">NODE</div>
                        <div className="text-[11px] font-bold text-slate-300 truncate mt-0.5">{contextMenu.node.name}</div>
                        {contextMenu.node.risk != null && (
                            <div className={clsx('text-[9px] font-bold',
                                contextMenu.node.risk > 90 ? 'text-rose-400' : contextMenu.node.risk > 70 ? 'text-orange-400' : 'text-slate-500'
                            )}>
                                Risk: {contextMenu.node.risk}/100
                            </div>
                        )}
                    </div>
                    {[
                        { icon: <Eye size={11} />, label: 'Enrich Entity', col: 'text-cyan-400' },
                        { icon: <Crosshair size={11} />, label: 'Start Trace', col: 'text-amber-400' },
                        { icon: <ZapOff size={11} />, label: 'Isolate Host', col: 'text-rose-400' },
                        { icon: <Shield size={11} />, label: 'Block Entity', col: 'text-orange-400' },
                        { icon: <Target size={11} />, label: 'Add to Report', col: 'text-purple-400' },
                        { icon: <AlertTriangle size={11} />, label: 'Flag as IOC', col: 'text-amber-500' },
                        { icon: <ExternalLink size={11} />, label: 'Open Detail Panel', col: 'text-slate-400' },
                    ].map(item => (
                        <button
                            key={item.label}
                            className="w-full flex items-center gap-2.5 px-3 py-2 text-[10px] hover:bg-slate-900/60 transition-colors border-l-2 border-transparent hover:border-cyan-500/30"
                            onClick={() => {
                                if (item.label === 'Open Detail Panel') setSelectedNode(contextMenu.node);
                                else handleAction(item.label, contextMenu.node);
                            }}
                        >
                            <span className={item.col}>{item.icon}</span>
                            <span className="text-slate-300">{item.label}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
