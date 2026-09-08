import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin,
  Radar,
  Zap,
  Cpu,
  Bell,
  Settings,
  Command,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Activity,
  Search,
  RefreshCw,
} from 'lucide-react';
import { CommandPalette, type Command as CommandType } from './CommandPalette';
import { api } from '@/lib/api';
import { GlassDossier, type EntityData } from './GlassDossier';

interface CommandCenterProps {
  children?: React.ReactNode;
  onTabChange?: (tab: string) => void;
  selectedNode?: any;
  onNodeSelect?: (node: any) => void;
  onDeepScan?: (nodeId: string) => void;
}

type TabType = 'battlefield' | 'intelligence' | 'offensive' | 'systems';

interface TabConfig {
  id: TabType;
  label: string;
  icon: React.ReactNode;
  badge?: number;
  component: React.ComponentType<any>;
}

interface TabBadges {
  [key: string]: number;
}

// Enhanced Tab Components with Better Styling
const BattlefieldTab: React.FC<any> = ({ children }) => (
  <motion.div 
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="h-full w-full flex flex-col"
  >
    <div className="flex-1 overflow-hidden rounded-xl border border-white/5 bg-gradient-to-br from-slate-900/20 to-slate-800/20 backdrop-blur">
      {children || <div className="flex items-center justify-center h-full text-white/40">Battlefield View</div>}
    </div>
  </motion.div>
);

const IntelligenceTab: React.FC<any> = ({ onNodeSelect, selectedNode, onDeepScan }) => {
  const [scanResults, setScanResults] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [threatLevel, setThreatLevel] = useState<'critical' | 'high' | 'medium' | 'low'>('medium');

  useEffect(() => {
    if (selectedNode) {
      setIsLoading(true);
      const fetchAnalysis = async () => {
        try {
            const analysis = await api.getRiskAnalysis(selectedNode.id);
            const threats = analysis.linked_threats?.length || 0;
            setThreatLevel(
                analysis.risk_score >= 90 ? 'critical' :
                analysis.risk_score >= 70 ? 'high' :
                analysis.risk_score >= 40 ? 'medium' :
                'low'
            );
            setScanResults({
                node: selectedNode,
                leaks: analysis.leaks || [],
                threats,
                malware: analysis.malware_detected,
                c2Communication: analysis.c2_communication,
                exploits: analysis.vulnerabilities?.length || 0,
            });
        } catch (error) {
            console.error('Failed to get risk analysis:', error);
        } finally {
            setIsLoading(false);
        }
      }
      fetchAnalysis();
    }
  }, [selectedNode]);

  const riskColors = {
    critical: 'from-red-500/20 to-red-600/10 border-red-500/30',
    high: 'from-orange-500/20 to-orange-600/10 border-orange-500/30',
    medium: 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30',
    low: 'from-green-500/20 to-green-600/10 border-green-500/30',
  };

  const riskBgColors = {
    critical: 'bg-red-500/10',
    high: 'bg-orange-500/10',
    medium: 'bg-yellow-500/10',
    low: 'bg-green-500/10',
  };

  const riskTextColors = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-yellow-400',
    low: 'text-green-400',
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="h-full space-y-4 overflow-y-auto pr-4"
    >
      {/* Intelligence Status Card */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="p-6 rounded-xl border border-cyan-500/30 bg-gradient-to-br from-cyan-500/10 to-blue-500/5 backdrop-blur"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 3, repeat: Infinity }}>
              <Radar className="text-cyan-400" size={20} />
            </motion.div>
            <h3 className="text-lg font-bold text-white">Intelligence Feeds</h3>
          </div>
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-3 h-3 rounded-full bg-cyan-400"
          />
        </div>
        <p className="text-sm text-white/60">Real-time threat intelligence monitoring</p>
      </motion.div>

      {/* Scan Status */}
      {isLoading && (
        <motion.div
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="p-4 rounded-lg border border-blue-500/30 bg-blue-500/10 backdrop-blur"
        >
          <div className="flex items-center gap-3">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            >
              <RefreshCw className="text-blue-400" size={18} />
            </motion.div>
            <p className="text-sm font-mono text-blue-300">Scanning selected node...</p>
          </div>
        </motion.div>
      )}

      {/* Scan Results */}
      {scanResults && (
        <>
          {/* Risk Level Card */}
          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.15 }}
            className={`p-6 rounded-xl border bg-gradient-to-br ${riskColors[threatLevel]} backdrop-blur`}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h4 className="text-sm font-mono text-white/60 mb-2">RISK ASSESSMENT</h4>
                <p className={`text-2xl font-bold ${riskTextColors[threatLevel]}`}>
                  {threatLevel.toUpperCase()}
                </p>
              </div>
              {threatLevel === 'critical' && <AlertCircle className="text-red-400" size={24} />}
              {threatLevel === 'high' && <AlertCircle className="text-orange-400" size={24} />}
              {threatLevel === 'low' && <CheckCircle2 className="text-green-400" size={24} />}
            </div>
          </motion.div>

          {/* Node Details Grid */}
          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-2 gap-3"
          >
            <div className="p-4 rounded-lg bg-white/5 border border-white/10 backdrop-blur">
              <p className="text-xs text-white/50 mb-2">NODE ID</p>
              <p className="text-sm font-mono text-white/80 truncate">{scanResults.node?.id}</p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10 backdrop-blur">
              <p className="text-xs text-white/50 mb-2">THREATS</p>
              <p className={`text-sm font-bold ${riskTextColors[threatLevel]}`}>
                {scanResults.threats} detected
              </p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10 backdrop-blur">
              <p className="text-xs text-white/50 mb-2">TYPE</p>
              <p className="text-sm font-mono text-white/80">{scanResults.node?.type || 'Unknown'}</p>
            </div>
            <div className="p-4 rounded-lg bg-white/5 border border-white/10 backdrop-blur">
              <p className="text-xs text-white/50 mb-2">STATUS</p>
              <p className="text-sm text-green-400 font-bold">✓ Active</p>
            </div>
          </motion.div>

          {/* Threat Indicators */}
          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.25 }}
            className={`p-6 rounded-xl border ${riskBgColors[threatLevel]} backdrop-blur border-white/10`}
          >
            <h4 className="text-sm font-mono text-white/60 mb-4">THREAT INDICATORS</h4>
            <div className="space-y-3">
              {scanResults.malware && (
                <div className="flex items-center gap-3 p-2 rounded bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="text-red-400" size={16} />
                  <span className="text-sm text-red-300">Malware signature detected</span>
                </div>
              )}
              {scanResults.c2Communication && (
                <div className="flex items-center gap-3 p-2 rounded bg-orange-500/10 border border-orange-500/20">
                  <AlertCircle className="text-orange-400" size={16} />
                  <span className="text-sm text-orange-300">C2 communication pattern</span>
                </div>
              )}
              {scanResults.exploits > 0 && (
                <div className="flex items-center gap-3 p-2 rounded bg-yellow-500/10 border border-yellow-500/20">
                  <AlertCircle className="text-yellow-400" size={16} />
                  <span className="text-sm text-yellow-300">{scanResults.exploits} exploits found</span>
                </div>
              )}
              {scanResults.leaks.length > 0 && (
                <div className="flex items-center gap-3 p-2 rounded bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="text-red-400" size={16} />
                  <span className="text-sm text-red-300">Data leak risk: {scanResults.leaks.length}</span>
                </div>
              )}
              {scanResults.threats === 0 && (
                <div className="flex items-center gap-3 p-2 rounded bg-green-500/10 border border-green-500/20">
                  <CheckCircle2 className="text-green-400" size={16} />
                  <span className="text-sm text-green-300">No immediate threats detected</span>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}

      {!selectedNode && !isLoading && (
        <motion.div
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="flex flex-col items-center justify-center h-32 text-white/40 gap-2"
        >
          <Search size={32} />
          <p className="text-sm">Select a node to begin intelligence gathering</p>
        </motion.div>
      )}
    </motion.div>
  );
};

const OffensiveTab: React.FC<any> = () => {
  const offensiveTools = [
    { name: 'Recon-ng', status: 'Ready', color: 'cyan' },
    { name: 'Exploit Kit', status: 'Armed', color: 'orange' },
    { name: 'Payload Gen', status: 'Staged', color: 'purple' },
    { name: 'C2 Server', status: 'Online', color: 'red' },
  ];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="h-full space-y-4 overflow-y-auto pr-4"
    >
      {/* Offensive Status */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="p-6 rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-500/10 to-pink-500/5 backdrop-blur"
      >
        <div className="flex items-center gap-2 mb-2">
          <Zap className="text-purple-400" size={20} />
          <h3 className="text-lg font-bold text-white">Offensive Operations</h3>
        </div>
        <p className="text-sm text-white/60">Authorized penetration testing toolkit</p>
      </motion.div>

      {/* Tools Grid */}
      <div className="grid grid-cols-2 gap-4">
        {offensiveTools.map((tool, idx) => (
          <motion.div
            key={tool.name}
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: idx * 0.05 }}
            className="p-4 rounded-lg border border-white/10 bg-white/5 backdrop-blur hover:bg-white/10 transition-colors cursor-pointer group"
          >
            <div className="flex items-start justify-between mb-3">
              <h4 className="font-mono text-sm font-bold text-white">{tool.name}</h4>
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className={`w-2 h-2 rounded-full bg-${tool.color}-400`}
              />
            </div>
            <p className={`text-xs font-mono text-${tool.color}-400`}>● {tool.status}</p>
          </motion.div>
        ))}
      </div>

      {/* Operations Guide */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="p-6 rounded-xl border border-yellow-500/30 bg-yellow-500/10 backdrop-blur"
      >
        <p className="text-sm text-yellow-300 mb-3 font-bold">⚠️ Authorization Required</p>
        <ul className="text-xs text-white/60 space-y-1 font-mono">
          <li>• Verify Rules of Engagement (ROE) status</li>
          <li>• Confirm target authorization</li>
          <li>• Enable automated logging and reporting</li>
          <li>• Maintain operational security (OPSEC)</li>
        </ul>
      </motion.div>
    </motion.div>
  );
};

const SystemsTab: React.FC<any> = () => {
  const systemMetrics = [
    { label: 'Backend Health', status: 'Operational', icon: Activity, color: 'green' },
    { label: 'Neo4j Graph', status: 'Connected', icon: TrendingUp, color: 'cyan' },
    { label: 'Kafka Streams', status: 'Active', icon: Activity, color: 'blue' },
    { label: 'API Gateway', status: 'Healthy', icon: CheckCircle2, color: 'green' },
  ];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="h-full space-y-4 overflow-y-auto pr-4"
    >
      {/* System Status Overview */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="p-6 rounded-xl border border-blue-500/30 bg-gradient-to-br from-blue-500/10 to-cyan-500/5 backdrop-blur"
      >
        <div className="flex items-center gap-2 mb-2">
          <Cpu className="text-blue-400" size={20} />
          <h3 className="text-lg font-bold text-white">System Status</h3>
        </div>
        <p className="text-sm text-white/60">Real-time infrastructure monitoring</p>
      </motion.div>

      {/* System Metrics Grid */}
      <div className="grid grid-cols-2 gap-4">
        {systemMetrics.map((metric, idx) => {
          const Icon = metric.icon;
          return (
            <motion.div
              key={metric.label}
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: idx * 0.05 }}
              className="p-4 rounded-lg border border-white/10 bg-white/5 backdrop-blur"
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon className={`text-${metric.color}-400`} size={16} />
                <p className="text-xs text-white/50 font-mono">{metric.label}</p>
              </div>
              <p className={`text-sm font-bold text-${metric.color}-400`}>✓ {metric.status}</p>
            </motion.div>
          );
        })}
      </div>

      {/* Performance Metrics */}
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="p-6 rounded-xl border border-white/10 bg-white/5 backdrop-blur space-y-3"
      >
        <h4 className="text-sm font-mono text-white/60 mb-4">PERFORMANCE METRICS</h4>
        {[
          { label: 'API Response Time', value: '45ms', good: true },
          { label: 'Database Load', value: '32%', good: true },
          { label: 'Memory Usage', value: '68%', good: true },
          { label: 'Cache Hit Rate', value: '94%', good: true },
        ].map((metric) => (
          <div key={metric.label} className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-white/60">{metric.label}</span>
              <span className={`font-bold ${metric.good ? 'text-green-400' : 'text-red-400'}`}>
                {metric.value}
              </span>
            </div>
            <div className="h-1 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: '0%' }}
                animate={{ width: metric.value }}
                transition={{ duration: 1 }}
                className={`h-full rounded-full ${metric.good ? 'bg-green-400' : 'bg-red-400'}`}
              />
            </div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
};

export const CommandCenter: React.FC<CommandCenterProps> = ({
  children,
  onTabChange,
  selectedNode,
  onNodeSelect,
  onDeepScan,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('battlefield');
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isEntityDossierOpen, setIsEntityDossierOpen] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<EntityData | null>(null);
  const [tabBadges, setTabBadges] = useState<TabBadges>({});

  // Simulated entity data from selected node
  const getEntityFromNode = useCallback((node: any): EntityData | null => {
    if (!node) return null;

    return {
      id: node.id || 'unknown',
      name: node.name || 'Unknown Entity',
      type: node.type || 'Unknown Type',
      riskLevel: node.riskLevel || 'medium',
      description: node.description || 'No description available',
      attributes: {
        'Node ID': node.id,
        'Type': node.type,
        'Status': node.status || 'Active',
        'Last Seen': new Date().toLocaleDateString(),
        ...node.attributes,
      },
      threatIndicators: node.threatIndicators || undefined,
    };
  }, []);

  // Handle node selection and open dossier
  const handleNodeSelect = useCallback(
    (node: any) => {
      const entity = getEntityFromNode(node);
      if (entity) {
        setSelectedEntity(entity);
        setIsEntityDossierOpen(true);
      }
      onNodeSelect?.(node);
    },
    [getEntityFromNode, onNodeSelect]
  );

  // Update tab when active tab changes
  useEffect(() => {
    onTabChange?.(activeTab);
  }, [activeTab, onTabChange]);



  // Command palette commands
  const commands: CommandType[] = [
    {
      id: 'switch-battlefield',
      label: 'Switch to Battlefield',
      description: 'View the Neo4j threat graph',
      action: () => setActiveTab('battlefield'),
      category: 'battlefield',
      hotkey: 'Ctrl+1',
    },
    {
      id: 'switch-intelligence',
      label: 'Switch to Intelligence',
      description: 'View Intel X and Censys feeds',
      action: () => setActiveTab('intelligence'),
      category: 'intelligence',
      hotkey: 'Ctrl+2',
    },
    {
      id: 'switch-offensive',
      label: 'Switch to Offensive',
      description: 'Launch recon and exploit tools',
      action: () => setActiveTab('offensive'),
      category: 'offensive',
      hotkey: 'Ctrl+3',
    },
    {
      id: 'switch-systems',
      label: 'Switch to Systems',
      description: 'Monitor system health',
      action: () => setActiveTab('systems'),
      category: 'tools',
      hotkey: 'Ctrl+4',
    },
    {
      id: 'refresh-feeds',
      label: 'Refresh Intel Feeds',
      description: 'Re-scan all intelligence sources',
      action: () => {
        setTabBadges({});
        setActiveTab('intelligence');
      },
      category: 'intelligence',
      hotkey: 'Ctrl+R',
    },
    {
      id: 'deep-scan',
      label: 'Deep Scan Selected Node',
      description: 'Run comprehensive analysis',
      action: () => {
        if (selectedNode) onDeepScan?.(selectedNode.id);
      },
      category: 'tools',
      hotkey: 'Ctrl+S',
    },
  ];

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K for command palette
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
      }

      // Ctrl+1, 2, 3, 4 for tab switching
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case '1':
            e.preventDefault();
            setActiveTab('battlefield');
            break;
          case '2':
            e.preventDefault();
            setActiveTab('intelligence');
            break;
          case '3':
            e.preventDefault();
            setActiveTab('offensive');
            break;
          case '4':
            e.preventDefault();
            setActiveTab('systems');
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const tabs: TabConfig[] = [
    {
      id: 'battlefield',
      label: 'Battlefield',
      icon: <MapPin size={18} />,
      component: BattlefieldTab,
    },
    {
      id: 'intelligence',
      label: 'Intelligence',
      icon: <Radar size={18} />,
      badge: tabBadges['intelligence'],
      component: IntelligenceTab,
    },
    {
      id: 'offensive',
      label: 'Offensive',
      icon: <Zap size={18} />,
      component: OffensiveTab,
    },
    {
      id: 'systems',
      label: 'Systems',
      icon: <Cpu size={18} />,
      component: SystemsTab,
    },
  ];

  return (
    <div className="w-full h-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex flex-col overflow-hidden">
      {/* Enhanced Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="border-b border-white/10 bg-gradient-to-r from-slate-900/80 via-slate-800/80 to-slate-900/80 backdrop-blur-md px-6 py-5 shadow-lg"
      >
        <div className="flex items-center justify-between">
          {/* Left Section */}
          <div className="flex items-center gap-4 flex-1">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="text-blue-400 flex-shrink-0"
            >
              <Radar size={28} />
            </motion.div>
            
            <div className="hidden sm:flex flex-col">
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Command Center
              </h1>
              <p className="text-xs text-white/50 font-mono">Enterprise Threat Intelligence Platform</p>
            </div>

            <motion.span
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-2 h-2 bg-green-400 rounded-full ml-2 flex-shrink-0"
            />
          </div>

          {/* Right Section - Controls */}
          <div className="flex items-center gap-2">
            {/* Command Palette Button */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setIsPaletteOpen(true)}
              className="px-3 py-2 rounded-lg bg-gradient-to-r from-blue-500/20 to-cyan-500/20 hover:from-blue-500/30 hover:to-cyan-500/30 border border-blue-400/30 hover:border-blue-400/50 text-blue-300 hover:text-blue-200 transition-all font-mono text-xs flex items-center gap-2 shadow-lg group"
              title="Open Command Palette (Ctrl+K)"
            >
              <Command size={16} />
              <span className="hidden lg:inline font-bold">Ctrl+K</span>
            </motion.button>

            {/* Notifications */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white transition-all group relative"
              title="Notifications"
            >
              <Bell size={18} />
              <motion.span
                animate={{ scale: [1, 1.3, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute top-1 right-1 w-2 h-2 bg-red-400 rounded-full"
              />
            </motion.button>

            {/* Settings */}
            <motion.button
              whileHover={{ scale: 1.05, rotate: 90 }}
              whileTap={{ scale: 0.95 }}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white/60 hover:text-white transition-all"
              title="Settings"
            >
              <Settings size={18} />
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* Enhanced Tabs Navigation */}
      <div className="border-b border-white/10 bg-gradient-to-r from-slate-900/50 via-slate-800/50 to-slate-900/50 backdrop-blur-md px-6 py-2 shadow-md">
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
          {tabs.map((tab, idx) => (
            <motion.button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05 }}
              whileHover={{ backgroundColor: activeTab !== tab.id ? 'rgba(255,255,255,0.05)' : undefined }}
              whileTap={{ scale: 0.98 }}
              className={`relative px-5 py-3 font-mono text-sm font-bold transition-all flex items-center gap-2 whitespace-nowrap group rounded-lg ${
                activeTab === tab.id
                  ? 'text-white bg-white/10 shadow-lg'
                  : 'text-white/50 hover:text-white/70'
              }`}
            >
              <span className={`transition-colors ${activeTab === tab.id ? 'text-blue-400' : 'text-white/40 group-hover:text-white/60'}`}>
                {tab.icon}
              </span>
              <span>{tab.label}</span>

              {/* Badge with Enhanced Styling */}
              {tab.badge && tab.badge > 0 && (
                <motion.span
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="ml-1 inline-flex items-center justify-center min-w-5 h-5 px-1.5 text-xs font-bold rounded-full bg-gradient-to-r from-red-500 to-red-600 text-white shadow-lg"
                >
                  {Math.min(tab.badge, 99)}
                </motion.span>
              )}

              {/* Active Indicator Line */}
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTabIndicator"
                  className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-cyan-400 to-blue-500 rounded-t-lg shadow-lg shadow-blue-500/50"
                  transition={{ duration: 0.3 }}
                />
              )}
            </motion.button>
          ))}
        </div>
      </div>

      {/* Tab Content Area */}
      <div className="flex-1 overflow-hidden bg-gradient-to-br from-slate-900/30 via-slate-800/20 to-slate-900/30">
        <AnimatePresence mode="wait">
          {tabs.map((tab) => {
            if (activeTab !== tab.id) return null;

            const TabComponent = tab.component;

            return (
              <motion.div
                key={tab.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="h-full w-full p-6 overflow-y-auto"
              >
                <TabComponent
                  onNodeSelect={handleNodeSelect}
                  selectedNode={selectedNode}
                  onDeepScan={onDeepScan}
                >
                  {activeTab === 'battlefield' && children}
                </TabComponent>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Command Palette */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        commands={commands}
      />

      {/* Glass Dossier */}
      <GlassDossier
        entity={selectedEntity}
        isOpen={isEntityDossierOpen}
        onClose={() => setIsEntityDossierOpen(false)}
        onDeepScan={onDeepScan}
      />
    </div>
  );
};
