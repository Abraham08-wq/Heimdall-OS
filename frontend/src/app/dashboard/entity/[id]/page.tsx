'use client';

import { useEffect, useState } from 'react';
import RiskMeter from '@/components/ui/RiskMeter';
import RelationshipGraph from '@/components/graph/RelationshipGraph';
import { Shield, Fingerprint, Clock, Share2, Loader2, AlertTriangle } from 'lucide-react';
import { api, Entity } from '@/lib/api';

export default function EntityProfilePage({ params }: { params: { id: string } }) {
    const entityId = params.id;
    const [entity, setEntity] = useState<Entity | null>(null);
    const [summary, setSummary] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [timeline, setTimeline] = useState<any[] | null>(null);

    // Chat State
    const [chatInput, setChatInput] = useState('');
    const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'analyst', content: string }[]>([]);
    const [isChatting, setIsChatting] = useState(false);

    const handleChatSubmit = async () => {
        if (!chatInput.trim()) return;

        const question = chatInput;
        setChatInput('');
        setChatHistory(prev => [...prev, { role: 'user', content: question }]);
        setIsChatting(true);

        try {
            const res = await api.chatWithAnalyst(entityId, question);
            setChatHistory(prev => [...prev, { role: 'analyst', content: res.response }]);
        } catch (err) {
            setChatHistory(prev => [...prev, { role: 'analyst', content: "Connection lost to Neural Engine." }]);
        } finally {
            setIsChatting(false);
        }
    };

    const [investigation, setInvestigation] = useState<any>(null);

    useEffect(() => {
        const loadEntityData = async () => {
            try {
                // Parallel fetch for Entity, Summary, and Deep Investigation
                const [entityData, summaryData, investData, timelineData] = await Promise.all([
                    api.getEntity(entityId),
                    api.getAISummary(entityId),
                    api.investigateEntity(entityId),
                    api.forensicEntityTimeline(entityId)
                ]);

                setEntity(entityData);
                setSummary(summaryData.summary);
                setInvestigation(investData);
                setTimeline(timelineData.timeline);
                setChatHistory([{ role: 'analyst', content: `Analyst Agent active. Context loaded for ${entityData.canonical_name}.` }]);

            } catch (err) {
                console.error("Failed to load entity profile", err);
                setError("Could not load entity intelligence. ID might be invalid.");
            } finally {
                setLoading(false);
            }
        };

        if (entityId) {
            loadEntityData();
        }
    }, [entityId]);

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-4">
                <Loader2 className="h-10 w-10 text-primary animate-spin" />
                <p className="font-mono text-gray-400 animate-pulse">Accessing Secure Archives...</p>
            </div>
        );
    }

    if (error || !entity) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-4">
                <AlertTriangle className="h-12 w-12 text-alert" />
                <p className="font-mono text-xl text-white">INTELLIGENCE NOT FOUND</p>
                <p className="font-mono text-gray-400">{error}</p>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col p-6 gap-6 overflow-hidden">
            {/* 1. Header Identity Card */}
            <div className="glass-panel p-6 rounded-2xl flex items-center justify-between">
                <div className="flex items-center gap-6">
                    <div className="h-20 w-20 rounded-full bg-primary/20 flex items-center justify-center border-2 border-primary">
                        <Fingerprint className="h-10 w-10 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold font-mono text-white uppercase">{entity.canonical_name}</h1>
                        <div className="flex gap-4 text-sm text-gray-400 mt-2 font-mono">
                            <span className="bg-white/5 px-2 py-1 rounded">ID: {entityId}</span>
                            <span className="bg-white/5 px-2 py-1 rounded uppercase">Type: {entity.type}</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-8">
                    <div className="text-right">
                        <p className="text-xs text-gray-400 uppercase tracking-widest">Risk Assessment</p>
                        <p className={`font-bold ${entity.risk_score > 70 ? 'text-alert' : 'text-warning'}`}>
                            {entity.risk_score > 70 ? 'CRITICAL' : entity.risk_score > 40 ? 'ELEVATED' : 'LOW'}
                        </p>
                    </div>
                    <RiskMeter score={entity.risk_score} />
                </div>
            </div>

            {/* 2. Main Content Grid */}
            <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">

                {/* Left: Attributes & Evidence */}
                <div className="col-span-4 flex flex-col gap-6 overflow-y-auto pr-2">
                    <div className="glass-panel p-6 rounded-2xl">
                        <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase flex gap-2">
                            <Shield className="h-4 w-4" /> Validated Selectors
                        </h3>
                        <div className="space-y-3 font-mono text-sm">
                            {(entity.attributes || []).map((attr: any, idx: number) => (
                                <div key={idx} className="flex justify-between p-2 bg-white/5 rounded">
                                    <span className="text-gray-300 truncate max-w-[200px]" title={attr.value}>{attr.value}</span>
                                    <span className={`text-xs border px-1 rounded ${attr.confidence > 0.8 ? 'text-success border-success' : 'text-warning border-warning'}`}>
                                        {attr.type.toUpperCase()}
                                    </span>
                                </div>
                            ))}
                            {(!entity.attributes || entity.attributes.length === 0) && (
                                <div className="text-gray-500 italic">No selectors found.</div>
                            )}
                        </div>
                    </div>

                    <div className="glass-panel p-6 rounded-2xl flex-1">
                        <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase flex gap-2">
                            <Clock className="h-4 w-4" /> Activity Timeline
                        </h3>
                        <div className="border-l-2 border-white/10 pl-4 space-y-6 text-sm">
                            {timeline && timeline.map((event, index) => (
                                <div key={index} className="relative">
                                    <div className="absolute -left-[21px] top-1 h-3 w-3 rounded-full bg-primary"></div>
                                    <p className="text-gray-200">{event.reasons?.[0] || 'Interaction event'}</p>
                                    <p className="text-xs text-gray-500 font-mono">{new Date(event.timestamp).toLocaleString()}</p>
                                </div>
                            ))}
                            {(!timeline || timeline.length === 0) && (
                                <div className="text-gray-500 italic">No timeline data available.</div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Center: Graph Visualization */}
                <div className="col-span-5 glass-panel rounded-2xl flex flex-col">
                    <div className="p-4 border-b border-white/5 flex justify-between items-center">
                        <h3 className="text-sm font-bold text-gray-400 uppercase flex gap-2">
                            <Share2 className="h-4 w-4" /> Relationship Network
                        </h3>
                    </div>
                    <div className="flex-1 relative bg-black/50">
                        <RelationshipGraph entityId={entityId} />
                    </div>
                </div>

                {/* Right: AI Analysis & Chat */}
                <div className="col-span-3 flex flex-col gap-6">
                    {/* Investigation Summary Card */}
                    <div className="glass-panel p-6 rounded-2xl border-l-4 border-l-red-500 overflow-y-auto max-h-[400px]">
                        <h3 className="text-sm font-bold text-red-500 mb-4 uppercase tracking-widest flex items-center gap-2">
                            <Fingerprint size={14} /> Investigation Report
                        </h3>

                        {investigation && (
                            <div className="mb-4 p-3 bg-red-900/20 border border-red-500/30 rounded flex justify-between items-center">
                                <div>
                                    <div className="text-[10px] text-red-400 uppercase">Verdict</div>
                                    <div className="font-bold text-red-100">{investigation.verdict}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[10px] text-red-400 uppercase">Threat Score</div>
                                    <div className="font-bold text-2xl text-red-500">{investigation.threat_score}</div>
                                </div>
                            </div>
                        )}

                        <div className="space-y-4">
                            <div>
                                <h4 className="text-xs text-gray-500 uppercase mb-2">Kill Chain Stage</h4>
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-red-500 w-full animate-pulse"></div>
                                    </div>
                                    <span className="text-xs font-bold text-red-400">{investigation?.kill_chain_stage || 'ANALYZING...'}</span>
                                </div>
                            </div>

                            <div className="prose prose-invert prose-sm">
                                {summary ? (
                                    <div className="whitespace-pre-wrap">{summary}</div>
                                ) : (
                                    <p className="text-gray-500 italic">Generating intelligence summary...</p>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Ask the Analyst Chat */}
                    <div className="glass-panel p-4 rounded-2xl flex-1 flex flex-col border border-white/10">
                        <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase flex gap-2 items-center">
                            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            Ask the Analyst
                        </h3>

                        <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-[200px] max-h-[300px] pr-2">
                            {chatHistory.map((msg, idx) => (
                                <div key={idx} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                    <span className="text-[10px] text-gray-500 uppercase">{msg.role}</span>
                                    <div className={`p-2 rounded-lg text-xs max-w-[90%] ${msg.role === 'user' ? 'bg-primary/20 text-primary-foreground' : 'bg-white/10 text-gray-300'}`}>
                                        {msg.content}
                                    </div>
                                </div>
                            ))}
                            {isChatting && <div className="text-xs text-gray-500 animate-pulse">Analyst is typing...</div>}
                        </div>

                        <div className="mt-auto relative">
                            <input
                                type="text"
                                value={chatInput}
                                onChange={(e) => setChatInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleChatSubmit()}
                                placeholder="Query the entity knowledge base..."
                                className="w-full bg-black/50 border border-white/10 rounded-lg py-2 px-3 text-sm text-white focus:outline-none focus:border-primary transition-colors"
                            />
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
