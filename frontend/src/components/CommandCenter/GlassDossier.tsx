import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, AlertTriangle, Shield, Zap, Download, Share2, Copy } from 'lucide-react';

export interface EntityData {
  id: string;
  name: string;
  type: string;
  riskLevel: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  attributes: Record<string, string | number | boolean>;
  threatIndicators?: Array<{
    indicator: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    description: string;
  }>;
  metadata?: Record<string, any>;
}

interface GlassDossierProps {
  entity: EntityData | null;
  isOpen: boolean;
  onClose: () => void;
  onDeepScan?: (entityId: string) => void;
}

const riskColors = {
  critical: 'from-red-500 to-red-600',
  high: 'from-orange-500 to-orange-600',
  medium: 'from-yellow-500 to-yellow-600',
  low: 'from-green-500 to-green-600',
};

const riskLabels = {
  critical: '🔴 CRITICAL',
  high: '🟠 HIGH',
  medium: '🟡 MEDIUM',
  low: '🟢 LOW',
};

export const GlassDossier: React.FC<GlassDossierProps> = ({
  entity,
  isOpen,
  onClose,
  onDeepScan,
}) => {

  const [isScanning, setIsScanning] = useState(false);

  const handleDeepScan = async () => {
    if (!entity || !onDeepScan) return;
    setIsScanning(true);
    try {
      await onDeepScan(entity.id);
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && entity && (
        <>
          {/* Enhanced Backdrop with Blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-black/40 backdrop-blur-md"
          />

          {/* Enhanced Glass Dossier Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8, y: 50, x: 100 }}
            animate={{ opacity: 1, scale: 1, y: 0, x: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 50, x: 100 }}
            transition={{ duration: 0.35, type: 'spring', damping: 25 }}
            className="fixed right-6 top-1/2 z-40 w-[32rem] -translate-y-1/2 rounded-2xl bg-white/8 backdrop-blur-xl border border-white/20 shadow-2xl overflow-hidden group hover:border-white/30 transition-colors"
          >
            {/* Enhanced Header with Gradient */}
            <div
              className={`bg-gradient-to-br ${
                riskColors[entity.riskLevel]
              } p-6 relative overflow-hidden before:absolute before:inset-0 before:bg-black/20`}
            >
              {/* Animated Gradient Background */}
              <motion.div
                animate={{ 
                  background: [
                    'radial-gradient(circle at 0% 0%, rgba(255,255,255,0.1) 0%, transparent 50%)',
                    'radial-gradient(circle at 100% 100%, rgba(255,255,255,0.1) 0%, transparent 50%)',
                    'radial-gradient(circle at 0% 0%, rgba(255,255,255,0.1) 0%, transparent 50%)',
                  ]
                }}
                transition={{ duration: 4, repeat: Infinity }}
                className="absolute inset-0 opacity-30"
              />

              <div className="relative z-10">
                {/* Header Top Row */}
                <div className="flex items-start justify-between mb-4">
                  <motion.span
                    animate={{ opacity: [0.6, 1, 0.6] }}
                    transition={{ duration: 2, repeat: Infinity }}
                    className="text-xs font-mono font-bold text-white/90 uppercase tracking-widest"
                  >
                    ◆ Entity Dossier
                  </motion.span>
                  <motion.button
                    whileHover={{ scale: 1.1, rotate: 90 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={onClose}
                    className="text-white/70 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10"
                  >
                    <X size={20} />
                  </motion.button>
                </div>

                {/* Entity Title */}
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                  className="mb-4"
                >
                  <h2 className="text-3xl font-black text-white break-words leading-tight tracking-tight">
                    {entity.name}
                  </h2>
                  <motion.p 
                    className="text-white/80 text-sm font-mono mt-2 bg-white/10 w-fit px-3 py-1 rounded-lg mt-2"
                  >
                    {entity.type}
                  </motion.p>
                </motion.div>

                {/* Risk Level Badge */}
                <div className="flex items-center gap-3">
                  <motion.span
                    animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className={`inline-block w-4 h-4 rounded-full shadow-lg ${
                      entity.riskLevel === 'critical' ? 'bg-red-300 shadow-red-500/50' :
                      entity.riskLevel === 'high' ? 'bg-orange-300 shadow-orange-500/50' :
                      entity.riskLevel === 'medium' ? 'bg-yellow-300 shadow-yellow-500/50' :
                      'bg-green-300 shadow-green-500/50'
                    }`}
                  />
                  <span className="text-white font-mono font-bold text-sm uppercase tracking-widest">
                    {riskLabels[entity.riskLevel]}
                  </span>
                </div>
              </div>
            </div>

            {/* Enhanced Content Area */}
            <div className="p-6 space-y-5 max-h-[60vh] overflow-y-auto custom-scrollbar">
              {/* Description */}
              {entity.description && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 }}
                  className="p-4 rounded-xl bg-gradient-to-br from-white/10 to-white/5 border border-white/10 backdrop-blur"
                >
                  <p className="text-white/80 font-mono text-sm leading-relaxed">
                    {entity.description}
                  </p>
                </motion.div>
              )}

              {/* Threat Indicators */}
              {entity.threatIndicators && entity.threatIndicators.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <div className="flex items-center gap-2 mb-4">
                    <motion.div animate={{ rotate: [0, 360] }} transition={{ duration: 3, repeat: Infinity }}>
                      <AlertTriangle size={18} className="text-red-400" />
                    </motion.div>
                    <h3 className="text-white font-mono font-bold text-sm uppercase tracking-widest">
                      Threat Indicators
                    </h3>
                    <span className="ml-auto text-xs bg-red-500/20 text-red-300 px-2 py-1 rounded-lg font-bold">
                      {entity.threatIndicators.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {entity.threatIndicators.map((threat, idx) => (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, x: -15 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.25 + idx * 0.05 }}
                        whileHover={{ x: 5 }}
                        className="p-3 rounded-lg bg-gradient-to-r from-red-500/20 to-red-500/5 border border-red-400/30 cursor-pointer hover:border-red-400/50 transition-colors"
                      >
                        <div className="flex items-start gap-3">
                          <motion.span
                            animate={{ scale: [1, 1.3, 1] }}
                            transition={{ duration: 1.2, repeat: Infinity, delay: idx * 0.1 }}
                            className="text-lg font-bold text-red-400 mt-0"
                          >
                            ●
                          </motion.span>
                          <div className="flex-1 min-w-0">
                            <p className="text-white/95 font-mono text-xs font-bold uppercase tracking-wider">
                              {threat.indicator}
                            </p>
                            <p className="text-white/60 font-mono text-xs mt-1 leading-relaxed">
                              {threat.description}
                            </p>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Attributes Grid */}
              {Object.keys(entity.attributes).length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <h3 className="text-white font-mono font-bold text-sm mb-4 uppercase tracking-widest">
                    Attributes & Metadata
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(entity.attributes).slice(0, 6).map(([key, value], idx) => (
                      <motion.div
                        key={key}
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 + idx * 0.04 }}
                        className="p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer group"
                      >
                        <p className="text-white/50 font-mono text-xs uppercase tracking-widest group-hover:text-white/70 transition-colors">
                          {key}
                        </p>
                        <p className="text-white/90 font-mono font-bold text-xs mt-1 truncate group-hover:text-white transition-colors">
                          {String(value).substring(0, 20)}
                        </p>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}
            </div>

            {/* Enhanced Action Buttons */}
            <div className="p-6 border-t border-white/10 bg-gradient-to-b from-white/5 to-transparent">
              <div className="grid grid-cols-3 gap-2 mb-3">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title="Copy entity ID"
                  className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 hover:text-white transition-all"
                >
                  <Copy size={16} />
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title="Share dossier"
                  className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 hover:text-white transition-all"
                >
                  <Share2 size={16} />
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title="Export dossier"
                  className="p-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 hover:text-white transition-all"
                >
                  <Download size={16} />
                </motion.button>
              </div>

              {/* Primary Action Buttons */}
              <div className="flex gap-2">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleDeepScan}
                  disabled={isScanning}
                  className="flex-1 px-4 py-3 rounded-lg bg-gradient-to-r from-blue-500/30 to-blue-600/30 hover:from-blue-500/50 hover:to-blue-600/50 disabled:opacity-50 disabled:cursor-not-allowed border border-blue-400/40 text-blue-300 hover:text-blue-100 font-mono text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg"
                >
                  <motion.span
                    animate={isScanning ? { rotate: 360 } : {}}
                    transition={{ duration: 1, repeat: isScanning ? Infinity : 0, ease: 'linear' }}
                  >
                    <Zap size={16} />
                  </motion.span>
                  {isScanning ? 'SCANNING...' : 'DEEP SCAN'}
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onClose}
                  className="flex-1 px-4 py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/20 hover:border-white/40 text-white/70 hover:text-white font-mono text-xs font-bold transition-all"
                >
                  CLOSE
                </motion.button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
;
