/**
 * ForensicPlaybackTab.tsx - Forensic DVR for Attack Playback
 *
 * Features:
 * - Replay past command executions
 * - Timeline scrubbing
 * - Speed controls (0.5x, 1x, 2x, 4x)
 * - Log export and sharing
 * - Timeline visualization
 */

'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Download,
  Share2,
  ZoomIn,
  ZoomOut,
  Clock,
} from 'lucide-react';

interface ExecutionLogEntry {
  timestamp: string;
  type: 'stdout' | 'stderr' | 'status' | 'error';
  data: string;
}

interface Execution {
  id: string;
  script_name: string;
  status: string;
  exit_code: number | null;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number;
  logs: ExecutionLogEntry[];
}

interface ForensicPlaybackTabProps {
  execution: Execution | null;
  executionHistory: Execution[];
  onSelectExecution?: (execution: Execution) => void;
}

export const ForensicPlaybackTab: React.FC<ForensicPlaybackTabProps> = ({
  execution,
  executionHistory,
  onSelectExecution,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [currentLogIndex, setCurrentLogIndex] = useState(0);
  const [displayedLogs, setDisplayedLogs] = useState<ExecutionLogEntry[]>([]);
  const playbackIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const logs = useMemo(() => execution?.logs || [], [execution?.logs]);
  const totalLogs = logs.length;
  const progress = totalLogs > 0 ? (currentLogIndex / totalLogs) * 100 : 0;

  // Auto-scroll to latest log
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayedLogs]);

  // Handle playback
  useEffect(() => {
    if (!isPlaying || !logs || logs.length === 0) {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current);
      }
      return;
    }

    const delay = Math.max(50, Math.round(100 / playbackSpeed));
    playbackIntervalRef.current = setInterval(() => {
      setCurrentLogIndex((prev) => {
        if (prev >= totalLogs - 1) {
          setIsPlaying(false);
          return totalLogs - 1;
        }
        return prev + 1;
      });
    }, delay);

    return () => {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, totalLogs, logs]);

  // Update displayed logs based on current index
  useEffect(() => {
    setDisplayedLogs(logs.slice(0, currentLogIndex + 1));
  }, [currentLogIndex, logs]);

  const getLogColor = (type: string) => {
    switch (type) {
      case 'stdout':
        return 'text-green-400';
      case 'stderr':
        return 'text-red-400';
      case 'status':
        return 'text-yellow-400';
      case 'error':
        return 'text-red-500';
      default:
        return 'text-slate-400';
    }
  };

  if (!execution) {
    return (
      <div className="flex flex-col h-full gap-4">
        <div className="text-slate-600 italic text-center py-8">
          Select an execution from history to view playback
        </div>

        {/* Execution History List */}
        <div className="space-y-2 overflow-y-auto">
          {executionHistory.length === 0 ? (
            <div className="text-slate-600 italic text-center py-4">
              No execution history yet
            </div>
          ) : (
            executionHistory.map((exec) => (
              <motion.button
                key={exec.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  onSelectExecution?.(exec);
                  setCurrentLogIndex(0);
                  setIsPlaying(false);
                  setDisplayedLogs([]);
                }}
                className="w-full text-left p-3 bg-slate-900/50 border border-cyan-500/20 rounded hover:border-cyan-400/50 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-cyan-300">{exec.script_name}</span>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      exec.status === 'COMPLETED'
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}
                  >
                    {exec.status}
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  {new Date(exec.started_at).toLocaleString()} · {exec.duration_seconds.toFixed(2)}s
                </div>
              </motion.button>
            ))
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <div className="bg-slate-900/50 border border-cyan-500/20 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold text-cyan-300">{execution.script_name}</h3>
            <p className="text-xs text-slate-500">
              {new Date(execution.started_at).toLocaleString()} · {execution.duration_seconds.toFixed(2)}s
            </p>
          </div>
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                const content = displayedLogs.map((log) => `[${log.type}] ${log.data}`).join('\n');
                const blob = new Blob([content], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${execution.script_name}-${execution.id}.log`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
              title="Download logs"
            >
              <Download className="w-4 h-4 text-cyan-400" />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => {
                const content = displayedLogs.map((log) => `[${log.type}] ${log.data}`).join('\n');
                navigator.clipboard.writeText(content);
              }}
              className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
              title="Copy logs"
            >
              <Share2 className="w-4 h-4 text-cyan-400" />
            </motion.button>
          </div>
        </div>

        {/* Playback Controls */}
        <div className="flex items-center gap-3 mb-3">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => {
              setCurrentLogIndex(0);
              setDisplayedLogs([]);
              setIsPlaying(false);
            }}
            className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
            title="Restart playback"
          >
            <SkipBack className="w-4 h-4 text-cyan-400" />
          </motion.button>

          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 text-cyan-400" />
            ) : (
              <Play className="w-4 h-4 text-cyan-400" />
            )}
          </motion.button>

          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setCurrentLogIndex(Math.min(totalLogs - 1, currentLogIndex + 10))}
            className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
            title="Fast forward"
          >
            <SkipForward className="w-4 h-4 text-cyan-400" />
          </motion.button>

          <div className="text-xs text-slate-400">
            {currentLogIndex + 1} / {totalLogs}
          </div>

          <div className="flex-1 flex items-center gap-2">
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
              className="px-2 py-1 bg-slate-950 border border-cyan-500/30 rounded text-xs text-cyan-300 focus:outline-none focus:border-cyan-400"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-950 border border-cyan-500/20 rounded h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Logs Output */}
      <div className="flex-1 bg-gradient-to-b from-slate-900 to-slate-950 border border-cyan-500/30 rounded-lg overflow-y-auto p-4 font-mono text-sm space-y-1">
        {displayedLogs.length === 0 ? (
          <div className="text-slate-600 italic">Playback ready. Press play to begin.</div>
        ) : (
          displayedLogs.map((log, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className={`flex gap-2 ${getLogColor(log.type)}`}
            >
              <span className="text-slate-600 min-w-fit">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className="text-slate-500">[{log.type}]</span>
              <span>{log.data}</span>
            </motion.div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
};

export default ForensicPlaybackTab;
