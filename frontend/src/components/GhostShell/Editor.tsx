"use client";

import React from 'react';
import Editor, { useMonaco } from '@monaco-editor/react';
import { Play, Terminal as TerminalIcon, Save, Zap } from 'lucide-react';
import { ThemeConfig } from '@/theme/ThemeConfig';
import { clsx } from 'clsx';

interface GhostEditorProps {
    code: string;
    language: string;
    onChange: (value: string | undefined) => void;
    onExecute: () => void;
    isExecuting: boolean;
}

const GhostEditor: React.FC<GhostEditorProps> = ({ code, language, onChange, onExecute, isExecuting }) => {
    const monaco = useMonaco();

    React.useEffect(() => {
        if (monaco) {
            monaco.editor.defineTheme('project-xy', {
                base: 'vs-dark',
                inherit: true,
                rules: [
                    { token: 'comment', foreground: '505050', fontStyle: 'italic' },
                    { token: 'keyword', foreground: 'ff2a2a', fontStyle: 'bold' },
                    { token: 'string', foreground: '00f3ff' },
                    { token: 'number', foreground: 'ff8c00' },
                ],
                colors: {
                    'editor.background': ThemeConfig.colors.bg.primary,
                    'editor.lineHighlightBackground': '#1f1f1f',
                }
            });
            monaco.editor.setTheme('project-xy');
        }
    }, [monaco]);

    return (
        <div className="flex flex-col h-full border border-[#1f1f1f] rounded-lg overflow-hidden bg-[#050505]">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#0a0a0a] border-b border-[#1f1f1f]">
                <div className="flex items-center gap-2">
                    <TerminalIcon size={16} className="text-cyan-500" />
                    <span className="text-xs font-mono font-bold text-gray-300 tracking-wider">
                        GHOST_SHELL // {language.toUpperCase()}
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    <button className="p-2 hover:bg-[#1f1f1f] rounded text-gray-500 hover:text-white transition-colors">
                        <Save size={16} />
                    </button>
                    <button
                        onClick={onExecute}
                        disabled={isExecuting}
                        className={clsx(
                            "flex items-center gap-2 px-4 py-1.5 rounded text-xs font-bold transition-all",
                            isExecuting
                                ? "bg-gray-800 text-gray-500 cursor-not-allowed"
                                : "bg-red-900/20 text-red-500 border border-red-900 hover:bg-red-900/40 hover:text-red-400 hover:shadow-[0_0_10px_rgba(255,42,42,0.3)]"
                        )}
                    >
                        {isExecuting ? (
                            <Zap size={14} className="animate-spin" />
                        ) : (
                            <Play size={14} />
                        )}
                        RUN ON TARGET
                    </button>
                </div>
            </div>

            {/* Editor Area */}
            <div className="flex-1 relative">
                <Editor
                    height="100%"
                    language={language}
                    value={code}
                    theme="project-xy"
                    onChange={onChange}
                    options={{
                        minimap: { enabled: false },
                        fontSize: 14,
                        fontFamily: 'Fira Code, monospace',
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        cursorBlinking: 'smooth',
                        cursorSmoothCaretAnimation: 'on',
                        padding: { top: 16 }
                    }}
                />
            </div>
        </div>
    );
};

export default GhostEditor;
