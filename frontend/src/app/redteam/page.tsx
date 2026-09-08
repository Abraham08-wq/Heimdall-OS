'use client';
import { useState } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import { Crosshair, Target, Plus, Zap, Send, Clock } from 'lucide-react';
import { apiRequest } from '@/lib/api';

interface Mission { id?: string; target?: string; status?: string; phase?: string; risk?: string; created_at?: string; }
interface MitreTechnique { id?: string; x_mitre_id?: string; name?: string; kill_chain_phases?: { phase_name: string }[]; description?: string; }

function TechniqueChip({ t, onClick, selected }: { t: MitreTechnique; onClick: () => void; selected: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`text-left px-2 py-1.5 rounded border text-[10px] font-mono transition-all ${
        selected
          ? 'bg-red-950/60 border-red-700 text-red-300'
          : 'bg-[#0D0000] border-red-900/30 text-red-700 hover:border-red-700 hover:text-red-500'
      }`}
    >
      <span className="font-black text-red-600 block">{t.x_mitre_id}</span>
      <span className="truncate block">{t.name}</span>
    </button>
  );
}

export default function RedTeamOps() {
  const [target, setTarget]         = useState('');
  const [objective, setObjective]   = useState('');
  const [selectedTechs, setSelected] = useState<string[]>([]);
  const [missions, setMissions]     = useState<Mission[]>([]);
  const [launching, setLaunching]   = useState(false);
  const [status, setStatus]         = useState('');

  // Built-in top MITRE techniques for quick select (no API call needed)
  const techniques: MitreTechnique[] = [
    { x_mitre_id: 'T1059.001', name: 'PowerShell',            kill_chain_phases: [{ phase_name: 'execution' }] },
    { x_mitre_id: 'T1566.001', name: 'Spearphishing Attach.', kill_chain_phases: [{ phase_name: 'initial-access' }] },
    { x_mitre_id: 'T1003',     name: 'OS Credential Dump',    kill_chain_phases: [{ phase_name: 'credential-access' }] },
    { x_mitre_id: 'T1055',     name: 'Process Injection',     kill_chain_phases: [{ phase_name: 'privilege-escalation' }] },
    { x_mitre_id: 'T1021',     name: 'Remote Services',       kill_chain_phases: [{ phase_name: 'lateral-movement' }] },
    { x_mitre_id: 'T1041',     name: 'Exfil over C2',         kill_chain_phases: [{ phase_name: 'exfiltration' }] },
    { x_mitre_id: 'T1486',     name: 'Data Encrypted Impact', kill_chain_phases: [{ phase_name: 'impact' }] },
    { x_mitre_id: 'T1078',     name: 'Valid Accounts',        kill_chain_phases: [{ phase_name: 'initial-access' }] },
    { x_mitre_id: 'T1190',     name: 'SQL Injection',         kill_chain_phases: [{ phase_name: 'initial-access' }] },
    { x_mitre_id: 'T1110',     name: 'Brute Force',           kill_chain_phases: [{ phase_name: 'credential-access' }] },
    { x_mitre_id: 'T1071',     name: 'App Layer Protocol',    kill_chain_phases: [{ phase_name: 'command-and-control' }] },
    { x_mitre_id: 'T1036',     name: 'Masquerading',          kill_chain_phases: [{ phase_name: 'defense-evasion' }] },
  ];

  const toggleTech = (id: string) =>
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);

  const launchMission = async () => {
    if (!target.trim()) return setStatus('⚠️  Target is required');
    setLaunching(true);
    setStatus('Initiating mission...');
    try {
      const res = await apiRequest<Mission>('/missions/launch', {
        method: 'POST',
        body: JSON.stringify({ target, objective, techniques: selectedTechs }),
      });
      setMissions(m => [res, ...m]);
      setStatus(`✅ Mission launched: ${res.id ?? 'ID pending'}`);
      setTarget(''); setObjective(''); setSelected([]);
    } catch (err: any) {
      setStatus(`⚠️  ${err?.message ?? 'Launch error — check backend'}`);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <TeamShell team="red" title="Red Team Operations" subtitle="Mission Planning & Offensive Tooling — CLASSIFIED">
      <div className="p-6 space-y-6">
        {/* Mission Launcher */}
        <div className="bg-[#0D0000] border border-red-900/40 rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-red-900/30 bg-red-950/10">
            <Target size={12} className="text-red-600" />
            <span className="text-[11px] font-mono font-black tracking-widest text-red-500">MISSION LAUNCHER</span>
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-[9px] font-mono tracking-widest text-red-700 block mb-1">TARGET SYSTEM</label>
                <input
                  value={target}
                  onChange={e => setTarget(e.target.value)}
                  placeholder="192.168.1.0/24 or hostname"
                  className="w-full bg-black border border-red-900/50 text-red-300 font-mono text-xs px-3 py-2 rounded focus:border-red-700 focus:outline-none placeholder:text-red-900"
                />
              </div>
              <div>
                <label className="text-[9px] font-mono tracking-widest text-red-700 block mb-1">OBJECTIVE</label>
                <input
                  value={objective}
                  onChange={e => setObjective(e.target.value)}
                  placeholder="e.g. credential harvest, lateral movement"
                  className="w-full bg-black border border-red-900/50 text-red-300 font-mono text-xs px-3 py-2 rounded focus:border-red-700 focus:outline-none placeholder:text-red-900"
                />
              </div>
            </div>
            {status && (
              <div className="text-[10px] font-mono text-red-400 bg-red-950/20 border border-red-900/30 rounded px-3 py-2">
                {status}
              </div>
            )}
            <button
              onClick={launchMission}
              disabled={launching}
              className="flex items-center gap-2 px-4 py-2 bg-red-700 hover:bg-red-600 disabled:bg-red-950 disabled:text-red-800 text-white font-mono text-xs font-bold tracking-widest rounded transition-colors"
            >
              <Send size={12} />
              {launching ? 'LAUNCHING...' : 'LAUNCH MISSION'}
            </button>
          </div>
        </div>

        {/* MITRE Quick Select */}
        <div className="bg-[#0D0000] border border-red-900/40 rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-red-900/30 bg-red-950/10">
            <Zap size={12} className="text-red-600" />
            <span className="text-[11px] font-mono font-black tracking-widest text-red-500">MITRE ATT&CK — QUICK SELECT</span>
            {selectedTechs.length > 0 && (
              <span className="ml-auto text-[9px] font-black tracking-widest text-red-400">
                {selectedTechs.length} SELECTED
              </span>
            )}
          </div>
          <div className="p-3 grid grid-cols-2 md:grid-cols-4 gap-2">
            {techniques.map(t => (
              <TechniqueChip
                key={t.x_mitre_id}
                t={t}
                onClick={() => toggleTech(t.x_mitre_id!)}
                selected={selectedTechs.includes(t.x_mitre_id!)}
              />
            ))}
          </div>
        </div>

        {/* Active Missions */}
        <div className="bg-[#0D0000] border border-red-900/40 rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-red-900/30 bg-red-950/10">
            <Crosshair size={12} className="text-red-600" />
            <span className="text-[11px] font-mono font-black tracking-widest text-red-500">ACTIVE MISSIONS</span>
          </div>
          {missions.length === 0 ? (
            <div className="text-center py-8">
              <Crosshair size={20} className="text-red-900 mx-auto mb-2" />
              <p className="text-red-900 text-xs font-mono">No missions launched yet. Configure target and launch.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-red-900/30">
                  {['ID', 'TARGET', 'PHASE', 'STATUS', 'RISK', 'TIME'].map(h => (
                    <th key={h} className="px-4 py-2 text-left text-[8px] font-black tracking-widest text-red-800">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-red-900/10">
                {missions.map((m, i) => (
                  <tr key={m.id ?? i} className="hover:bg-red-950/10">
                    <td className="px-4 py-2 text-[10px] font-mono text-red-500">{(m.id ?? '—').slice(0, 8)}</td>
                    <td className="px-4 py-2 text-[10px] font-mono text-red-300">{m.target}</td>
                    <td className="px-4 py-2 text-[9px] font-mono text-red-600">{m.phase ?? 'INITIAL'}</td>
                    <td className="px-4 py-2"><span className="text-[9px] font-black tracking-widest text-yellow-500">{m.status ?? 'PENDING'}</span></td>
                    <td className="px-4 py-2 text-[10px] font-mono text-red-400">{m.risk ?? 'MEDIUM'}</td>
                    <td className="px-4 py-2 text-[9px] font-mono text-slate-600 flex items-center gap-1"><Clock size={9}/>{m.created_at ? new Date(m.created_at).toLocaleTimeString() : 'NOW'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </TeamShell>
  );
}
