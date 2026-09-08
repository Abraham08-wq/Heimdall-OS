/**
 * WAR ROOM COMMAND DECK
 * =====================
 * 4-Quadrant expert interface for boardroom and war room decision making
 * 
 * Quadrant 1: Global Risk Heatmap & Financial VaR
 * Quadrant 2: Neural De-Masking Identity Graph
 * Quadrant 3: Secret Archive Breach Terminal
 * Quadrant 4: Kinetic "Battlefield" Map (Neo4j Pulse)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LineChart, Line, AreaChart, Area, ResponsiveContainer, XAxis, YAxis } from 'recharts';

import { AlertTriangle, Shield, Zap, Radio, TrendingUp, Users, Lock, Globe, Play, Pause, Send } from 'lucide-react';
import { api } from '@/lib/api';

interface RiskMetric {
  country: string;
  threatLevel: number;
  var95: number;
  var99: number;
  riskScore: number;
}

interface ThreatActor {
  id: string;
  description: string;
  severity: number;
  source: string;
  iocs: { type: string; value: string }[];
}

interface BreachRecord {
  datasetId: string;
  name: string;
  recordCount: number;
  affectedOrgs: string[];
  discoveredDate: string;
}

interface BattlefieldAsset {
  id: string;
  type: string;
  status: 'secure' | 'exposed' | 'compromised' | 'critical';
  location: { x: number; y: number };
  value: number;
}

interface DossierData {
  actor_id: string;
  confidence: number;
  observations: number;
  enriched_matches: number;
}

export const WarRoomCommandDeck: React.FC = () => {
  const [riskData, setRiskData] = useState<RiskMetric[]>([]);
  const [threatActors, setThreatActors] = useState<ThreatActor[]>([]);
  const [breachData, setBreachData] = useState<BreachRecord[]>([]);
  const [battlefieldAssets, setBattlefieldAssets] = useState<BattlefieldAsset[]>([]);
  const [selectedQuadrant, setSelectedQuadrant] = useState<number | null>(null);
  const [systemStatus, setSystemStatus] = useState('INITIALIZING');
  const [threatLevel, setThreatLevel] = useState<'critical' | 'high' | 'medium' | 'low'>('medium');
  
  // New state for attribution and containment
  const [attributionIndicators, setAttributionIndicators] = useState<string[]>([]);
  const [attributionInput, setAttributionInput] = useState('');
  const [dossierData, setDossierData] = useState<DossierData | null>(null);
  const [isCorrelating, setIsCorrelating] = useState(false);
  const [containmentHost, setContainmentHost] = useState('');
  const [containmentSeverity, setContainmentSeverity] = useState(9);
  const [isIsolating, setIsIsolating] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error' | 'info', text: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setSystemStatus('FETCHING DATA');
      try {
        const [snapshotData, threatsData] = await Promise.all([
          api.getRadarSnapshot(),
          api.getActiveThreats()
        ]);

        if (!snapshotData || !threatsData) {
          throw new Error('Failed to fetch data from one or more endpoints');
        }

        // Process snapshot data for Quadrants 1, 3, 4
        const riskMetrics = (Object.entries(snapshotData.threat_map) as [string, number][]).map(([country, threatCount]) => ({
          country,
          threatLevel: Math.min(10, Math.ceil(threatCount / 10)),
          var95: threatCount * 1000000,
          var99: threatCount * 1500000,
          riskScore: Math.min(100, threatCount * 10),
        }));
        setRiskData(riskMetrics);

        const breaches = snapshotData.breaches.map((breach: any) => ({
          datasetId: breach.dataset_id,
          name: breach.name,
          recordCount: breach.record_count,
          affectedOrgs: breach.affected_organizations,
          discoveredDate: breach.date_discovered,
        }));
        setBreachData(breaches);

        const assets = snapshotData.assets.map((asset: any) => ({
          id: asset.asset_id,
          type: asset.asset_type,
          status: asset.is_exposed ? (asset.vulnerabilities.some((v: any) => v.severity === 'critical') ? 'critical' : 'exposed') : 'secure',
          // MOCK LOCATION: API does not provide location data for assets.
          location: { x: Math.random() * 80 + 10, y: Math.random() * 80 + 10 },
          value: asset.exposure_severity * 10,
        }));
        setBattlefieldAssets(assets);

        // Process threats data for Quadrant 2
        const activeThreats = threatsData.active_threats.map((event: any) => ({
          id: event.event_id,
          description: event.description,
          severity: event.severity,
          source: event.source,
          iocs: event.iocs.map((ioc: any) => ({ type: ioc.ioc_type, value: ioc.ioc_value })),
        }));
        setThreatActors(activeThreats);
        
        setSystemStatus('OPTIMAL');
        const overallThreat = Math.max(...riskMetrics.map(r => r.threatLevel), 0);
        if (overallThreat >= 8) setThreatLevel('critical');
        else if (overallThreat >= 6) setThreatLevel('high');
        else if (overallThreat >= 4) setThreatLevel('medium');
        else setThreatLevel('low');

      } catch (error) {
        console.error('Error fetching war room data:', error);
        setSystemStatus('ERROR');
        setFeedbackMessage({ type: 'error', text: 'Failed to load critical intelligence data.' });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
        // Refresh every 60 seconds. Disable polling in non-interactive environments by env var.
        import.meta && typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'production' && console.debug && console.debug('WarRoom polling active');
        const pollingEnabled = typeof window !== 'undefined' ? true : false;
        const interval = pollingEnabled ? window.setInterval(fetchData, 60000) : undefined; // Refresh every 60 seconds

    return () => {
      if (interval) window.clearInterval(interval);
    };
  }, []);

  // API Integration: Attribution Engine
  const correlateIndicators = useCallback(async () => {
    if (attributionIndicators.length === 0) {
      setFeedbackMessage({ type: 'error', text: 'Add at least one indicator' });
      return;
    }
    
    setIsCorrelating(true);
    try {
      const data = await api.correlateWarRoomIndicators(attributionIndicators);
      setDossierData(data);
      setFeedbackMessage({ type: 'success', text: `Actor ${data.actor_id} (${(data.confidence * 100).toFixed(1)}% confidence)` });
    } catch (error) {
      setFeedbackMessage({ type: 'error', text: `Correlation failed: ${error}` });
    } finally {
      setIsCorrelating(false);
    }
  }, [attributionIndicators]);

  const addIndicator = useCallback(() => {
    if (attributionInput.trim()) {
      setAttributionIndicators([...attributionIndicators, attributionInput]);
      setAttributionInput('');
    }
  }, [attributionInput, attributionIndicators]);

  const removeIndicator = useCallback((index: number) => {
    setAttributionIndicators(attributionIndicators.filter((_, i) => i !== index));
  }, [attributionIndicators]);

  // API Integration: Containment Service
  const isolateHost = useCallback(async () => {
    if (!containmentHost.trim()) {
      setFeedbackMessage({ type: 'error', text: 'Enter a host identifier' });
      return;
    }
    
    if (containmentSeverity < 9) {
      setFeedbackMessage({ type: 'error', text: 'Severity must be P1 (≥9) for isolation' });
      return;
    }
    
    setIsIsolating(true);
    try {
      const data = await api.isolateWarRoomHost(containmentHost, containmentSeverity);
      setFeedbackMessage({ type: 'success', text: `Isolation ${data.outcome}: ${containmentHost}` });
      setThreatLevel('critical');
    } catch (error) {
      setFeedbackMessage({ type: 'error', text: `Isolation failed: ${error}` });
    } finally {
      setIsIsolating(false);
    }
  }, [containmentHost, containmentSeverity]);

  return (
    <div className="w-full h-screen bg-black/95 text-white overflow-hidden">
      {/* SYSTEM STATUS BAR */}
      <div className="h-16 bg-gradient-to-r from-blue-900/50 to-purple-900/50 border-b border-cyan-500/30 flex items-center justify-between px-8">
        <div className="flex items-center gap-4">
          <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
          <span className="font-mono text-sm">SOVEREIGN COMMAND DECK</span>
          <span className="text-xs text-gray-400">|</span>
          <span className="text-xs text-gray-400">2026-03-17 00:00:00 UTC</span>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">System Status:</span>
            <span className={`text-sm font-bold ${
              systemStatus === 'OPTIMAL' ? 'text-green-400' : 'text-red-400'
            }`}>
              {systemStatus}
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Threat Level:</span>
            <span className={`text-sm font-bold px-3 py-1 rounded border ${
              threatLevel === 'critical' ? 'border-red-500 bg-red-500/10 text-red-400' :
              threatLevel === 'high' ? 'border-orange-500 bg-orange-500/10 text-orange-400' :
              threatLevel === 'medium' ? 'border-yellow-500 bg-yellow-500/10 text-yellow-400' :
              'border-green-500 bg-green-500/10 text-green-400'
            }`}>
              {threatLevel.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* 4-QUADRANT LAYOUT */}
      <div className="grid grid-cols-2 gap-3 h-[calc(100%-4rem)] p-3 bg-black/90">
        
        {/* QUADRANT 1: GLOBAL RISK HEATMAP & FINANCIAL VaR */}
        <motion.div
          className="bg-gradient-to-br from-blue-900/20 to-blue-900/5 border border-blue-500/30 rounded-lg overflow-hidden cursor-pointer hover:border-blue-400/50 transition-all"
          onClick={() => setSelectedQuadrant(selectedQuadrant === 1 ? null : 1)}
          whileHover={{ borderColor: 'rgba(96, 165, 250, 0.8)' }}
        >
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-blue-950/40 border-b border-blue-500/20 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                <h2 className="font-mono text-sm text-blue-300">GLOBAL RISK HEATMAP</h2>
              </div>
              <span className="text-xs text-blue-400">VaR @ 99% Confidence</span>
            </div>

            {/* Risk Heatmap Data */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {isLoading ? <div className="text-center p-8 text-gray-400">Loading...</div> : riskData.map((risk, idx) => (
                <motion.div
                  key={idx}
                  className="bg-black/50 border border-blue-500/20 rounded p-3"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs text-blue-300">{risk.country}</span>
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      risk.threatLevel >= 8 ? 'bg-red-500/20 text-red-400' :
                      risk.threatLevel >= 6 ? 'bg-orange-500/20 text-orange-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {risk.threatLevel}/10
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-gray-400">VaR 95%:</span>
                      <span className="text-cyan-400 font-mono ml-1">
                        ${(risk.var95 / 1000000).toFixed(0)}M
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400">VaR 99%:</span>
                      <span className="text-red-400 font-mono ml-1">
                        ${(risk.var99 / 1000000).toFixed(0)}M
                      </span>
                    </div>
                  </div>
                  
                  {/* Risk Score Bar */}
                  <div className="mt-2 h-1.5 bg-black/50 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-yellow-500 to-red-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${risk.riskScore}%` }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* QUADRANT 2: AUTONOMOUS SOC THREATS */}
        <motion.div
          className="bg-gradient-to-br from-purple-900/20 to-purple-900/5 border border-purple-500/30 rounded-lg overflow-hidden cursor-pointer hover:border-purple-400/50 transition-all"
          onClick={() => setSelectedQuadrant(selectedQuadrant === 2 ? null : 2)}
          whileHover={{ borderColor: 'rgba(168, 85, 247, 0.8)' }}
        >
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-purple-950/40 border-b border-purple-500/20 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                <h2 className="font-mono text-sm text-purple-300">AUTONOMOUS SOC THREATS</h2>
              </div>
              <span className="text-xs text-purple-400">{threatActors.length} Active Events</span>
            </div>

            {/* Threat Actor Network */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {isLoading ? <div className="text-center p-8 text-gray-400">Loading...</div> : threatActors.map((actor, idx) => (
                <motion.div
                  key={idx}
                  className="bg-black/50 border border-purple-500/20 rounded p-3 hover:border-purple-400/50 transition-all"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-mono text-xs text-purple-300">{actor.description}</p>
                      <p className="text-xs text-gray-400 mt-1">Source: {actor.source}</p>
                    </div>
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      actor.severity >= 8 ? 'bg-red-500/20 text-red-400' :
                      'bg-orange-500/20 text-orange-400'
                    }`}>
                      SEV: {actor.severity}/10
                    </span>
                  </div>
                  
                  <div className="text-xs text-gray-400 mb-2">
                    IOCs: {actor.iocs.map(ioc => ioc.value).join(', ')}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* QUADRANT 3: SECRET ARCHIVE BREACH TERMINAL */}
        <motion.div
          className="bg-gradient-to-br from-orange-900/20 to-orange-900/5 border border-orange-500/30 rounded-lg overflow-hidden cursor-pointer hover:border-orange-400/50 transition-all"
          onClick={() => setSelectedQuadrant(selectedQuadrant === 3 ? null : 3)}
          whileHover={{ borderColor: 'rgba(249, 115, 22, 0.8)' }}
        >
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-orange-950/40 border-b border-orange-500/20 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-orange-400" />
                <h2 className="font-mono text-sm text-orange-300">SECRET ARCHIVE BREACH DATA</h2>
              </div>
              <span className="text-xs text-orange-400">{breachData.length} Active Breaches</span>
            </div>

            {/* Breach Records */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {isLoading ? <div className="text-center p-8 text-gray-400">Loading...</div> : breachData.map((breach, idx) => (
                <motion.div
                  key={idx}
                  className="bg-black/50 border border-orange-500/20 rounded p-3 hover:border-orange-400/50 transition-all"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-mono text-xs text-orange-300">{breach.name}</p>
                      <p className="text-xs text-gray-400 mt-1">Discovered: {breach.discoveredDate}</p>
                    </div>
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                  </div>
                  
                  <div className="text-xs text-gray-400 mb-2">
                    Records: <span className="text-orange-400 font-mono">{(breach.recordCount / 1000000).toFixed(0)}M</span>
                  </div>
                  
                  <div className="text-xs text-gray-400">
                    Organizations: {breach.affectedOrgs.join(', ')}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* QUADRANT 4: KINETIC BATTLEFIELD MAP */}
        <motion.div
          className="bg-gradient-to-br from-green-900/20 to-green-900/5 border border-green-500/30 rounded-lg overflow-hidden cursor-pointer hover:border-green-400/50 transition-all"
          onClick={() => setSelectedQuadrant(selectedQuadrant === 4 ? null : 4)}
          whileHover={{ borderColor: 'rgba(34, 197, 94, 0.8)' }}
        >
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="bg-green-950/40 border-b border-green-500/20 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-green-400" />
                <h2 className="font-mono text-sm text-green-300">KINETIC BATTLEFIELD MAP</h2>
              </div>
              <span className="text-xs text-green-400">{battlefieldAssets.length} Assets</span>
            </div>

            {/* Asset Map Canvas */}
            <div className="flex-1 bg-gradient-to-br from-black to-green-950/10 relative overflow-hidden">
              <svg className="w-full h-full opacity-20">
                <defs>
                  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5"/>
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" className="text-green-500"/>
              </svg>

              {/* Assets on map */}
              <div className="absolute inset-0">
                {isLoading ? <div className="text-center p-8 text-gray-400">Loading...</div> : battlefieldAssets.map((asset) => (
                  <motion.div
                    key={asset.id}
                    className={`absolute w-3 h-3 rounded-full border-2 ${
                      asset.status === 'secure' ? 'bg-green-500/50 border-green-400' :
                      asset.status === 'exposed' ? 'bg-yellow-500/50 border-yellow-400' :
                      asset.status === 'compromised' ? 'bg-orange-500/50 border-orange-400' :
                      'bg-red-500/50 border-red-400'
                    }`}
                    style={{
                      left: `${asset.location.x}%`,
                      top: `${asset.location.y}%`,
                      transform: 'translate(-50%, -50%)',
                    }}
                    animate={{
                      scale: asset.status === 'critical' ? [1, 1.3, 1] : 1,
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                    }}
                    title={`${asset.type} - ${asset.status}`}
                  >
                    {asset.status === 'critical' && (
                      <motion.div
                        className="absolute inset-0 rounded-full border border-red-400"
                        animate={{ scale: [1, 1.5], opacity: [1, 0] }}
                        transition={{ duration: 1, repeat: Infinity }}
                      />
                    )}
                  </motion.div>
                ))}
              </div>

              {/* Asset legend */}
              <div className="absolute bottom-2 left-2 text-xs space-y-1 text-gray-400">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500/50 border border-green-400" />
                  <span>Secure</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-yellow-500/50 border border-yellow-400" />
                  <span>Exposed</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-orange-500/50 border border-orange-400" />
                  <span>Compromised</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-red-500/50 border border-red-400" />
                  <span>Critical</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* ATTRIBUTION & CONTAINMENT CONTROL PANEL (Floating Glassmorphism) */}
      <AnimatePresence>
        {selectedQuadrant === null && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 right-6 w-96 bg-white/5 backdrop-blur-xl border border-white/10 rounded-xl p-6 shadow-2xl"
          >
            {/* Feedback Message */}
            {feedbackMessage && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className={`mb-4 p-3 rounded-lg text-sm font-mono ${
                  feedbackMessage.type === 'success' ? 'bg-green-500/10 border border-green-500/30 text-green-300' :
                  feedbackMessage.type === 'error' ? 'bg-red-500/10 border border-red-500/30 text-red-300' :
                  'bg-blue-500/10 border border-blue-500/30 text-blue-300'
                }`}
              >
                {feedbackMessage.text}
              </motion.div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 mb-4 border-b border-white/10">
              <button
                onClick={() => setSelectedQuadrant(1)}
                className="flex-1 px-3 py-2 text-xs font-mono text-cyan-400 hover:text-cyan-300 border-b-2 border-cyan-500/50"
              >
                ATTRIBUTION
              </button>
              <button
                onClick={() => setSelectedQuadrant(2)}
                className="flex-1 px-3 py-2 text-xs font-mono text-purple-400 hover:text-purple-300"
              >
                CONTAINMENT
              </button>
            </div>

            {/* ATTRIBUTION TAB */}
            <div className="space-y-3">
              <div>
                <label className="text-xs font-mono text-gray-400 mb-1 block">Threat Indicators</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={attributionInput}
                    onChange={(e) => setAttributionInput(e.target.value)}
                    placeholder="IP, email, domain..."
                    className="flex-1 bg-black/50 border border-white/10 rounded px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-cyan-500/50"
                  />
                  <button
                    onClick={addIndicator}
                    className="px-3 py-2 bg-cyan-500/10 border border-cyan-500/30 rounded hover:bg-cyan-500/20 text-cyan-400 text-xs"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Added Indicators */}
              {attributionIndicators.length > 0 && (
                <div className="space-y-1">
                  {attributionIndicators.map((ind, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-black/50 border border-white/10 rounded px-3 py-2 text-xs">
                      <span className="font-mono text-cyan-300">{ind}</span>
                      <button
                        onClick={() => removeIndicator(idx)}
                        className="text-gray-500 hover:text-red-400"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Correlate Button */}
              <button
                onClick={correlateIndicators}
                disabled={isCorrelating || attributionIndicators.length === 0}
                className="w-full px-4 py-2 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 rounded font-mono text-xs text-cyan-300 hover:border-cyan-400/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isCorrelating ? (
                  <>
                    <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity }} className="w-3 h-3 border-2 border-cyan-500/50 border-t-cyan-400 rounded-full" />
                    Correlating...
                  </>
                ) : (
                  <>
                    <Zap className="w-3 h-3" />
                    Correlate Threat Actors
                  </>
                )}
              </button>

              {/* Dossier Result */}
              {dossierData && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="bg-black/50 border border-cyan-500/20 rounded p-3 text-xs space-y-1"
                >
                  <div className="flex justify-between">
                    <span className="text-gray-400">Actor ID:</span>
                    <span className="font-mono text-cyan-300">{dossierData.actor_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Confidence:</span>
                    <span className="font-mono text-cyan-300">{(dossierData.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Observations:</span>
                    <span className="font-mono text-cyan-300">{dossierData.observations}</span>
                  </div>
                </motion.div>
              )}
            </div>

            {/* CONTAINMENT TAB (Hidden by default, shown on click) */}
            {selectedQuadrant === 2 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-3"
              >
                <div>
                  <label className="text-xs font-mono text-gray-400 mb-1 block">Host Identifier</label>
                  <input
                    type="text"
                    value={containmentHost}
                    onChange={(e) => setContainmentHost(e.target.value)}
                    placeholder="IP or hostname..."
                    className="w-full bg-black/50 border border-white/10 rounded px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-purple-500/50"
                  />
                </div>

                <div>
                  <label className="text-xs font-mono text-gray-400 mb-1 block">Severity (P1=9-10)</label>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    value={containmentSeverity}
                    onChange={(e) => setContainmentSeverity(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-xs text-gray-400 mt-1">Level: {containmentSeverity}</div>
                </div>

                <button
                  onClick={isolateHost}
                  disabled={isIsolating || containmentSeverity < 9}
                  className="w-full px-4 py-2 bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-500/30 rounded font-mono text-xs text-purple-300 hover:border-purple-400/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isIsolating ? (
                    <>
                      <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity }} className="w-3 h-3 border-2 border-purple-500/50 border-t-purple-400 rounded-full" />
                      Isolating...
                    </>
                  ) : (
                    <>
                      <Shield className="w-3 h-3" />
                      Isolate Host
                    </>
                  )}
                </button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default WarRoomCommandDeck;
