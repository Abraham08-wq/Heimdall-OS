'use client';

import React, { useState, useRef, useCallback } from 'react';
import TeamShell from '@/components/Layout/TeamShell';
import { api } from '@/lib/api';
import {
  Target, Radio, Search, Globe, Server, FileSearch,
  AlertOctagon, Wifi, MapPin, Hash, ChevronDown,
  Loader2, Terminal, Crosshair, Activity, Shield
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
type ScanType = 'OSINT' | 'Port Scan' | 'DNS' | 'Whois' | 'Shodan';

interface ReconResult {
  target?: string;
  scan_type?: string;
  output?: string;
  asn?: string;
  org?: string;
  country?: string;
  city?: string;
  open_ports?: number[];
  cves?: string[];
  domains?: string[];
  raw?: string;
  timestamp?: string;
  status?: string;
}

interface OSINTResult {
  id?: string;
  type?: string;
  value?: string;
  source?: string;
  confidence?: number;
  [key: string]: any;
}

// ─── Scan Type Config ─────────────────────────────────────────────────────────
const SCAN_TYPES: { type: ScanType; icon: React.ReactNode; description: string }[] = [
  { type: 'OSINT', icon: <Globe size={14} />, description: 'Open-source intelligence gathering' },
  { type: 'Port Scan', icon: <Server size={14} />, description: 'TCP/UDP port discovery & fingerprinting' },
  { type: 'DNS', icon: <Hash size={14} />, description: 'DNS enumeration & zone transfer' },
  { type: 'Whois', icon: <FileSearch size={14} />, description: 'Domain registration & ownership lookup' },
  { type: 'Shodan', icon: <Search size={14} />, description: 'Internet-facing asset indexing' },
];

// ─── Radar Sweep Animation ────────────────────────────────────────────────────
function RadarSweep() {
  return (
    <div className="relative w-24 h-24 shrink-0">
      <svg viewBox="0 0 96 96" className="w-full h-full">
        <circle cx="48" cy="48" r="44" fill="none" stroke="#FF2D2015" strokeWidth="1" />
        <circle cx="48" cy="48" r="30" fill="none" stroke="#FF2D2020" strokeWidth="1" />
        <circle cx="48" cy="48" r="15" fill="none" stroke="#FF2D2030" strokeWidth="1" />
        <line x1="48" y1="48" x2="48" y2="4" stroke="#FF2D2040" strokeWidth="1" />
        <line x1="48" y1="48" x2="92" y2="48" stroke="#FF2D2040" strokeWidth="1" />
        <defs>
          <radialGradient id="sweep" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="rotate(-90)">
            <stop offset="0%" stopColor="#FF2D20" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#FF2D20" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path
          d="M48,48 L48,4 A44,44 0 0,1 92,48 Z"
          fill="url(#sweep)"
          style={{ transformOrigin: '48px 48px', animation: 'spin 2.5s linear infinite' }}
        />
        <circle cx="48" cy="48" r="3" fill="#FF2D20" style={{ filter: 'drop-shadow(0 0 4px #FF2D20)' }} />
      </svg>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

// ─── Enrichment Card ──────────────────────────────────────────────────────────
function EnrichCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-red-900/30 bg-red-950/10 p-3">
      <div className="flex items-center gap-1.5 text-red-700 mb-1.5">
        {icon}
        <span className="text-[9px] font-mono tracking-widest uppercase">{label}</span>
      </div>
      <div className="text-xs font-mono text-red-300">{value}</div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function ReconPage() {
  const [target, setTarget] = useState('');
  const [scanType, setScanType] = useState<ScanType>('OSINT');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ReconResult | null>(null);
  const [osintResults, setOsintResults] = useState<OSINTResult[]>([]);
  const [terminalLines, setTerminalLines] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  const appendLine = useCallback((line: string) => {
    setTerminalLines(prev => [...prev, line]);
    setTimeout(() => terminalRef.current?.scrollTo({ top: 99999, behavior: 'smooth' }), 50);
  }, []);

  const runScan = useCallback(async () => {
    if (!target.trim()) return;
    setScanning(true);
    setResult(null);
    setOsintResults([]);
    setError(null);
    setTerminalLines([
      `[${new Date().toISOString()}] OMNISCAN initialized`,
      `[*] Target: ${target}`,
      `[*] Scan type: ${scanType}`,
      `[*] Launching probe...`,
    ]);

    try {
      // POST to /api/v1/recon/probe
      const probeRes = await api.apiRequest<ReconResult>('/recon/probe', {
        method: 'POST',
        body: JSON.stringify({ target: target.trim(), scan_type: scanType }),
      });
      setResult(probeRes);
      appendLine(`[+] Probe complete — status: ${probeRes.status ?? 'ok'}`);
      if (probeRes.output) {
        probeRes.output.split('\n').forEach(l => appendLine(l));
      }
      if (probeRes.open_ports?.length) appendLine(`[+] Open ports: ${probeRes.open_ports.join(', ')}`);
      if (probeRes.cves?.length) appendLine(`[!] CVEs detected: ${probeRes.cves.join(', ')}`);

      // OSINT enrichment
      try {
        const osint = await api.apiRequest<OSINTResult[]>(`/recon/osint/search?query=${encodeURIComponent(target)}`);
        setOsintResults(osint ?? []);
        appendLine(`[+] OSINT enrichment: ${(osint ?? []).length} indicators`);
      } catch {
        appendLine(`[-] OSINT enrichment unavailable`);
      }

      appendLine(`[✓] Scan complete`);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      appendLine(`[ERROR] ${msg}`);
      appendLine(`[i] API unreachable — check connectivity`);
    } finally {
      setScanning(false);
    }
  }, [target, scanType, appendLine]);

  const selectedScanConfig = SCAN_TYPES.find(s => s.type === scanType)!;

  return (
    <TeamShell
      team="red"
      title="OMNISCAN RECONNAISSANCE ENGINE"
      subtitle="Passive & Active OSINT — Target profiling, port discovery, vulnerability correlation"
      badge={scanning ? 'SCANNING' : undefined}
    >
      <div className="p-6 space-y-6">
        {/* Input Panel */}
        <div className="rounded-xl border border-red-900/40 bg-gradient-to-br from-red-950/20 to-[#0D0000] p-5">
          <div className="flex items-center gap-3 mb-4">
            <Crosshair size={16} className="text-red-500" />
            <span className="text-[10px] font-mono text-red-700 tracking-widest uppercase">Target Acquisition</span>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            {/* Target Input */}
            <div className="flex-1 relative">
              <Target size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-red-700" />
              <input
                type="text"
                value={target}
                onChange={e => setTarget(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !scanning && runScan()}
                placeholder="IP, domain, CIDR, or ASN…"
                className="w-full bg-red-950/20 border border-red-900/40 rounded-lg pl-9 pr-4 py-2.5 text-sm font-mono text-red-200 placeholder-red-900 focus:outline-none focus:border-red-600/60 focus:ring-1 focus:ring-red-600/20 transition-all"
              />
            </div>

            {/* Scan Type Selector */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(o => !o)}
                className="flex items-center gap-2 bg-red-950/30 border border-red-900/40 rounded-lg px-4 py-2.5 text-sm font-mono text-red-400 hover:border-red-700/60 transition-all min-w-[160px] justify-between"
              >
                <span className="flex items-center gap-2">
                  {selectedScanConfig.icon}
                  {scanType}
                </span>
                <ChevronDown size={14} className={`transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              {dropdownOpen && (
                <div className="absolute z-50 mt-1 w-64 rounded-xl border border-red-900/40 bg-[#180000] shadow-2xl overflow-hidden">
                  {SCAN_TYPES.map(({ type, icon, description }) => (
                    <button
                      key={type}
                      onClick={() => { setScanType(type); setDropdownOpen(false); }}
                      className={`w-full flex items-start gap-3 px-4 py-3 hover:bg-red-950/30 transition-colors text-left ${scanType === type ? 'bg-red-950/40' : ''}`}
                    >
                      <span className="mt-0.5 text-red-500">{icon}</span>
                      <div>
                        <p className="text-xs font-mono text-red-300 font-semibold">{type}</p>
                        <p className="text-[10px] text-red-800 mt-0.5">{description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Launch Button */}
            <button
              onClick={runScan}
              disabled={scanning || !target.trim()}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg font-mono text-sm font-bold bg-red-700 hover:bg-red-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              style={{ boxShadow: scanning ? '0 0 20px rgba(255,45,32,0.4)' : undefined }}
            >
              {scanning ? <Loader2 size={15} className="animate-spin" /> : <Radio size={15} />}
              {scanning ? 'SCANNING' : 'LAUNCH'}
            </button>
          </div>
        </div>

        {/* Main Results Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Terminal Output */}
          <div className="lg:col-span-3 rounded-xl border border-red-900/30 bg-[#0a0000] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-red-950/50 bg-[#120000]">
              <div className="flex items-center gap-2">
                <Terminal size={13} className="text-red-600" />
                <span className="text-[10px] font-mono text-red-700 tracking-widest">SCAN OUTPUT</span>
              </div>
              {scanning && <RadarSweep />}
              {!scanning && terminalLines.length > 0 && (
                <Activity size={14} className="text-red-900" />
              )}
            </div>
            <div
              ref={terminalRef}
              className="flex-1 p-4 font-mono text-[11px] text-green-400 leading-5 overflow-y-auto min-h-64 max-h-96 scrollbar-thin"
              style={{ background: '#050000' }}
            >
              {terminalLines.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 gap-3 opacity-40">
                  <Shield size={28} className="text-red-900" />
                  <p className="text-red-900 text-xs tracking-widest">AWAITING TARGET</p>
                </div>
              ) : (
                terminalLines.map((line, i) => (
                  <div key={i} className={`${line.startsWith('[ERROR]') ? 'text-red-500' : line.startsWith('[!]') ? 'text-yellow-500' : line.startsWith('[+]') || line.startsWith('[✓]') ? 'text-green-400' : 'text-green-700'}`}>
                    {line || <br />}
                  </div>
                ))
              )}
              {scanning && <span className="inline-block w-2 h-3 bg-green-400 ml-1 animate-pulse" />}
            </div>
          </div>

          {/* OSINT Enrichment Cards */}
          <div className="lg:col-span-2 space-y-3">
            <div className="rounded-xl border border-red-900/30 bg-[#0D0000] p-4">
              <h3 className="text-[10px] font-mono text-red-700 tracking-widest mb-3 uppercase flex items-center gap-2">
                <Globe size={11} /> OSINT Enrichment
              </h3>
              {!result && !scanning ? (
                <p className="text-red-900 text-[11px] font-mono text-center py-6">Run a scan to populate intelligence</p>
              ) : scanning ? (
                <div className="space-y-2">{[1,2,3,4].map(i => (
                  <div key={i} className="h-12 bg-red-950/20 rounded-lg animate-pulse" />
                ))}</div>
              ) : (
                <div className="space-y-2">
                  <EnrichCard icon={<Hash size={11} />} label="ASN" value={result?.asn ?? '—'} />
                  <EnrichCard icon={<Globe size={11} />} label="Organization" value={result?.org ?? '—'} />
                  <EnrichCard icon={<MapPin size={11} />} label="Geolocation" value={result?.city && result?.country ? `${result.city}, ${result.country}` : '—'} />
                  <EnrichCard
                    icon={<Wifi size={11} />}
                    label="Open Ports"
                    value={result?.open_ports?.length ? result.open_ports.slice(0, 8).join(' · ') + (result.open_ports.length > 8 ? ' …' : '') : '—'}
                  />
                  <EnrichCard
                    icon={<AlertOctagon size={11} />}
                    label="CVEs"
                    value={result?.cves?.length ? (
                      <div className="space-y-0.5">
                        {result.cves.slice(0, 4).map(cve => (
                          <div key={cve} className="text-red-400 text-[10px]">{cve}</div>
                        ))}
                        {result.cves.length > 4 && <div className="text-red-800 text-[10px]">+{result.cves.length - 4} more</div>}
                      </div>
                    ) : '—'}
                  />
                </div>
              )}
            </div>

            {/* OSINT indicators */}
            {osintResults.length > 0 && (
              <div className="rounded-xl border border-red-900/30 bg-[#0D0000] p-4">
                <h3 className="text-[10px] font-mono text-red-700 tracking-widest mb-3 uppercase">
                  Indicators ({osintResults.length})
                </h3>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {osintResults.slice(0, 20).map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-[10px] font-mono py-1 border-b border-red-950/30">
                      <span className="text-red-800">{r.type ?? 'ioc'}</span>
                      <span className="text-red-400 flex-1 truncate">{r.value ?? JSON.stringify(r).slice(0, 40)}</span>
                      {r.confidence !== undefined && (
                        <span className="text-red-700">{r.confidence}%</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
            <AlertOctagon size={14} className="text-red-500 shrink-0" />
            <p className="text-xs font-mono text-red-400">{error}</p>
          </div>
        )}
      </div>
    </TeamShell>
  );
}
