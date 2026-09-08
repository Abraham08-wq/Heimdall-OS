/**
 * MissionShell.tsx - Main Command Center Terminal Interface
 * 
 * The flagship UI component of the Sovereign Command Center.
 * Features: Tabbed interface, real-time execution streaming, script library browser,
 * execution history with forensic playback, approval workflows.
 * 
 * Design: Glassmorphism with cyan/purple hacker aesthetic
 * State: Zustand (global execution state, script library, approval queue)
 * Communication: WebSocket for real-time streaming, REST for CRUD operations
 */

'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { create } from 'zustand';
import {
  Terminal,
  Send,
  Search,
  Play,
  Pause,
  Square,
  Eye,
  Copy,
  Download,
  Settings,
  AlertCircle,
  CheckCircle,
  Clock,
  Zap,
} from 'lucide-react';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

interface Script {
  id: string;
  name: string;
  language: 'python' | 'bash';
  code: string;
  team: 'RED' | 'BLUE';
  category: 'RECON' | 'EXPLOIT' | 'PATCH' | 'ISOLATION' | 'FORENSICS' | 'HARDENING';
  danger_level: number;
  is_approved: boolean;
  metadata: Record<string, any>;
  created_at: string;
  created_by: string;
}

interface ExecutionResult {
  execution_id: string;
  script_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_seconds: number;
  started_at: string;
  completed_at: string | null;
}

interface ExecutionLog {
  type: 'stdout' | 'stderr' | 'status' | 'error';
  data: string;
  timestamp: string;
}

interface ApprovalRequest {
  id: string;
  script_id: string;
  script_name: string;
  danger_level: number;
  requested_by: string;
  requested_at: string;
  team: 'RED' | 'BLUE';
}

// ============================================================================
// ZUSTAND STORE - Global State Management
// ============================================================================

interface StoreState {
  // Script library state
  scripts: Script[];
  selectedScript: Script | null;
  scriptFilter: {
    team?: 'RED' | 'BLUE';
    category?: string;
    searchTerm?: string;
    maxDanger?: number;
  };
  setScriptFilter: (filter: Partial<StoreState['scriptFilter']>) => void;
  setSelectedScript: (script: Script | null) => void;
  loadScripts: (scripts: Script[]) => void;

  // Execution state
  currentExecution: ExecutionResult | null;
  executionLogs: ExecutionLog[];
  isExecuting: boolean;
  executionHistory: ExecutionResult[];
  addExecutionLog: (log: ExecutionLog) => void;
  setCurrentExecution: (execution: ExecutionResult | null) => void;
  setIsExecuting: (executing: boolean) => void;
  clearLogs: () => void;

  // Approval queue
  approvalQueue: ApprovalRequest[];
  setApprovalQueue: (queue: ApprovalRequest[]) => void;

  // UI state
  activeTab: 'console' | 'scripts' | 'history' | 'approvals' | 'intelligence';
  setActiveTab: (tab: StoreState['activeTab']) => void;
}

const useStore = create<StoreState>((set) => ({
  scripts: [],
  selectedScript: null,
  scriptFilter: {},
  setScriptFilter: (filter) =>
    set((state) => ({
      scriptFilter: { ...state.scriptFilter, ...filter },
    })),
  setSelectedScript: (script) => set({ selectedScript: script }),
  loadScripts: (scripts) => set({ scripts }),

  currentExecution: null,
  executionLogs: [],
  isExecuting: false,
  executionHistory: [],
  addExecutionLog: (log) =>
    set((state) => ({
      executionLogs: [...state.executionLogs, log],
    })),
  setCurrentExecution: (execution) => set({ currentExecution: execution }),
  setIsExecuting: (executing) => set({ isExecuting: executing }),
  clearLogs: () => set({ executionLogs: [] }),

  approvalQueue: [],
  setApprovalQueue: (queue) => set({ approvalQueue: queue }),

  activeTab: 'console',
  setActiveTab: (tab) => set({ activeTab: tab }),
}));

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

/**
 * ConsolePane - Real-time execution output terminal
 */
const ConsolePane: React.FC = () => {
  const { currentExecution, executionLogs, isExecuting } = useStore();
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (!isPaused) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [executionLogs, isPaused]);

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-slate-900 to-slate-950 border border-cyan-500/30 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-500/20 bg-black/40">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-cyan-400 animate-pulse" />
          <span className="text-cyan-300 font-mono text-sm font-bold">
            $ MISSION_CONSOLE
          </span>
        </div>
        <div className="flex gap-2">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsPaused(!isPaused)}
            className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
          >
            {isPaused ? (
              <Play className="w-4 h-4 text-cyan-400" />
            ) : (
              <Pause className="w-4 h-4 text-cyan-400" />
            )}
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => useStore.setState({ executionLogs: [] })}
            className="p-2 hover:bg-cyan-500/20 rounded transition-colors"
          >
            <Square className="w-4 h-4 text-cyan-400" />
          </motion.button>
        </div>
      </div>

      {/* Output Area */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1">
        {executionLogs.length === 0 ? (
          <div className="text-slate-600 italic">Ready for operations...</div>
        ) : (
          executionLogs.map((log, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-2 ${
                log.type === 'stderr'
                  ? 'text-red-400'
                  : log.type === 'status'
                    ? 'text-yellow-400'
                    : 'text-green-400'
              }`}
            >
              <span className="text-slate-600 min-w-fit">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span>{log.data}</span>
            </motion.div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Status Footer */}
      {currentExecution && (
        <div className="px-4 py-3 border-t border-cyan-500/20 bg-black/40 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isExecuting ? (
              <>
                <Zap className="w-4 h-4 text-yellow-400 animate-pulse" />
                <span className="text-yellow-400 text-sm">Executing...</span>
              </>
            ) : currentExecution.status === 'COMPLETED' ? (
              <>
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-green-400 text-sm">Completed</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-4 h-4 text-red-400" />
                <span className="text-red-400 text-sm">{currentExecution.status}</span>
              </>
            )}
          </div>
          <span className="text-slate-400 text-sm">
            Duration: {currentExecution.duration_seconds.toFixed(2)}s
          </span>
        </div>
      )}
    </div>
  );
};

/**
 * ScriptLibraryPane - Browse and filter available scripts
 */
const ScriptLibraryPane: React.FC = () => {
  const { scripts, selectedScript, setSelectedScript, scriptFilter, setScriptFilter } =
    useStore();

  const filteredScripts = scripts.filter((script) => {
    if (scriptFilter.team && script.team !== scriptFilter.team) return false;
    if (scriptFilter.category && script.category !== scriptFilter.category) return false;
    if (scriptFilter.maxDanger && script.danger_level > scriptFilter.maxDanger)
      return false;
    if (
      scriptFilter.searchTerm &&
      !script.name.toLowerCase().includes(scriptFilter.searchTerm.toLowerCase())
    )
      return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Filters */}
      <div className="bg-slate-900/50 border border-cyan-500/20 rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search scripts..."
            className="flex-1 px-3 py-2 bg-slate-950 border border-cyan-500/30 rounded text-cyan-300 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
            value={scriptFilter.searchTerm || ''}
            onChange={(e) => setScriptFilter({ searchTerm: e.target.value })}
          />
          <Search className="w-5 h-5 text-cyan-400 self-center" />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <select
            className="px-3 py-2 bg-slate-950 border border-cyan-500/30 rounded text-cyan-300 focus:outline-none focus:border-cyan-400"
            value={scriptFilter.team || ''}
            onChange={(e) => setScriptFilter({ team: e.target.value as 'RED' | 'BLUE' })}
          >
            <option value="">All Teams</option>
            <option value="RED">🔴 Red Team</option>
            <option value="BLUE">🔵 Blue Team</option>
          </select>

          <select
            className="px-3 py-2 bg-slate-950 border border-cyan-500/30 rounded text-cyan-300 focus:outline-none focus:border-cyan-400"
            value={scriptFilter.maxDanger || ''}
            onChange={(e) =>
              setScriptFilter({ maxDanger: e.target.value ? parseInt(e.target.value) : undefined })
            }
          >
            <option value="">All Danger Levels</option>
            <option value="3">Low (1-3)</option>
            <option value="6">Medium (4-6)</option>
            <option value="10">High (7+)</option>
          </select>
        </div>
      </div>

      {/* Script List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        <AnimatePresence>
          {filteredScripts.map((script) => (
            <motion.button
              key={script.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              onClick={() => setSelectedScript(script)}
              className={`w-full text-left p-3 rounded-lg border transition-all ${
                selectedScript?.id === script.id
                  ? 'bg-cyan-500/30 border-cyan-400'
                  : 'bg-slate-900/50 border-cyan-500/20 hover:bg-slate-800/50'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-sm font-bold text-cyan-300">
                  {script.name}
                </span>
                <div className="flex gap-2">
                  <span
                    className={`px-2 py-1 rounded text-xs font-bold ${
                      script.team === 'RED'
                        ? 'bg-red-900/50 text-red-300'
                        : 'bg-blue-900/50 text-blue-300'
                    }`}
                  >
                    {script.team}
                  </span>
                  <span className="px-2 py-1 rounded text-xs font-bold bg-yellow-900/50 text-yellow-300">
                    ⚠️ {script.danger_level}/10
                  </span>
                </div>
              </div>
              <div className="text-xs text-slate-400">
                {script.category} • {script.language.toUpperCase()}
              </div>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>

      {/* Selected Script Details */}
      {selectedScript && (
        <div className="bg-slate-900/50 border border-cyan-500/20 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-cyan-300 font-bold">{selectedScript.name}</h3>
            {!selectedScript.is_approved && (
              <AlertCircle className="w-4 h-4 text-yellow-400" />
            )}
          </div>
          <div className="bg-slate-950 rounded p-3 font-mono text-xs text-green-400 max-h-32 overflow-y-auto">
            {selectedScript.code}
          </div>
          <div className="mt-3 flex gap-2">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigator.clipboard.writeText(selectedScript.code)}
              className="flex-1 px-3 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 rounded text-cyan-300 text-sm flex items-center justify-center gap-2"
            >
              <Copy className="w-4 h-4" />
              Copy
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex-1 px-3 py-2 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 rounded text-green-300 text-sm flex items-center justify-center gap-2"
            >
              <Play className="w-4 h-4" />
              Execute
            </motion.button>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * ExecutionHistoryPane - Forensic DVR with playback capability
 */
const ExecutionHistoryPane: React.FC = () => {
  const { executionHistory } = useStore();
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResult | null>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  return (
    <div className="grid grid-cols-3 gap-4 h-full">
      {/* History List */}
      <div className="col-span-1 overflow-y-auto space-y-2">
        {executionHistory.map((execution) => (
          <motion.button
            key={execution.execution_id}
            whileHover={{ scale: 1.02 }}
            onClick={() => setSelectedExecution(execution)}
            className={`w-full text-left p-3 rounded-lg border transition-all ${
              selectedExecution?.execution_id === execution.execution_id
                ? 'bg-cyan-500/30 border-cyan-400'
                : 'bg-slate-900/50 border-cyan-500/20 hover:bg-slate-800/50'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              {execution.status === 'COMPLETED' ? (
                <CheckCircle className="w-4 h-4 text-green-400" />
              ) : execution.status === 'FAILED' ? (
                <AlertCircle className="w-4 h-4 text-red-400" />
              ) : (
                <Clock className="w-4 h-4 text-yellow-400" />
              )}
              <span className="text-xs text-slate-400">
                {new Date(execution.started_at).toLocaleString()}
              </span>
            </div>
            <div className="text-xs text-cyan-300 font-mono">
              Exit: {execution.exit_code}
            </div>
          </motion.button>
        ))}
      </div>

      {/* Playback View */}
      {selectedExecution && (
        <div className="col-span-2 flex flex-col gap-4">
          <div className="bg-slate-900/50 border border-cyan-500/20 rounded-lg p-4 flex-1 overflow-hidden">
            <div className="h-full bg-slate-950 rounded font-mono text-sm text-green-400 overflow-y-auto p-3">
              <div className="text-cyan-400 mb-2">$ Forensic DVR Playback</div>
              <div>{selectedExecution.stdout}</div>
              {selectedExecution.stderr && (
                <div className="text-red-400 mt-2">{selectedExecution.stderr}</div>
              )}
            </div>
          </div>

          {/* Playback Controls */}
          <div className="bg-slate-900/50 border border-cyan-500/20 rounded-lg p-3 flex items-center justify-between">
            <div className="flex gap-2">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                className="p-2 bg-cyan-500/20 hover:bg-cyan-500/30 rounded border border-cyan-500/30"
              >
                <Play className="w-4 h-4 text-cyan-400" />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                className="p-2 bg-cyan-500/20 hover:bg-cyan-500/30 rounded border border-cyan-500/30"
              >
                <Pause className="w-4 h-4 text-cyan-400" />
              </motion.button>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Speed:</span>
              <select
                value={playbackSpeed}
                onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
                className="px-2 py-1 bg-slate-950 border border-cyan-500/30 rounded text-cyan-300 text-xs focus:outline-none focus:border-cyan-400"
              >
                <option value={0.5}>0.5x</option>
                <option value={1}>1x</option>
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
            </div>

            <div className="flex gap-2">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                className="p-2 bg-cyan-500/20 hover:bg-cyan-500/30 rounded border border-cyan-500/30"
              >
                <Download className="w-4 h-4 text-cyan-400" />
              </motion.button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * ApprovalQueuePane - Manage pending script approvals
 */
const ApprovalQueuePane: React.FC = () => {
  const { approvalQueue } = useStore();

  return (
    <div className="space-y-3">
      {approvalQueue.length === 0 ? (
        <div className="p-8 text-center text-slate-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No pending approvals</p>
        </div>
      ) : (
        approvalQueue.map((request) => (
          <motion.div
            key={request.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/50 border border-yellow-500/30 rounded-lg p-4"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-yellow-300 font-bold">{request.script_name}</h3>
                <div className="text-xs text-slate-400 mt-1">
                  Requested by: {request.requested_by} •{' '}
                  {new Date(request.requested_at).toLocaleString()}
                </div>
              </div>
              <span className="px-2 py-1 rounded text-xs font-bold bg-red-900/50 text-red-300">
                ⚠️ {request.danger_level}/10
              </span>
            </div>

            <div className="flex gap-2">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="flex-1 px-3 py-2 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 rounded text-green-300 text-sm font-bold"
              >
                ✓ Approve
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="flex-1 px-3 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded text-red-300 text-sm font-bold"
              >
                ✗ Reject
              </motion.button>
            </div>
          </motion.div>
        ))
      )}
    </div>
  );
};

/**
 * IntelligencePaneStub - Placeholder for Phase 3 intelligence features
 */
const IntelligencePaneStub: React.FC = () => {
  return (
    <div className="h-full flex flex-col items-center justify-center text-slate-500">
      <Zap className="w-16 h-16 mb-4 opacity-30" />
      <p className="text-lg font-bold mb-2">Phase 3: Neural Intelligence</p>
      <p className="text-sm text-center">
        De-Masking • Linguistic Translation • Digital Snapshots • Purple Team Feedback
      </p>
      <p className="text-xs mt-4 opacity-50">Coming in next phase...</p>
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT - MissionShell
// ============================================================================

export const MissionShell: React.FC = () => {
  const { activeTab, setActiveTab } = useStore();

  const tabs: Array<{
    id: StoreState['activeTab'];
    label: string;
    icon: React.ReactNode;
  }> = [
    { id: 'console', label: 'Console', icon: <Terminal className="w-4 h-4" /> },
    { id: 'scripts', label: 'Arsenal', icon: <Zap className="w-4 h-4" /> },
    { id: 'history', label: 'Forensics', icon: <Clock className="w-4 h-4" /> },
    { id: 'approvals', label: 'Approvals', icon: <AlertCircle className="w-4 h-4" /> },
    { id: 'intelligence', label: 'Intelligence', icon: <Eye className="w-4 h-4" /> },
  ];

  return (
    <div className="w-full h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-cyan-500/20 bg-black/40 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
              SOVEREIGN COMMAND CENTER
            </h1>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-2 hover:bg-cyan-500/20 rounded-lg transition-colors"
          >
            <Settings className="w-5 h-5 text-cyan-400" />
          </motion.button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 px-6 py-3 border-b border-cyan-500/20 bg-black/20 overflow-x-auto">
        {tabs.map((tab) => (
          <motion.button
            key={tab.id}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm font-bold whitespace-nowrap transition-all ${
              activeTab === tab.id
                ? 'bg-cyan-500/30 text-cyan-300 border border-cyan-400'
                : 'text-slate-400 hover:text-cyan-300 border border-transparent'
            }`}
          >
            {tab.icon}
            {tab.label}
          </motion.button>
        ))}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden p-6">
        <AnimatePresence mode="wait">
          {activeTab === 'console' && (
            <motion.div
              key="console"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full"
            >
              <ConsolePane />
            </motion.div>
          )}

          {activeTab === 'scripts' && (
            <motion.div
              key="scripts"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full"
            >
              <ScriptLibraryPane />
            </motion.div>
          )}

          {activeTab === 'history' && (
            <motion.div
              key="history"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full"
            >
              <ExecutionHistoryPane />
            </motion.div>
          )}

          {activeTab === 'approvals' && (
            <motion.div
              key="approvals"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <ApprovalQueuePane />
            </motion.div>
          )}

          {activeTab === 'intelligence' && (
            <motion.div
              key="intelligence"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="h-full"
            >
              <IntelligencePaneStub />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default MissionShell;
