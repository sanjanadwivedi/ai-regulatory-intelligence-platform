import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import { RegulatoryIntelligenceSummary } from '../../types';
import { Loader2, Activity, FileText, CheckCircle, AlertCircle, BookOpen } from 'lucide-react';

export function RegulatoryIntelligenceSummaryWidget() {
  const [summary, setSummary] = useState<RegulatoryIntelligenceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    ServiceAPI.getRegulatoryIntelligenceSummary()
      .then(data => {
        if (isMounted) {
          setSummary(data);
          setLoading(false);
        }
      })
      .catch(err => {
        if (isMounted) {
          setError('Failed to load regulatory intelligence summary.');
          setLoading(false);
        }
      });
    return () => { isMounted = false; };
  }, []);

  if (loading) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex items-center justify-center min-h-[150px]">
        <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-red-900/30 text-red-400 flex items-center justify-center min-h-[150px]">
        <AlertCircle className="w-5 h-5 mr-2" />
        {error || 'Failed to load summary.'}
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800">
      <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-6">
        <Activity className="w-5 h-5 text-brand-400" />
        Regulatory Intelligence Summary
      </h2>
      
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50 text-center">
          <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Total Regulations</p>
          <p className="text-2xl font-bold text-white">{summary.total_regulations}</p>
        </div>
        
        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50 text-center">
          <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">New Regulations</p>
          <p className="text-2xl font-bold text-green-400">{summary.new_regulations}</p>
        </div>

        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50 text-center">
          <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Updated Regulations</p>
          <p className="text-2xl font-bold text-blue-400">{summary.updated_regulations}</p>
        </div>

        <div className="bg-slate-900/50 p-4 rounded-xl border border-amber-900/30 text-center relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-amber-500/50"></div>
          <p className="text-amber-400/80 text-xs uppercase tracking-wider mb-2">Review Required</p>
          <p className="text-2xl font-bold text-amber-500">{summary.changes_requiring_review}</p>
        </div>

        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50 text-center">
          <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Affected Downstream</p>
          <div className="flex justify-center gap-4 mt-2">
             <div title="Affected Assessments">
                <p className="text-xs text-slate-500">Assess</p>
                <p className="text-sm font-bold text-white">{summary.affected_assessments}</p>
             </div>
             <div title="Affected Obligations">
                <p className="text-xs text-slate-500">Oblig</p>
                <p className="text-sm font-bold text-white">{summary.affected_obligations}</p>
             </div>
             <div title="Affected Tasks">
                <p className="text-xs text-slate-500">Tasks</p>
                <p className="text-sm font-bold text-white">{summary.affected_tasks}</p>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
