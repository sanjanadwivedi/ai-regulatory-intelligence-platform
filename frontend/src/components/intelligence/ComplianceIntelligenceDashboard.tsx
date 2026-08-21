import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import {
  ComplianceIntelligenceSnapshot,
  ComplianceDefensePack,
  ComplianceEvidenceManifest,
  UnresolvedItem
} from '../../types';
import {
  ShieldCheck, AlertTriangle, FileText, Download,
  Activity, Search, ShieldAlert, GitMerge, FileX, Info,
  Loader2, RefreshCw
} from 'lucide-react';
import { ApplicabilityReviewActionCenter } from './ApplicabilityReviewActionCenter';

const formatCategory = (cat: string | null | undefined) => {
  if (!cat) return 'Unresolved Item';
  if (cat === 'REQUIRES_REVIEW_APPLICABILITY') return 'Applicability Review Required';
  return cat.replace(/_/g, ' ');
};

const formatSeverityText = (sev: string | null | undefined) => {
  if (!sev) return 'Review Required';
  if (sev === 'REQUIRES_REVIEW') return 'Review Required';
  return sev.replace(/_/g, ' ');
};

const formatEntityType = (type: string | null | undefined) => {
  if (!type) return 'Unknown Entity';
  if (type === 'RegulatoryApplicabilityAssessment') return 'Regulatory Applicability Assessment';
  return type.replace(/([A-Z])/g, ' $1').trim();
};

function UnresolvedItemsSection({ items }: { items: UnresolvedItem[] }) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const grouped = React.useMemo(() => {
    const map: Record<string, UnresolvedItem[]> = {};
    for (const item of items) {
      const cat = item.category || 'UNKNOWN';
      if (!map[cat]) map[cat] = [];
      map[cat].push(item);
    }
    return map;
  }, [items]);

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-red-900/30">
      <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
        <ShieldAlert className="w-5 h-5 text-red-400" />
        Unresolved Items & Gaps ({items.length})
      </h3>
      <div className="space-y-4">
        {Object.entries(grouped).map(([cat, catItems]) => {
          const isExpanded = expandedCategories.has(cat);
          const severity = catItems[0]?.severity;
          
          return (
            <div key={cat} className="bg-slate-900/50 rounded-xl border border-slate-800/50 overflow-hidden">
              <div className="p-4 flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-white">{formatCategory(cat)}</h4>
                  <p className="text-xs text-slate-500 mt-1">{catItems.length} item{catItems.length !== 1 ? 's' : ''} • {formatSeverityText(severity)}</p>
                </div>
                <button
                  onClick={() => toggleCategory(cat)}
                  className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-md transition-colors"
                >
                  {isExpanded ? 'Hide details' : `View ${catItems.length} item${catItems.length !== 1 ? 's' : ''}`}
                </button>
              </div>
              
              {isExpanded && (
                <div className="border-t border-slate-800/50 bg-slate-950/30 overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800/50 text-xs uppercase tracking-wider text-slate-500">
                        <th className="p-3 font-medium">Severity</th>
                        <th className="p-3 font-medium">Issue</th>
                        <th className="p-3 font-medium">Entity</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm">
                      {catItems.map((item, idx) => (
                        <tr key={idx} className="border-b border-slate-800/30 hover:bg-slate-900/50">
                          <td className="p-3 align-top">
                            <span className={`px-2 py-1 text-[10px] font-bold rounded-md ${item.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                                item.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400' :
                                  item.severity === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' :
                                    'bg-slate-700/50 text-slate-300'
                              }`}>
                              {formatSeverityText(item.severity)}
                            </span>
                          </td>
                          <td className="p-3 text-slate-400 align-top">
                            <div className="font-medium text-slate-300">{item.title}</div>
                            <div className="text-xs text-slate-500 mt-0.5">{item.reason}</div>
                          </td>
                          <td className="p-3 text-slate-500 align-top">
                            <div>{formatEntityType(item.entity_type)}</div>
                            <div className="text-xs font-mono text-slate-500 mt-0.5">
                              {item.entity_id ? `${item.entity_id.split('-')[0]}...` : 'Not available'}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ComplianceIntelligenceDashboard() {
  type SnapshotState = 'LOADING' | 'NO_SNAPSHOT' | 'GENERATING' | 'SNAPSHOT_READY' | 'ERROR';
  const [viewState, setViewState] = useState<SnapshotState>('LOADING');

  const [snapshot, setSnapshot] = useState<ComplianceIntelligenceSnapshot | null>(null);
  const [defensePacks, setDefensePacks] = useState<ComplianceDefensePack[]>([]);
  const [isGeneratingPack, setIsGeneratingPack] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchIntelligence = async () => {
    setViewState('LOADING');
    setError(null);
    try {
      try {
        const snap = await ServiceAPI.getComplianceSnapshot();
        setSnapshot(snap);
        setViewState('SNAPSHOT_READY');
      } catch (e: any) {
        if (e.response?.status === 404) {
          // No snapshot exists yet, that's fine
          setSnapshot(null);
          setViewState('NO_SNAPSHOT');
        } else {
          throw e;
        }
      }

      const packs = await ServiceAPI.getDefensePacks();
      setDefensePacks(packs || []);
    } catch (err) {
      setError('Failed to load compliance intelligence data. Please try again.');
      setViewState('ERROR');
    }
  };

  useEffect(() => {
    fetchIntelligence();
  }, []);

  const handleGenerateSnapshot = async () => {
    setViewState('GENERATING');
    setError(null);
    try {
      const snap = await ServiceAPI.generateComplianceSnapshot();
      setSnapshot(snap);
      setViewState('SNAPSHOT_READY');
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 401) {
        setError('Your session has expired. Please sign in again.');
      } else if (status === 403) {
        setError('Only Compliance Officers and Administrators can generate Compliance Intelligence snapshots.');
      } else if (status === 422) {
        setError('The snapshot request could not be validated.');
      } else {
        setError('The snapshot could not be generated. Please try again.');
      }
      setViewState('ERROR');
      console.error('Snapshot generation diagnostic:', { status, message: err.message, data: err.response?.data });
    }
  };

  const handleGenerateDefensePack = async () => {
    if (!snapshot) return;
    setIsGeneratingPack(true);
    try {
      await ServiceAPI.generateDefensePack(snapshot.id);
      const packs = await ServiceAPI.getDefensePacks();
      setDefensePacks(packs || []);
    } catch (err) {
      setError('Failed to generate Evidence & Audit Package.');
    } finally {
      setIsGeneratingPack(false);
    }
  };

  const handleExportDefensePack = async (packId: string) => {
    try {
      const data = await ServiceAPI.exportDefensePack(packId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit-package-${packId}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Failed to export Evidence & Audit Package.');
    }
  };

  if (viewState === 'LOADING') {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-brand-400" />
            Compliance Intelligence & Evidence Package
          </h1>
          <p className="text-slate-400 mt-1">
            Deterministic point-in-time snapshot and auditable evidence package.
          </p>
          <div className="mt-3 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 max-w-2xl">
            <p className="text-amber-400 text-xs font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              Disclaimer: Operational evidence documents execution activity. It does not independently establish legal compliance or guarantee statutory compliance.
            </p>
          </div>
        </div>
        <button
          onClick={handleGenerateSnapshot}
          disabled={viewState === 'GENERATING'}
          className="btn-primary flex items-center gap-2"
        >
          {viewState === 'GENERATING' ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {snapshot ? 'Generate New Snapshot' : 'Generate Initial Snapshot'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* 1. OVERVIEW */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800">
        <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-brand-400" />
          Intelligence Overview
        </h2>
        {snapshot ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
            <div>
              <p className="text-slate-400 text-xs mb-1 uppercase tracking-wider">Snapshot ID</p>
              <p className="text-white font-mono text-xs">{snapshot.id}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs mb-1 uppercase tracking-wider">Generated At</p>
              <p className="text-white font-medium">{new Date(snapshot.generated_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs mb-1 uppercase tracking-wider">Engine Version</p>
              <p className="text-white font-mono text-xs">{snapshot.engine_version}</p>
            </div>
            <div>
              <p className="text-slate-400 text-xs mb-1 uppercase tracking-wider">Unresolved Items</p>
              <p className="text-amber-400 font-bold text-xl">{snapshot.unresolved_items?.length || 0}</p>
            </div>
          </div>
        ) : (
          <div className="text-slate-400 py-6 text-center">
            No intelligence snapshot generated yet. Click "Generate Initial Snapshot" to begin.
          </div>
        )}

        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800 flex items-start gap-3">
          <Info className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
          <p className="text-slate-300 text-sm">
            <span className="font-bold text-white">Disclaimer: </span>
            Operational evidence documents execution activity. Legal applicability and statutory compliance remain separate determinations. Completed tasks do not independently establish legal compliance.
          </p>
        </div>
      </div>

      {snapshot && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 2. LEGAL APPLICABILITY */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800">
            <h3 className="text-base font-bold text-white mb-4">Legal Applicability</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Applicable</p>
                <p className="text-2xl font-bold text-white">{snapshot.legal_summary?.applicable || 0}</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Not Applicable</p>
                <p className="text-2xl font-bold text-slate-400">{snapshot.legal_summary?.not_applicable || 0}</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Requires Review</p>
                <p className="text-2xl font-bold text-amber-500">{snapshot.legal_summary?.requires_review || 0}</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 italic text-center">
              Evaluated {snapshot.legal_summary?.total_regulations_evaluated || 0} regulatory sources
            </p>
          </div>

          {/* 3. ACTIVE STATUTORY OBLIGATIONS */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800">
            <h3 className="text-base font-bold text-white mb-4">Statutory Obligations</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Active</p>
                <p className="text-2xl font-bold text-brand-400">{snapshot.obligation_summary?.active || 0}</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Superseded</p>
                <p className="text-2xl font-bold text-slate-500">{snapshot.obligation_summary?.superseded || 0}</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-xl text-center border border-slate-800/50">
                <p className="text-slate-400 text-xs uppercase tracking-wider mb-2">Review Needed</p>
                <p className="text-2xl font-bold text-amber-500">{snapshot.obligation_summary?.requires_review || 0}</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 italic text-center">
              Authoritative extraction from applicable legal requirements
            </p>
          </div>
        </div>
      )}

      {snapshot && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* 4. OPERATIONAL EXECUTION */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800">
            <h3 className="text-base font-bold text-white mb-4">Operational Execution</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: 'Open', key: 'open', color: 'text-white' },
                { label: 'In Progress', key: 'in_progress', color: 'text-brand-400' },
                { label: 'Completed', key: 'completed', color: 'text-green-400' },
                { label: 'Overdue', key: 'overdue', color: 'text-red-400' },
                { label: 'Blocked', key: 'blocked', color: 'text-amber-400' },
                { label: 'Reopened', key: 'reopened', color: 'text-orange-400' },
              ].map(stat => (
                <div key={stat.key} className="bg-slate-900/30 p-3 rounded-lg border border-slate-800/30 flex justify-between items-center">
                  <span className="text-xs text-slate-400">{stat.label}</span>
                  <span className={`font-bold ${stat.color}`}>
                    {snapshot.operational_summary?.[stat.key] || 0}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-4 text-center">
              <span className="inline-block px-3 py-1 bg-brand-500/10 text-brand-400 text-xs rounded-full border border-brand-500/20 font-medium">
                Completed ≠ Legally Compliant
              </span>
            </div>
          </div>

          {/* 5. EVIDENCE COVERAGE */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800">
            <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-brand-400" />
              Evidence Coverage
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-xl border border-slate-800/50">
                <span className="text-sm font-medium text-slate-300">Evidence Present</span>
                <span className="text-lg font-bold text-white">{snapshot.evidence_summary?.evidence_present || 0}</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-red-500/5 rounded-xl border border-red-500/10">
                <span className="text-sm font-medium text-red-400">Evidence Gaps</span>
                <span className="text-lg font-bold text-red-400">{snapshot.evidence_summary?.evidence_gap || 0}</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-amber-500/5 rounded-xl border border-amber-500/10">
                <span className="text-sm font-medium text-amber-400">Completed Without Evidence</span>
                <span className="text-lg font-bold text-amber-400">{snapshot.evidence_summary?.completed_without_evidence || 0}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ACTION CENTER */}
      <ApplicabilityReviewActionCenter />

      {/* 6. UNRESOLVED ITEMS */}
      {snapshot && snapshot.unresolved_items && snapshot.unresolved_items.length > 0 && (
        <UnresolvedItemsSection items={snapshot.unresolved_items} />
      )}

      {/* 7. PROVENANCE EXPLORER */}
      {snapshot && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800">
          <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
            <GitMerge className="w-5 h-5 text-brand-400" />
            3-Layer Provenance Explorer
          </h3>
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-400 overflow-hidden">
            <p className="mb-2 text-slate-500">// Provenance Graph implicitly traces all active entities across layers.</p>
            <div className="pl-4 border-l-2 border-brand-500/30 py-2">
              <span className="text-brand-300 font-bold">LAYER 1 — REGULATORY / LEGAL</span>
              <p className="mt-1 pl-4 text-slate-500">Regulations → Assessments → Statutory Evidence</p>
            </div>
            <div className="pl-4 border-l-2 border-amber-500/30 py-2 mt-2">
              <span className="text-amber-300 font-bold">LAYER 2 — ORGANIZATION</span>
              <p className="mt-1 pl-4 text-slate-500">Enterprise Profile → Discovered Signals → Org Context</p>
            </div>
            <div className="pl-4 border-l-2 border-green-500/30 py-2 mt-2">
              <span className="text-green-300 font-bold">LAYER 3 — OPERATIONAL</span>
              <p className="mt-1 pl-4 text-slate-500">Obligations → Tasks → Operational Evidence → Triggers</p>
            </div>
          </div>
        </div>
      )}

      {/* 8. EVIDENCE & AUDIT PACKAGE MANAGER */}
      {snapshot && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-brand-400" />
                Evidence & Audit Package Manager
              </h3>
              <p className="text-xs text-slate-400 mt-1">Immutable cryptographic audit packages</p>
            </div>
            <button
              onClick={handleGenerateDefensePack}
              disabled={isGeneratingPack}
              className="btn-secondary flex items-center gap-2"
            >
              {isGeneratingPack ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
              Generate Evidence Package
            </button>
          </div>

          {defensePacks.length > 0 ? (
            <div className="space-y-3">
              {defensePacks.map(pack => (
                <div key={pack.id} className={`p-4 rounded-xl border ${pack.status === 'GENERATED' ? 'bg-slate-900/80 border-brand-500/30' : 'bg-slate-900/30 border-slate-800'} flex flex-col md:flex-row gap-4 justify-between items-start md:items-center`}>
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-white font-bold">{pack.pack_version}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider ${pack.status === 'GENERATED' ? 'bg-green-500/20 text-green-400' : 'bg-slate-800 text-slate-400'}`}>
                        {pack.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-2 flex items-center gap-1">
                      SHA-256: <span className="text-slate-300">{pack.content_hash.substring(0, 16)}...</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-slate-500">{new Date(pack.generated_at).toLocaleDateString()}</span>
                    <button
                      onClick={() => handleExportDefensePack(pack.id)}
                      className="ml-4 p-2 rounded-lg bg-slate-800 text-white hover:bg-slate-700 transition-colors"
                      title="Export JSON"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500 border border-dashed border-slate-800 rounded-xl">
              <FileX className="w-8 h-8 mx-auto mb-3 text-slate-600" />
              <p>No Evidence & Audit Packages generated yet.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
