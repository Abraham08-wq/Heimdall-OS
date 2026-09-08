'use client';
import { useEffect, useState } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import { Shield, AlertTriangle, Activity, TrendingDown, Layers, RefreshCw, Radio } from 'lucide-react';
import { apiRequest } from '@/lib/api';

interface Threat { id?: string; timestamp?: string; severity?: string; action?: string; threat_score?: number; entity_id?: string; intent_classification?: string; }
interface Stats  { blocked_requests?: number; pii_events?: number; avg_threat_score?: number; total_requests?: number; layer_status?: Record<string,string>; }
interface FirewallHealth { status?: string; config?: Record<string,boolean>; layer_status?: Record<string,string>; }

const LAYER_NAMES = [
  'Layer 1 — Cleansing Transformer',
  'Layer 2 — Agentic RBAC Proxy',
  'Layer 3 — Cognitive Threat Classifier',
  'Layer 4 — Forensic Semantic Logger',
  'Layer 5 — Compliance Ledger',
];

function AlertCard({ t }: { t: Threat }) {
  const sev = t.severity ?? (t.threat_score && t.threat_score > 0.7 ? 'HIGH' : t.threat_score && t.threat_score > 0.3 ? 'MEDIUM' : 'LOW');
  const colors: Record<string, string> = { HIGH: 'border-l-red-600 bg-red-950/10', MEDIUM: 'border-l-orange-600 bg-orange-950/10', LOW: 'border-l-slate-700 bg-slate-900/20', CRITICAL: 'border-l-red-500 bg-red-950/20' };
  const badgeColors: Record<string, string> = { HIGH: 'text-red-400 bg-red-950 border-red-800', MEDIUM: 'text-orange-400 bg-orange-950 border-orange-800', LOW: 'text-slate-400 bg-slate-800 border-slate-700', CRITICAL: 'text-red-300 bg-red-950 border-red-700' };
  const bc = colors[sev.toUpperCase()] ?? colors.LOW;
  const sc = badgeColors[sev.toUpperCase()] ?? badgeColors.LOW;
  return (
    <div className={`border-l-2 rounded-r p-3 ${bc}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[8px] font-black tracking-widest px-1.5 py-px rounded border ${sc}`}>{sev.toUpperCase()}</span>
            <span className="text-[9px] font-mono text-slate-600">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '—'}</span>
          </div>
          <p className="text-xs text-slate-300 font-mono truncate">{t.intent_classification ?? t.action ?? 'THREAT_DETECTED'}</p>
          {t.entity_id && <p className="text-[9px] text-sky-700 font-mono mt-0.5">entity: {t.entity_id}</p>}
        </div>
        {t.threat_score !== undefined && (
          <span className="text-[10px] font-black font-mono text-sky-500 tabular-nums flex-shrink-0">{t.threat_score.toFixed(3)}</span>
        )}
      </div>
    </div>
  );
}

export default function SOCCommandCenter() {
  const [threats, setThreats] = useState<Threat[]>([]);
  const [stats, setStats]     = useState<Stats>({});
  const [loading, setLoading] = useState(true);
  // Layer status: pulled from /firewall/stats → layer_status map
  // Keys: cleansing | rbac | ensemble | forensic | compliance
  const [layerStatus, setLayerStatus] = useState<string[]>(['ARMED', 'ARMED', 'ARMED', 'ARMED', 'ARMED']);
  const [deployingDecoy, setDeployingDecoy] = useState(false);

  useEffect(() => {
    const load = async () => {
      const [t, s, fw] = await Promise.allSettled([
        apiRequest<Threat[] | { items?: Threat[]; threats?: Threat[] }>('/firewall/threats/recent?limit=20'),
        apiRequest<Stats>('/stats/'),
        apiRequest<FirewallHealth>('/firewall/stats'),
      ]);
      if (t.status === 'fulfilled') {
        const raw = t.value;
        setThreats(Array.isArray(raw) ? raw : (raw?.threats ?? raw?.items ?? []));
      }
      if (s.status === 'fulfilled') setStats(s.value ?? {});
      if (fw.status === 'fulfilled' && fw.value?.layer_status) {
        const ls = fw.value.layer_status;
        setLayerStatus([
          ls['cleansing']  ?? 'ARMED',
          ls['rbac']       ?? 'ARMED',
          ls['ensemble']   ?? 'ARMED',
          ls['forensic']   ?? 'ARMED',
          ls['compliance'] ?? 'ARMED',
        ]);
      }
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, []);

  const deployDecoy = async () => {
    setDeployingDecoy(true);
    try {
      await apiRequest('/defense/decoys/deploy', {
        method: 'POST',
        body: JSON.stringify({ path: `/honeypot/svc-${Date.now()}`, protocol: 'TCP' }),
      });
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: 'Decoy deployed — tripwire armed', level: 'ok' }
      }));
    } catch (e) {
      window.dispatchEvent(new CustomEvent('projectxy:toast', {
        detail: { msg: `Decoy deploy failed: ${(e as Error).message}`, level: 'error' }
      }));
    } finally {
      setDeployingDecoy(false);
    }
  };

  const statCards = [
    { label: 'Threats Blocked', value: stats.blocked_requests ?? 0,  icon: Shield,      color: 'text-sky-400'    },
    { label: 'PII Violations',  value: stats.pii_events ?? 0,        icon: AlertTriangle,color: 'text-yellow-400' },
    { label: 'Total Requests',  value: stats.total_requests ?? 0,    icon: Activity,    color: 'text-slate-300'  },
    { label: 'Avg Threat Score',value: (stats.avg_threat_score ?? 0).toFixed(3), icon: TrendingDown, color: 'text-emerald-400' },
  ];

  return (
    <TeamShell team="blue" title="SOC Command Center" subtitle="Security Operations — Defensive Posture">
      <div className="p-6 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-sky-950/10 border border-sky-900/30 rounded-lg p-4">
              <Icon size={14} className={`${color} mb-2`} />
              <p className={`text-2xl font-black tabular-nums ${color}`}>{value}</p>
              <p className="text-[10px] text-slate-500 tracking-wide mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Alert Queue */}
          <div className="bg-[#00091A] border border-sky-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-sky-900/20">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-sky-400">LIVE ALERT QUEUE</span>
              <span className="ml-auto text-[9px] font-mono text-slate-600">{threats.length} events</span>
            </div>
            <div className="p-3 space-y-2 max-h-80 overflow-y-auto">
              {loading ? (
                <p className="text-slate-600 text-sm font-mono text-center py-6">Fetching threats...</p>
              ) : threats.length === 0 ? (
                <div className="text-center py-6">
                  <Shield size={20} className="text-sky-800 mx-auto mb-2" />
                  <p className="text-slate-600 text-sm font-mono">No active threats. Defenses holding.</p>
                </div>
              ) : (
                threats.map((t, i) => <AlertCard key={t.id ?? i} t={t} />)
              )}
            </div>
          </div>

          {/* Cognitive Shield Layer Status */}
          <div className="bg-[#00091A] border border-sky-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-sky-900/20">
              <Layers size={12} className="text-sky-600" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-sky-400">COGNITIVE SHIELD — LAYER STATUS</span>
            </div>
            <div className="p-4 space-y-3">
              {LAYER_NAMES.map((name, i) => (
                <div key={name} className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-slate-400">{name}</span>
                  <span className={`text-[9px] font-black tracking-widest px-2 py-px rounded border ${
                    layerStatus[i] === 'ARMED'
                      ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                      : 'bg-red-950 text-red-400 border-red-800'
                  }`}>
                    {layerStatus[i]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </TeamShell>
  );
}
