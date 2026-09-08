"use client";

import React, { useState, useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { Bot, X, Send, Cpu, ShieldAlert, Minimize2, Maximize2 } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '@/lib/api';

interface Message {
    id: string;
    text: string;
    sender: 'user' | 'oracle';
    timestamp: Date;
}

export default function NexusOracle() {
    const pathname = usePathname();
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [messages, setMessages] = useState<Message[]>([
        { id: '1', text: 'NEXUS ORACLE ONLINE. Awaiting directives.', sender: 'oracle', timestamp: new Date() }
    ]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Determine Persona based on route
    const isGodMode = pathname.includes('/ghost') || pathname.includes('/redteam') || pathname.includes('/offensive');
    const themeColor = isGodMode ? 'red' : 'cyan';
    const personaTitle = isGodMode ? 'ORACLE // GOD MODE' : 'ORACLE // ANALYST COPILOT';

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isTyping, isOpen, isMinimized]);

    const handleSend = async (e?: React.FormEvent) => {
        if (e) e.preventDefault();
        if (!input.trim()) return;

        const userMsg: Message = { id: Date.now().toString(), text: input, sender: 'user', timestamp: new Date() };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsTyping(true);

        try {
            const data = await api.chatWithOracle(userMsg.text, isGodMode ? 'offensive' : 'defensive', isGodMode ? 'hacker' : 'analyst');
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                text: data.reply || "No response received.",
                sender: 'oracle',
                timestamp: new Date()
            }]);
        } catch (error) {
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                text: "[!] Oracle Offline. Connection Refused.",
                sender: 'oracle',
                timestamp: new Date()
            }]);
        } finally {
            setIsTyping(false);
        }
    };

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className={clsx(
                    "fixed bottom-6 right-6 p-4 rounded-full shadow-2xl transition-all hover:scale-110 z-50 flex items-center justify-center group animate-bounce",
                    isGodMode ? "bg-red-900/80 border border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.4)]" : "bg-cyan-900/80 border border-cyan-500/50 shadow-[0_0_30px_rgba(6,182,212,0.4)]"
                )}
            >
                {isGodMode ? <ShieldAlert className="text-red-400 group-hover:animate-pulse" size={24} /> : <Cpu className="text-cyan-400 group-hover:animate-pulse" size={24} />}
            </button>
        );
    }

    return (
        <div className={clsx(
            "fixed bottom-6 right-6 w-96 flex flex-col z-50 transition-all duration-300 glass-panel-heavy rounded-xl overflow-hidden",
            isGodMode ? "oracle-red" : "oracle-cyan",
            isMinimized ? "h-14" : "h-[32rem]"
        )}>
            {/* Header */}
            <div className={clsx(
                "p-3 flex justify-between items-center cursor-pointer border-b",
                isGodMode ? "bg-red-950/40 border-red-900/50" : "bg-cyan-950/40 border-cyan-900/50"
            )} onClick={() => setIsMinimized(!isMinimized)}>
                <div className="flex items-center gap-2">
                    {isGodMode ? <ShieldAlert size={16} className="text-red-500 animate-pulse" /> : <Cpu size={16} className="text-cyan-500 animate-pulse" />}
                    <span className={clsx("text-xs font-bold tracking-widest", isGodMode ? "text-red-500" : "text-cyan-500")}>
                        {personaTitle}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={(e) => { e.stopPropagation(); setIsMinimized(!isMinimized); }} className="text-slate-400 hover:text-white">
                        {isMinimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); setIsOpen(false); }} className="text-slate-400 hover:text-white">
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Chat Body */}
            {!isMinimized && (
                <>
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar" ref={scrollRef}>
                        {messages.map((msg) => (
                            <div key={msg.id} className={clsx("flex flex-col max-w-[85%]", msg.sender === 'user' ? "ml-auto items-end" : "mr-auto items-start")}>
                                <div className={clsx(
                                    "p-3 rounded-lg text-sm font-mono whitespace-pre-wrap break-words",
                                    msg.sender === 'user'
                                        ? "bg-slate-800 text-white border border-slate-700 rounded-tr-none"
                                        : isGodMode
                                            ? "bg-red-950/30 text-red-100 border border-red-900/50 rounded-tl-none shadow-[0_0_15px_rgba(239,68,68,0.1)]"
                                            : "bg-cyan-950/30 text-cyan-100 border border-cyan-900/50 rounded-tl-none shadow-[0_0_15px_rgba(6,182,212,0.1)]"
                                )}>
                                    {msg.text}
                                </div>
                                <span className="text-[9px] text-slate-500 mt-1 uppercase tracking-wider">{msg.timestamp.toLocaleTimeString()}</span>
                            </div>
                        ))}
                        {isTyping && (
                            <div className="mr-auto items-start max-w-[85%]">
                                <div className={clsx(
                                    "p-3 rounded-lg text-sm font-mono text-center",
                                    isGodMode ? "bg-red-950/30 text-red-500 border border-red-900/50" : "bg-cyan-950/30 text-cyan-500 border border-cyan-900/50"
                                )}>
                                    <span className="animate-pulse">PROCESSING DATA STREAMS...</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Input */}
                    <div className={clsx(
                        "p-3 border-t",
                        isGodMode ? "bg-red-950/20 border-red-900/50" : "bg-cyan-950/20 border-cyan-900/50"
                    )}>
                        <form onSubmit={handleSend} className="flex gap-2">
                            <input
                                autoFocus
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder={isGodMode ? "Enter destructive command query..." : "Ask Oracle for mitigation advice..."}
                                className="flex-1 bg-black/40 border border-slate-800 rounded px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-slate-500 placeholder:text-slate-600"
                            />
                            <button
                                type="submit"
                                disabled={isTyping}
                                className={clsx(
                                    "p-2 rounded flex items-center justify-center transition-colors disabled:opacity-50",
                                    isGodMode ? "bg-red-900/50 hover:bg-red-600 text-white" : "bg-cyan-900/50 hover:bg-cyan-600 text-white"
                                )}
                            >
                                <Send size={16} />
                            </button>
                        </form>
                    </div>
                </>
            )}
        </div>
    );
}
