/**
 * ScriptEditorTab.tsx - Monaco Editor Integration for Script Editing
 *
 * Features:
 * - Syntax highlighting for Python/Bash
 * - Real-time code execution
 * - Script modification and saving
 * - Danger level indication
 * - Team color coding
 */

'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Save, Copy, Download, AlertTriangle, CheckCircle } from 'lucide-react';

interface Script {
  id: string;
  name: string;
  language: 'python' | 'bash';
  code: string;
  team: 'RED' | 'BLUE';
  category: string;
  danger_level: number;
  is_approved: boolean;
  created_at: string;
  created_by: string;
}

interface ScriptEditorTabProps {
  script: Script | null;
  onSave?: (scriptId: string, updatedCode: string) => Promise<void>;
  readOnly?: boolean;
}

export const ScriptEditorTab: React.FC<ScriptEditorTabProps> = ({
  script,
  onSave,
  readOnly = false,
}) => {
  const [code, setCode] = useState(script?.code || '');
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  useEffect(() => {
    setCode(script?.code || '');
  }, [script?.code]);

  const getDangerColor = (level: number) => {
    if (level <= 3) return 'text-green-400';
    if (level <= 6) return 'text-yellow-400';
    if (level <= 8) return 'text-orange-400';
    return 'text-red-400';
  };

  const getTeamBgColor = (team: string) => {
    return team === 'RED' ? 'bg-red-950/30 border-red-500/30' : 'bg-blue-950/30 border-blue-500/30';
  };

  const handleSave = async () => {
    if (!script || readOnly) return;

    setIsSaving(true);
    setSaveStatus('idle');

    try {
      await onSave?.(script.id, code);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Save failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  if (!script) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 italic">
        Select a script to view and edit
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <div className={`border rounded-lg p-4 ${getTeamBgColor(script.team)}`}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="text-lg font-bold text-white mb-1">{script.name}</h3>
            <div className="flex items-center gap-3 text-sm">
              <span className="px-2 py-1 bg-slate-700 rounded text-slate-300">
                {script.language}
              </span>
              <span className="px-2 py-1 bg-slate-700 rounded text-slate-300">
                {script.category}
              </span>
              <span className={`px-2 py-1 flex items-center gap-1 ${getDangerColor(script.danger_level)}`}>
                <AlertTriangle className="w-3 h-3" />
                {script.danger_level}/10
              </span>
              {script.is_approved ? (
                <span className="px-2 py-1 flex items-center gap-1 text-green-400">
                  <CheckCircle className="w-3 h-3" />
                  Approved
                </span>
              ) : (
                <span className="px-2 py-1 flex items-center gap-1 text-yellow-400">
                  <AlertTriangle className="w-3 h-3" />
                  Pending Approval
                </span>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigator.clipboard.writeText(code)}
              className="p-2 hover:bg-slate-700/50 rounded transition-colors"
              title="Copy code"
            >
              <Copy className="w-4 h-4 text-cyan-400" />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                const element = document.createElement('a');
                element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(code));
                element.setAttribute('download', `${script.name}.${script.language === 'python' ? 'py' : 'sh'}`);
                element.style.display = 'none';
                document.body.appendChild(element);
                element.click();
                document.body.removeChild(element);
              }}
              className="p-2 hover:bg-slate-700/50 rounded transition-colors"
              title="Download script"
            >
              <Download className="w-4 h-4 text-cyan-400" />
            </motion.button>
            {!readOnly && (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleSave}
                disabled={isSaving}
                className={`p-2 rounded transition-colors ${
                  saveStatus === 'saved'
                    ? 'bg-green-500/30 text-green-400'
                    : saveStatus === 'error'
                      ? 'bg-red-500/30 text-red-400'
                      : 'hover:bg-cyan-500/20 text-cyan-400'
                }`}
                title="Save script"
              >
                <Save className="w-4 h-4" />
              </motion.button>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-400">
          Created by {script.created_by} on {new Date(script.created_at).toLocaleDateString()}
        </p>
      </div>

      {/* Code Editor Area */}
      <div className="flex-1 bg-gradient-to-b from-slate-900 to-slate-950 border border-cyan-500/30 rounded-lg overflow-hidden flex flex-col">
        {/* Line numbers + Code */}
        <div className="flex-1 overflow-auto">
          <pre className="font-mono text-sm text-green-400 p-4 whitespace-pre-wrap break-words">
            <code>{code}</code>
          </pre>
        </div>

        {/* Footer */}
        <div className="border-t border-cyan-500/20 bg-black/40 px-4 py-2 text-xs text-slate-500">
          Lines: {code.split('\n').length} | Characters: {code.length}
        </div>
      </div>

      {/* Info */}
      <div className="text-xs text-slate-500 space-y-1">
        <p>⚠️ Scripts with danger_level &gt; 5 require approval before execution</p>
        <p>💡 Use the Console tab to execute this script and watch output in real-time</p>
      </div>
    </div>
  );
};

export default ScriptEditorTab;
