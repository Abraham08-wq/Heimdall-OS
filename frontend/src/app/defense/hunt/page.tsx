'use client';
import { useEffect, useState, useRef } from 'react';
import { TeamShell } from '@/components/Layout/TeamShell';
import { Activity, Search, Clock, AlertTriangle } from 'lucide-react';
import { apiRequest } from '@/lib/api';

interface HuntResult {
  id?: string; timestamp?: string; entity_id?: string;
  threat_score?: number; action?: string; similarity?: number;
  intent_classification?: string; prompt_hash?: string;
}

export default function ThreatHunt() {
  const [query, setQuery]     = useState('');
  const [entityId, setEntityId] = useState('');
  const [results, setResults] = useState<HuntResult[]>([]);
  const [chain, setChain]     = useState<HuntResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError]     = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const hunt = async () => {
    if (!query.trim()) return;
    setSearching(true); setError(''); setChain([]);
    try {
      const res = await apiRequest<HuntResult[] | { results?: HuntResult[] }>(
        '/forensic/hunt/similarity',
        { method: 'POST', body: JSON.stringify({ query, top_k: 15 }) }
      );
      setResults(Array.isArray(res) ? res : (res?.results ?? []));
    } catch (e: any) {
      setError(e?.message ?? 'Hunt query failed');
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const loadChain = async (eid: string) => {
    setEntityId(eid);
    try {
      const res = await apiRequest<HuntResult[] | { chain?: HuntResult[] }>(
        `/forensic/hunt/entity/${encodeURIComponent(eid)}`
      );
      setChain(Array.isArray(res) ? res : (res?.chain ?? []));
    } catch { setChain([]); }
  };

  const threatColor = (s: number) =>
    s > 0.7 ? 'text-red-400' : s > 0.3 ? 'text-yellow-400' : 'text-emerald-400';

  return (
    <TeamShell team="blue" title="Threat Hunt" subtitle="Forensic AI Observability — Layer 4 Semantic Search">
      <div className="p-6 space-y-6">
        {/* Search Bar */}
        <div className="bg-[#00091A] border border-sky-900/30 rounded-lg p-4">
          <label className="text-[9px] font-mono tracking-widest text-sky-700 block mb-2">
            SEMANTIC HUNT QUERY — describe behaviour, not syntax
          </label>
          <div className="flex gap-3">
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && hunt()}
              placeholder="e.g. 'ignore previous instructions', 'jailbreak attempt', 'PII exfiltration'"
              className="flex-1 bg-black border border-sky-900/50 text-sky-300 font-mono text-xs px-3 py-2 rounded focus:border-sky-600 focus:outline-none placeholder:text-sky-900"
            />
            <button
              onClick={hunt}
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-sky-800 hover:bg-sky-700 disabled:bg-slate-900 disabled:text-slate-700 text-white font-mono text-xs font-bold tracking-wider rounded transition-colors"
            >
              <Search size={12} />
              {searching ? 'HUNTING...' : 'HUNT'}
            </button>
          </div>
          {error && <p className="text-red-400 text-[10px] font-mono mt-2">{error}</p>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Results */}
          <div className="bg-[#00091A] border border-sky-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-sky-900/20">
              <Activity size={12} className="text-sky-600" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-sky-400">SIMILARITY RESULTS</span>
              <span className="ml-auto text-[9px] font-mono text-slate-600">{results.length} matches</span>
            </div>
            <div className="divide-y divide-sky-900/20 max-h-96 overflow-y-auto">
              {results.length === 0 ? (
                <div className="py-10 text-center">
                  <Search size={20} className="text-sky-900 mx-auto mb-2" />
                  <p className="text-slate-600 text-xs font-mono">Enter a query and press HUNT</p>
                </div>
              ) : results.map((r, i) => (
                <div
                  key={r.id ?? i}
                  onClick={() => r.entity_id && loadChain(r.entity_id)}
                  className="px-4 py-3 hover:bg-sky-950/20 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-mono text-sky-700">{r.entity_id ?? 'anonymous'}</span>
                    {r.similarity !== undefined && (
                      <span className="text-[9px] font-black text-sky-500">{(r.similarity * 100).toFixed(1)}% match</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-black tabular-nums ${threatColor(r.threat_score ?? 0)}`}>
                      {(r.threat_score ?? 0).toFixed(3)}
                    </span>
                    <span className="text-[9px] font-mono text-slate-500">{r.action ?? '—'}</span>
                    <span className="text-[9px] font-mono text-slate-600 ml-auto truncate max-w-[100px]">
                      {r.intent_classification ?? ''}
                    </span>
                  </div>
                  {r.prompt_hash && (
                    <p className="text-[8px] font-mono text-slate-700 mt-0.5">hash: {r.prompt_hash}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Entity Chain */}
          <div className="bg-[#00091A] border border-sky-900/30 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-sky-900/20">
              <Clock size={12} className="text-sky-600" />
              <span className="text-[11px] font-mono font-bold tracking-widest text-sky-400">ENTITY TIMELINE</span>
              {entityId && <span className="ml-2 text-[9px] font-mono text-sky-700">{entityId}</span>}
            </div>
            <div className="divide-y divide-sky-900/10 max-h-96 overflow-y-auto">
              {chain.length === 0 ? (
                <div className="py-10 text-center">
                  <AlertTriangle size={20} className="text-sky-900 mx-auto mb-2" />
                  <p className="text-slate-600 text-xs font-mono">Click a result to load entity chain</p>
                </div>
              ) : chain.map((c, i) => (
                <div key={c.id ?? i} className="flex items-start gap-3 px-4 py-2">
                  <div className="flex flex-col items-center mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-600" />
                    {i < chain.length - 1 && <span className="w-px flex-1 bg-sky-900/30 my-0.5" />}
                  </div>
                  <div>
                    <p className="text-[9px] font-mono text-slate-500">{c.timestamp ? new Date(c.timestamp).toLocaleString() : '—'}</p>
                    <p className={`text-xs font-mono font-bold ${threatColor(c.threat_score ?? 0)}`}>{(c.threat_score ?? 0).toFixed(4)}</p>
                    <p className="text-[9px] text-slate-600">{c.action} — {c.intent_classification ?? ''}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </TeamShell>
  );
}
