import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Crosshair, Terminal, Shield, MapPin, Skull, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface InterceptModalProps {
    isOpen: boolean;
    onClose: () => void;
}

import { useCommand } from '@/context/CommandContext';

export default function InterceptModal({ isOpen, onClose }: InterceptModalProps) {
    const [mounted, setMounted] = useState(false);
    const [activeTab, setActiveTab] = useState<'trace' | 'redteam'>('trace');
    const [traceMode, setTraceMode] = useState(false);
    const [isTogglingTrace, setIsTogglingTrace] = useState(false);
    const [targetId, setTargetId] = useState('');
    const [logs, setLogs] = useState<string[]>([]);

    // Global State
    const { selectedTarget } = useCommand();

    // Red Team State
    const [targetOS, setTargetOS] = useState('windows');
    const [payload, setPayload] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);

    useEffect(() => {
        setMounted(true);
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.ctrlKey && e.code === 'Space') {
                if (isOpen) onClose();
            }
            if (e.key === 'Escape' && isOpen) onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose]);

    // Sync with Global Selection
    useEffect(() => {
        if (selectedTarget) {
            setTargetId(selectedTarget);
            log(`Target Locked: ${selectedTarget}`);
        }
    }, [selectedTarget]);

    if (!mounted || !isOpen) return null;

    const log = (msg: string) => setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev]);

    const handleTraceToggle = async () => {
        if (!targetId) {
            log("Error: No Target ID specified for trace.");
            return;
        }

        setIsTogglingTrace(true);
        const newMode = !traceMode;
        log(newMode ? "Initializing Active Trace Protocol..." : "Deactivating Trace...");

        try {
            await api.updateDevice(targetId, { active_trace: newMode });
            setTraceMode(newMode);
            log(newMode ? "Active Trace INITIATED - GPS Handshake Established" : "Active Trace DEACTIVATED");
        } catch (e) {
            log(`Error: Failed to update device trace state: ${(e as Error).message}`);
        } finally {
            setIsTogglingTrace(false);
        }
    };

    const generatePayload = async () => {
        if (!targetId) {
            log("Error: No Target ID specified for payload generation.");
            return;
        }
        
        setIsGenerating(true);
        log(`Generating payload for ${targetOS}...`);
        setPayload('');

        try {
            const res = await api.synthesizeExploit({ ip: targetId, target_cve: targetOS });
            if (res && res.weaponized_package?.payload_command) {
                setPayload(res.weaponized_package.payload_command);
                log("Payload generated successfully.");
            } else {
                throw new Error("Invalid or empty response from payload generator.");
            }
        } catch (e) {
            log(`Error generating payload: ${(e as Error).message}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const modalContent = (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
            {/* Backdrop with blur */}
            <div
                className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />

            {/* Modal Container */}
            <div className="relative w-full max-w-2xl bg-black/80 border border-primary/20 rounded-2xl shadow-[0_0_50px_rgba(0,243,255,0.1)] backdrop-filter backdrop-blur-xl overflow-hidden flex flex-col max-h-[80vh] cyber-grid-bg">

                {/* Grid Overlay */}
                <div className="absolute inset-0 bg-[url('/assets/grid.svg')] opacity-20 pointer-events-none"></div>

                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-primary/20 bg-primary/5 relative z-10">
                    <div className="flex items-center gap-2">
                        <Terminal className="w-5 h-5 text-primary" />
                        <h2 className="font-mono text-lg font-bold tracking-wider text-white">OMNI-PROBE INTERCEPT</h2>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-white/10 relative z-10">
                    <button
                        onClick={() => setActiveTab('trace')}
                        className={`flex-1 p-3 text-sm font-mono flex items-center justify-center gap-2 transition ${activeTab === 'trace' ? 'bg-primary/20 text-primary border-b-2 border-primary' : 'text-gray-400 hover:bg-white/5'}`}
                    >
                        <Crosshair className="w-4 h-4" /> TRACE & RECOVERY
                    </button>
                    <button
                        onClick={() => setActiveTab('redteam')}
                        className={`flex-1 p-3 text-sm font-mono flex items-center justify-center gap-2 transition ${activeTab === 'redteam' ? 'bg-alert/20 text-alert border-b-2 border-alert' : 'text-gray-400 hover:bg-white/5'}`}
                    >
                        <Skull className="w-4 h-4" /> RED TEAM OPS
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto flex-1 custom-scrollbar relative z-10">

                    {activeTab === 'trace' && (
                        <div className="space-y-6">
                            <div className="flex items-center justify-between bg-white/5 p-4 rounded-xl border border-white/5">
                                <div>
                                    <h3 className="text-white font-bold text-sm">Active Trace Mode</h3>
                                    <p className="text-xs text-gray-400">Real-time GPS triangulation & WebSocket feed</p>
                                </div>
                                <button
                                    onClick={handleTraceToggle}
                                    disabled={isTogglingTrace}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${traceMode ? 'bg-primary' : 'bg-gray-600'} disabled:opacity-50`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${traceMode ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                            </div>

                            <div className="space-y-2">
                                <label className="text-xs text-gray-400 font-mono uppercase">Target Identifier (ID / IP / MAC)</label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={targetId}
                                        onChange={(e) => setTargetId(e.target.value)}
                                        className="flex-1 bg-black/50 border border-white/10 rounded-lg p-3 text-white font-mono focus:border-primary focus:outline-none"
                                        placeholder="Enter target..."
                                    />
                                    <button className="bg-primary/20 hover:bg-primary/30 text-primary border border-primary/50 px-4 rounded-lg font-mono text-sm transition transition-all active:scale-95">
                                        PING
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'redteam' && (
                        <div className="space-y-6">
                            <div className="space-y-4">
                                <h3 className="text-alert font-bold flex items-center gap-2 font-mono uppercase text-sm border-b border-white/10 pb-2">
                                    <Terminal className="w-4 h-4" /> Payload Architect
                                </h3>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-xs text-gray-400 font-mono block mb-2">Target OS</label>
                                        <select
                                            value={targetOS}
                                            onChange={(e) => setTargetOS(e.target.value)}
                                            className="w-full bg-black/50 border border-white/10 rounded-lg p-2 text-white font-mono text-sm focus:border-alert focus:outline-none"
                                        >
                                            <option value="windows">Windows (x64)</option>
                                            <option value="linux">Linux (Python)</option>
                                            <option value="android">Android (APK)</option>
                                        </select>
                                    </div>
                                    <div className="flex items-end">
                                        <button
                                            onClick={generatePayload}
                                            disabled={isGenerating || !targetId}
                                            className="w-full bg-alert/20 hover:bg-alert/30 text-alert border border-alert/50 p-2 rounded-lg font-mono text-sm transition flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'GENERATE'}
                                        </button>
                                    </div>
                                </div>

                                {payload && (
                                    <div className="bg-black/80 rounded-lg p-4 font-mono text-xs text-green-400 break-all border border-white/10 relative group">
                                        {payload}
                                        <button
                                            className="absolute top-2 right-2 text-gray-500 hover:text-white"
                                            onClick={() => { navigator.clipboard.writeText(payload); log("Payload copied to clipboard"); }}
                                        >
                                            Copy
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="space-y-4 pt-4 border-t border-white/10">
                                <h3 className="text-alert font-bold flex items-center gap-2 font-mono uppercase text-sm">
                                    <Shield className="w-4 h-4" /> Vuln Scanner
                                </h3>
                                <div className="p-4 bg-white/5 rounded-lg text-center text-gray-500 text-sm font-mono">
                                    Select a target from the Graph to enable CVE correlation.
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Console Log Area */}
                    <div className="mt-6 border-t border-white/10 pt-4">
                        <div className="bg-black/90 p-3 rounded-lg h-32 overflow-y-auto text-[10px] font-mono text-gray-400 custom-scrollbar border border-white/5">
                            {logs.length === 0 ? <span className="opacity-30">System Idle...</span> : logs.map((l, i) => (
                                <div key={i} className="mb-1 border-b border-white/5 pb-1 last:border-0">{l}</div>
                            ))}
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
