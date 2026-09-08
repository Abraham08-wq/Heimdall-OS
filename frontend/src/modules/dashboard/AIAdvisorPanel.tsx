import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
    BrainCircuit, Loader2, Sparkles, Send, Shield, AlertTriangle,
    Zap, Target, Eye, RefreshCw, ChevronRight, TrendingUp
} from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Message {
    id: string;
    role: 'user' | 'advisor';
    content: string;
    ts: string;
    category?: 'brief' | 'recommend' | 'alert' | 'analysis';
}



const PROMPT_STARTERS = [
    { label: 'Daily Threat Brief', q: 'Generate a full threat intelligence report for today', icon: <TrendingUp size={11} /> },
    { label: 'MITRE Coverage', q: 'Analyze our MITRE ATT&CK coverage gaps', icon: <Target size={11} /> },
    { label: 'Isolation Guidance', q: 'How should I isolate the compromised host DC-01?', icon: <Shield size={11} /> },
    { label: 'Hunt Recommendations', q: 'What threat hunts should I run based on current anomalies?', icon: <Eye size={11} /> },
];

// ─── Component ────────────────────────────────────────────────────────────────

interface AIAdvisorPanelProps {
    insight?: string;
    isGenerating?: boolean;
}

export const AIAdvisorPanel: React.FC<AIAdvisorPanelProps> = ({ insight, isGenerating = false }) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [thinking, setThinking] = useState(false);
    const [briefIdx, setBriefIdx] = useState(0);
    const chatRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages, thinking]);

    const sendMessage = useCallback(async (text: string) => {
        if (!text.trim()) return;
        const userMsg: Message = { id: `u${Date.now()}`, role: 'user', content: text, ts: new Date().toLocaleTimeString() };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setThinking(true);

        try {
            const response = await api.chatWithAnalyst('', text); // Assuming empty entityId for now
            const advisorMsg: Message = { id: `a${Date.now()}`, role: 'advisor', content: response.response, ts: new Date().toLocaleTimeString(), category: 'analysis' };
            setMessages(prev => [...prev, advisorMsg]);
        } catch (error) {
            const errorMsg: Message = { id: `a${Date.now()}`, role: 'advisor', content: 'Sorry, I am having trouble connecting to the AI service.', ts: new Date().toLocaleTimeString(), category: 'alert' };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setThinking(false);
        }
    }, []);

    const categoryConfig = {
        alert: { border: 'border-rose-800', bg: 'bg-rose-950/20', label: 'CRITICAL ALERT' },
        recommend: { border: 'border-amber-800', bg: 'bg-amber-950/20', label: 'RECOMMENDATION' },
        brief: { border: 'border-indigo-800', bg: 'bg-indigo-950/20', label: 'INTEL BRIEF' },
        analysis: { border: 'border-cyan-800', bg: 'bg-cyan-950/10', label: 'ANALYSIS' },
    };

    return (
        <div className="flex flex-col h-full bg-black/80 border border-indigo-900/40 overflow-hidden font-mono">
            {/* Header */}
            <div className="px-3 py-2.5 border-b border-indigo-900/30 bg-black/60 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <BrainCircuit size={14} className="text-indigo-400 animate-pulse" />
                    <div>
                        <h3 className="text-[10px] font-bold text-indigo-400 tracking-widest">NEXUS AI STRATEGIC ADVISOR</h3>
                        <p className="text-[8px] text-indigo-900">Threat Intelligence · Playbook Counsel · Predictive Analysis</p>
                    </div>
                </div>

            </div>

            {/* Prompt starters */}
            <div className="flex gap-1 flex-wrap p-2 border-b border-slate-900/60 shrink-0">
                {PROMPT_STARTERS.map(p => (
                    <button key={p.label} onClick={() => sendMessage(p.q)}
                        className="flex items-center gap-1 text-[8px] px-2 py-1 bg-slate-900/60 border border-slate-800 rounded text-slate-500 hover:text-indigo-400 hover:border-indigo-800 transition-all font-mono">
                        {p.icon}{p.label}
                    </button>
                ))}
            </div>

            {/* Chat area */}
            <div ref={chatRef} className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
                {messages.map(msg => {
                    if (msg.role === 'user') {
                        return (
                            <div key={msg.id} className="flex justify-end">
                                <div className="max-w-[85%] bg-indigo-950/40 border border-indigo-800/50 rounded px-3 py-2 text-[10px] text-indigo-300 leading-relaxed">
                                    {msg.content}
                                </div>
                            </div>
                        );
                    }
                    const cat = msg.category ? categoryConfig[msg.category] : categoryConfig.analysis;
                    return (
                        <div key={msg.id} className={clsx("rounded border p-3", cat.border, cat.bg)}>
                            <div className="flex items-center gap-2 mb-2">
                                <div className="w-5 h-5 rounded bg-indigo-900/60 border border-indigo-700 flex items-center justify-center">
                                    <Sparkles size={10} className="text-indigo-400" />
                                </div>
                                <span className="text-[9px] font-bold text-indigo-500 tracking-widest">NEXUS ADVISOR</span>
                                {msg.category && <span className="text-[8px] text-slate-600">[{cat.label}]</span>}
                                <span className="text-[8px] text-slate-700 ml-auto">{msg.ts}</span>
                            </div>
                            <div className="text-[10px] text-slate-300 leading-relaxed whitespace-pre-wrap">
                                {msg.content.split('\n').map((line, i) => {
                                    if (line.startsWith('🔴') || line.startsWith('⚠️')) return <div key={i} className="text-rose-400 font-bold">{line}</div>;
                                    if (line.startsWith('⚡') || line.startsWith('✅')) return <div key={i} className="text-emerald-400 font-bold">{line}</div>;
                                    if (line.startsWith('📊') || line.startsWith('📋')) return <div key={i} className="text-cyan-400 font-bold">{line}</div>;
                                    if (line.startsWith('•') || line.startsWith('-')) return <div key={i} className="text-slate-400 pl-2">{line}</div>;
                                    if (line.match(/^\d+\./)) return <div key={i} className="text-slate-300 pl-2">{line}</div>;
                                    if (line.startsWith('**') && line.endsWith('**')) return <div key={i} className="font-bold text-white">{line.replace(/\*\*/g, '')}</div>;
                                    if (line.startsWith('|')) return <div key={i} className="font-mono text-[9px] text-slate-500">{line}</div>;
                                    return <div key={i}>{line}</div>;
                                })}
                            </div>
                            <div className="flex gap-2 mt-2">
                                <button className="text-[8px] bg-slate-900 border border-slate-700 px-2 py-0.5 rounded text-indigo-400 hover:bg-slate-800 transition-colors">Execute Recommendation</button>
                                <button className="text-[8px] bg-slate-900 border border-slate-700 px-2 py-0.5 rounded text-slate-500 hover:bg-slate-800 transition-colors">Detailed Report</button>
                            </div>
                        </div>
                    );
                })}
                {thinking && (
                    <div className="flex items-center gap-2 text-indigo-400/70 py-2 px-3 bg-indigo-950/20 rounded border border-indigo-900/30">
                        <Loader2 className="animate-spin shrink-0" size={12} />
                        <span className="text-[10px] tracking-wider animate-pulse">SYNTHESIZING THREAT INTELLIGENCE...</span>
                    </div>
                )}
            </div>

            {/* Input */}
            <div className="p-2 border-t border-indigo-900/30 bg-black/60 shrink-0">
                <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded px-3 py-2 focus-within:border-indigo-700 transition-colors">
                    <span className="text-indigo-600 text-xs shrink-0">›</span>
                    <input
                        type="text"
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
                        placeholder="Ask the Advisor..."
                        disabled={thinking}
                        className="bg-transparent border-none outline-none text-[10px] text-slate-300 w-full placeholder-slate-700 font-mono"
                    />
                    <button onClick={() => sendMessage(input)} disabled={!input.trim() || thinking}
                        className="text-indigo-500 hover:text-indigo-300 transition-colors disabled:opacity-30">
                        <Send size={12} />
                    </button>
                </div>
            </div>
        </div>
    );
};
