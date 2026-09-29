import React, { useState } from 'react';
import { GitCompare, PlusCircle, AlertCircle, MinusCircle, ShieldCheck, History } from 'lucide-react';
import { Badge } from '../common/Badge';
import { apiService as ServiceAPI } from '../../services/api';

interface DeltaRequirement {
  section: string;
  clause_title: string;
  description?: string;
  previous_version?: string;
  new_version?: string;
  reason?: string;
  severity?: 'HIGH' | 'MEDIUM' | 'LOW';
  affected_control?: string;
}

interface RegulationDeltaAnalyzerProps {
  regulationTitle?: string;
  docNumber?: string;
  regulationId?: string;
}

export const RegulationDeltaAnalyzer: React.FC<RegulationDeltaAnalyzerProps> = ({
  regulationTitle,
  docNumber,
  regulationId,
}) => {
  const [selectedTab, setSelectedTab] = useState<'ADDED' | 'MODIFIED' | 'REPEALED'>('ADDED');
  const [loading, setLoading] = useState(false);
  const [changes, setChanges] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (!regulationId) return;
    const fetchChanges = async () => {
      setLoading(true);
      try {
        const data = await ServiceAPI.getRegulatoryChanges(0, 10, regulationId);
        setChanges(data.items || []);
      } catch (err) {
        setError('Failed to load regulatory changes.');
      } finally {
        setLoading(false);
      }
    };
    fetchChanges();
  }, [regulationId]);

  if (loading) {
    return <div className="p-6 text-slate-400">Loading version changes...</div>;
  }

  if (error) {
    return <div className="p-6 text-rose-400">{error}</div>;
  }

  if (!changes || changes.length === 0) {
    return (
      <div className="p-12 text-center border-2 border-dashed border-slate-800 rounded-2xl">
        <GitCompare className="w-12 h-12 text-slate-600 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">No Regulatory Changes Detected</h2>
        <p className="text-slate-400 max-w-md mx-auto">
          The version analyzer only displays data when a genuine <span className="font-mono text-slate-300">RegulatoryChange</span> record has been persisted by the backend. There are currently no updates or version diffs for this regulation.
        </p>
      </div>
    );
  }

  const latestChange = changes[0];
  const added: DeltaRequirement[] = [];
  const modified: DeltaRequirement[] = [];
  const repealed: DeltaRequirement[] = [];

  // Parse diff_hunks if they exist
  if (latestChange.change.diff_hunks) {
     latestChange.change.diff_hunks.forEach((hunk: any) => {
        if (hunk.hunk_type === 'ADDED') {
           added.push({
             section: hunk.section_id || 'Unknown',
             clause_title: 'Added Content',
             description: hunk.content
           });
        } else if (hunk.hunk_type === 'MODIFIED') {
           modified.push({
             section: hunk.section_id || 'Unknown',
             clause_title: 'Modified Content',
             previous_version: hunk.old_content,
             new_version: hunk.content
           });
        } else if (hunk.hunk_type === 'REMOVED') {
           repealed.push({
             section: hunk.section_id || 'Unknown',
             clause_title: 'Repealed Content',
             reason: hunk.content
           });
        }
     });
  }



  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/20 shadow-xl flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <GitCompare className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">Regulation Version Changes & Diff</h2>
            <span className="px-2 py-0.5 text-xs font-mono bg-indigo-500/20 text-indigo-300 rounded border border-indigo-500/30">
              {latestChange.change.previous_version_id?.slice(0,8) || 'Previous'} vs {latestChange.change.new_version_id?.slice(0,8) || 'Current'}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Automated statutory change comparison highlighting added obligations, modified timelines, and repealed clauses.
          </p>
        </div>
      </div>

      {/* Delta Tabs Navigation */}
      <div className="flex items-center space-x-2 p-1.5 rounded-xl glass-panel border border-slate-800 text-xs font-semibold">
        <button
          onClick={() => setSelectedTab('ADDED')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
            selectedTab === 'ADDED' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <PlusCircle className="w-4 h-4 text-emerald-300" />
          <span>Added Obligations</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-emerald-400 font-mono rounded">{added.length}</span>
        </button>

        <button
          onClick={() => setSelectedTab('MODIFIED')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
            selectedTab === 'MODIFIED' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertCircle className="w-4 h-4 text-amber-300" />
          <span>Modified Rules</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-amber-400 font-mono rounded">{modified.length}</span>
        </button>

        <button
          onClick={() => setSelectedTab('REPEALED')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
            selectedTab === 'REPEALED' ? 'bg-rose-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <MinusCircle className="w-4 h-4 text-rose-300" />
          <span>Repealed Clauses</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-rose-400 font-mono rounded">{repealed.length}</span>
        </button>
      </div>

      {/* Tab Content Display */}
      <div className="space-y-4">
        {selectedTab === 'ADDED' && (
          <div className="space-y-3">
            {added.map((item, idx) => (
              <div key={idx} className="glass-panel p-5 rounded-2xl border border-emerald-500/30 space-y-3 bg-emerald-950/10">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">
                      {item.section}
                    </span>
                    <h3 className="text-sm font-bold text-white mt-1">{item.clause_title}</h3>
                  </div>
                  {item.severity && <Badge level={item.severity}>{item.severity} IMPACT</Badge>}
                </div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/80 p-3 rounded-xl border border-slate-800 font-sans">
                  {item.description}
                </p>
                {item.affected_control && (
                  <div className="flex items-center space-x-2 text-xs text-slate-400 pt-1">
                    <span>Mapped Control:</span>
                    <span className="font-mono text-brand-300 font-bold">{item.affected_control}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {selectedTab === 'MODIFIED' && (
          <div className="space-y-3">
            {modified.map((item, idx) => (
              <div key={idx} className="glass-panel p-5 rounded-2xl border border-amber-500/30 space-y-3 bg-amber-950/10">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 text-[10px] font-mono bg-amber-500/20 text-amber-300 rounded border border-amber-500/30">
                    {item.section}
                  </span>
                  <h3 className="text-sm font-bold text-white">{item.clause_title}</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-2">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-900 space-y-1">
                    <span className="text-[10px] uppercase font-bold text-rose-400 block">Previous Text</span>
                    <p className="text-slate-400 font-mono text-[11px] line-through">{item.previous_version}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-emerald-500/30 space-y-1">
                    <span className="text-[10px] uppercase font-bold text-emerald-400 block">New Enforced Text</span>
                    <p className="text-slate-200 font-mono text-[11px] font-semibold">{item.new_version}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {selectedTab === 'REPEALED' && (
          <div className="space-y-3">
            {repealed.map((item, idx) => (
              <div key={idx} className="glass-panel p-5 rounded-2xl border border-rose-500/30 space-y-2 bg-rose-950/10">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 text-[10px] font-mono bg-rose-500/20 text-rose-300 rounded border border-rose-500/30">
                    {item.section}
                  </span>
                  <h3 className="text-sm font-bold text-white">{item.clause_title}</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Reason for Repeal: <span className="text-slate-200 font-semibold">{item.reason}</span>
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
