import React, { useState, useEffect } from 'react';
import {
  FileText,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  X,
  ExternalLink,
  Copy,
  Check,
  Columns,
  List,
  AlertCircle,
  Plus,
  Minus,
  Sparkles,
  Layers
} from 'lucide-react';
import { Regulation } from '../../types';
import { ServiceAPI } from '../../services/api';

interface SourceDiffViewerProps {
  regulation: Regulation;
  onClose: () => void;
}

export const SourceDiffViewer: React.FC<SourceDiffViewerProps> = ({ regulation, onClose }) => {
  const [diffData, setDiffData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState<'SPLIT' | 'UNIFIED'>('SPLIT');
  const [activeTab, setActiveTab] = useState<'HUNKS' | 'SECTIONS' | 'RECOMMENDATIONS' | 'RAW'>('HUNKS');
  const [copied, setCopied] = useState(false);

  const [loadingStep, setLoadingStep] = useState<string>('Resolving source URL...');

  const fetchDiffData = async (forceFresh = false) => {
    setLoading(true);
    setError(null);
    setLoadingStep('🌐 Step 1/3: Resolving direct government source URL...');

    const cacheKey = `source_diff_${regulation.id}`;
    if (!forceFresh) {
      try {
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
          const { cachedAt, data } = JSON.parse(cached);
          if (Date.now() - cachedAt < 300000) {
            setDiffData(data);
            setLoading(false);
            return;
          }
        }
      } catch (e) {
        // Ignore cache parse errors
      }
    }

    try {
      setTimeout(() => setLoadingStep('📥 Step 2/3: Fetching live document text & stripping HTML chrome...'), 1000);
      setTimeout(() => setLoadingStep('🔍 Step 3/3: Running clause-level diff engine & n-gram overlap check...'), 2500);

      const data = await ServiceAPI.getSourceDiff(regulation.id);
      setDiffData(data);
      sessionStorage.setItem(cacheKey, JSON.stringify({ cachedAt: Date.now(), data }));
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to fetch live source diff';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };


  const [resolving, setResolving] = useState(false);
  const [resolutionMsg, setResolutionMsg] = useState<string | null>(null);

  const handleResolveUrl = async () => {
    setResolving(true);
    setResolutionMsg(null);
    try {
      const res = await ServiceAPI.resolveSourceUrl(regulation.id);
      if (res.resolved_source_url && res.resolved_source_url !== regulation.source_url) {
        setResolutionMsg(`✅ Index page resolved to direct document link: ${res.resolved_source_url}`);
      } else {
        setResolutionMsg(`ℹ️ ${res.resolution_reason || 'Source URL checked — already optimal'}`);
      }
      // Re-fetch diff with resolved URL
      await fetchDiffData(true);
    } catch (err: any) {
      setResolutionMsg(`⚠️ URL resolution failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setResolving(false);
    }
  };

  useEffect(() => {
    fetchDiffData();
  }, [regulation.id]);

  const handleCopyUrl = () => {

    const urlToCopy = regulation.resolved_source_url || regulation.source_url;
    if (urlToCopy) {
      navigator.clipboard.writeText(urlToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const diffType = diffData?.diff_type || 'UNKNOWN';
  const driftPct = diffData?.overall_drift_percentage ?? 0.0;
  const verificationScore = diffData?.verification_score ?? regulation.source_url_verification_score ?? 0.0;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-5xl w-full my-auto p-5 sm:p-6 space-y-5 shadow-2xl relative max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3 shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-500/20 text-brand-400 flex items-center justify-center border border-brand-500/30 shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white tracking-tight">Live Official Source Comparison</h2>
                <span className="text-xs font-mono text-slate-500">[{regulation.doc_number || regulation.authority}]</span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-md">
                {regulation.title}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 self-end sm:self-center">
            <button
              onClick={handleResolveUrl}
              disabled={resolving || loading}
              className="p-2 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 transition-colors border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5"
              title="Detect if URL is an index page and resolve to direct document link"
            >
              <Sparkles className={`w-3.5 h-3.5 text-indigo-400 ${resolving ? 'animate-spin' : ''}`} />
              <span>{resolving ? 'Resolving Link...' : 'Resolve Source URL'}</span>
            </button>

            <button
              onClick={() => fetchDiffData(true)}
              disabled={loading || resolving}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white transition-colors border border-slate-700 text-xs font-semibold flex items-center gap-1.5"
              title="Force re-fetch live source"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh Diff</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Resolution Banner Message if triggered */}
        {resolutionMsg && (
          <div className="px-3.5 py-2 rounded-xl bg-slate-950 border border-indigo-500/30 text-xs font-mono text-indigo-300 flex items-center justify-between shrink-0">
            <span>{resolutionMsg}</span>
            <button onClick={() => setResolutionMsg(null)} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
          </div>
        )}

        {/* Status Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl bg-slate-950 border border-slate-800/80 text-xs shrink-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-400 font-semibold">Drift Status:</span>
            {diffType === 'UNCHANGED' && (
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                UNCHANGED ({driftPct}% diff)
              </span>
            )}
            {diffType === 'MODIFIED' && (
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                MODIFIED ({driftPct}% diff)
              </span>
            )}
            {diffType === 'MAJOR_DRIFT' && (
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                MAJOR DRIFT ({driftPct}% diff)
              </span>
            )}
            {diffType === 'UNKNOWN' && (
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-slate-800 text-slate-400 border border-slate-700">
                UNCHECKED
              </span>
            )}

            <span className="text-slate-600">•</span>
            <span className="text-slate-400">
              Overlap Score: <strong className="text-brand-300 font-mono">{(verificationScore * 100).toFixed(1)}%</strong>
            </span>
          </div>

          <div className="flex items-center space-x-3 text-slate-400 text-[11px]">
            <span>Last Checked: <strong className="text-slate-200">{diffData?.fetch_timestamp ? new Date(diffData.fetch_timestamp).toLocaleTimeString() : 'Just now'}</strong></span>
            {regulation.source_url && (
              <a
                href={regulation.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-400 hover:text-brand-300 flex items-center gap-1 font-semibold"
              >
                <span>Official Source</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2 shrink-0">
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setActiveTab('HUNKS')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'HUNKS' ? 'bg-brand-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Clause Diff Hunks ({diffData?.diff_hunks?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('SECTIONS')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'SECTIONS' ? 'bg-brand-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Semantic Sections ({diffData?.semantic_sections?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('RECOMMENDATIONS')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'RECOMMENDATIONS' ? 'bg-amber-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Recommendations ({diffData?.recommendations?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab('RAW')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'RAW' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>Raw Text Compare</span>
            </button>
          </div>

          {activeTab === 'HUNKS' && (
            <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setCompareMode('SPLIT')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all flex items-center gap-1 ${
                  compareMode === 'SPLIT' ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30' : 'text-slate-400'
                }`}
              >
                <Columns className="w-3 h-3" />
                <span>Split Pane</span>
              </button>
              <button
                onClick={() => setCompareMode('UNIFIED')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all flex items-center gap-1 ${
                  compareMode === 'UNIFIED' ? 'bg-brand-500/20 text-brand-300 border border-brand-500/30' : 'text-slate-400'
                }`}
              >
                <List className="w-3 h-3" />
                <span>Unified View</span>
              </button>
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto min-h-[300px] space-y-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-4 text-center">
              <RefreshCw className="w-8 h-8 text-brand-400 animate-spin" />
              <div className="space-y-1">
                <p className="text-sm font-bold text-white tracking-tight">Computing Live Source Clause Diff</p>
                <div className="px-3.5 py-1.5 rounded-full bg-brand-500/15 border border-brand-500/30 text-xs font-mono text-brand-300 inline-block animate-pulse">
                  {loadingStep}
                </div>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">
                Target Source: {regulation.resolved_source_url || regulation.source_url || 'Official Portal'}
              </span>
            </div>
          ) : error ? (

            <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-4 text-xs">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                <h3 className="font-bold text-sm text-white">Live Source Fetch Failed</h3>
              </div>
              <p className="leading-relaxed">
                Could not fetch live official source from <strong className="font-mono text-rose-200">{regulation.source_url || 'N/A'}</strong>.
              </p>
              <div className="p-3 rounded-xl bg-slate-950 font-mono text-[11px] text-rose-200 border border-rose-500/20">
                Reason: {error}
              </div>
              <div className="flex items-center space-x-3 pt-2">
                <button
                  onClick={handleCopyUrl}
                  className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-750 text-white font-bold rounded-xl border border-slate-700 flex items-center gap-1.5 transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied URL!' : 'Copy Source URL to Clipboard'}</span>
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* TAB 1: CLAUSE DIFF HUNKS */}
              {activeTab === 'HUNKS' && (
                <div className="space-y-3">
                  {compareMode === 'SPLIT' ? (
                    <div className="space-y-3">
                      {/* Column Labels */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-bold uppercase tracking-wider text-slate-400 pb-1">
                        <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                          <span className="text-slate-300">STORED (Our System Copy)</span>
                          <span className="text-[10px] text-slate-500 font-mono">regulation.content_text</span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                          <span className="text-brand-300">LIVE (Official Government Source)</span>
                          <span className="text-[10px] text-slate-500 font-mono">Fresh HTTP Fetch</span>
                        </div>
                      </div>

                      {/* Diff Hunks List */}
                      {diffData?.diff_hunks?.length > 0 ? (
                        diffData.diff_hunks.map((hunk: any, idx: number) => {
                          const isUnchanged = hunk.type === 'unchanged';
                          const isModified = hunk.type === 'modified';
                          const isAdded = hunk.type === 'added';
                          const isRemoved = hunk.type === 'removed';

                          return (
                            <div
                              key={idx}
                              className={`p-3 rounded-2xl border text-xs font-mono leading-relaxed transition-all ${
                                isUnchanged
                                  ? 'bg-slate-950/60 border-slate-800/80 text-slate-300'
                                  : isModified
                                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
                                  : isAdded
                                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                                  : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                              }`}
                            >
                              {/* Hunk Status Header */}
                              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800/60 text-[11px]">
                                <span className="flex items-center gap-1.5 font-bold uppercase">
                                  {isUnchanged && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                                  {isModified && <AlertCircle className="w-3.5 h-3.5 text-amber-400" />}
                                  {isAdded && <Plus className="w-3.5 h-3.5 text-emerald-400" />}
                                  {isRemoved && <Minus className="w-3.5 h-3.5 text-rose-400" />}
                                  <span>{hunk.type}</span>
                                </span>

                                <div className="flex items-center space-x-3 text-[10px] text-slate-400">
                                  <span>Line stored: <strong>#{hunk.line_number_stored}</strong></span>
                                  <span>Line live: <strong>#{hunk.line_number_live}</strong></span>
                                  {isModified && (
                                    <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                                      Similarity: {Math.round(hunk.similarity_score * 100)}%
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Split Grid */}
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                                {/* Left: Stored Line */}
                                <div className={`p-2.5 rounded-xl bg-slate-950 border text-xs whitespace-pre-wrap font-sans ${
                                  isRemoved ? 'border-rose-500/40 text-rose-300 bg-rose-950/30' : 'border-slate-800/80 text-slate-300'
                                }`}>
                                  <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Stored Copy</span>
                                  {hunk.stored_line || <em className="text-slate-600 font-italic">[No stored line for added content]</em>}
                                </div>

                                {/* Right: Live Line */}
                                <div className={`p-2.5 rounded-xl bg-slate-950 border text-xs whitespace-pre-wrap font-sans ${
                                  isAdded ? 'border-emerald-500/40 text-emerald-300 bg-emerald-950/30' : isModified ? 'border-amber-500/40 text-amber-200' : 'border-slate-800/80 text-slate-300'
                                }`}>
                                  <span className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Official Live Source</span>
                                  {hunk.live_line || <em className="text-slate-600 font-italic">[Line deleted in live source]</em>}
                                </div>
                              </div>
                            </div>
                          );
                        })
                      ) : (
                        <div className="p-8 text-center glass-panel rounded-2xl border border-slate-800 text-xs text-slate-400">
                          No clause diff hunks to display.
                        </div>
                      )}
                    </div>
                  ) : (
                    /* UNIFIED MODE */
                    <div className="space-y-2 font-mono text-xs">
                      {diffData?.diff_hunks?.map((hunk: any, idx: number) => (
                        <div
                          key={idx}
                          className={`p-3 rounded-xl border whitespace-pre-wrap ${
                            hunk.type === 'unchanged'
                              ? 'bg-slate-950 text-slate-400 border-slate-900'
                              : hunk.type === 'added'
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                              : hunk.type === 'removed'
                              ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                              : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                          }`}
                        >
                          <div className="text-[10px] text-slate-500 font-bold uppercase mb-1">
                            [{hunk.type}] Stored #{hunk.line_number_stored} ➔ Live #{hunk.line_number_live}
                          </div>
                          {hunk.type === 'removed' && (
                            <div className="text-rose-400">- {hunk.stored_line}</div>
                          )}
                          {hunk.type === 'added' && (
                            <div className="text-emerald-400">+ {hunk.live_line}</div>
                          )}
                          {hunk.type === 'modified' && (
                            <div className="space-y-1">
                              <div className="text-rose-400">- {hunk.stored_line}</div>
                              <div className="text-emerald-400">+ {hunk.live_line}</div>
                            </div>
                          )}
                          {hunk.type === 'unchanged' && (
                            <div className="text-slate-300">  {hunk.stored_line}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SEMANTIC SECTIONS BREAKDOWN */}
              {activeTab === 'SECTIONS' && (
                <div className="space-y-3">
                  {diffData?.semantic_sections?.length > 0 ? (
                    diffData.semantic_sections.map((sec: any, idx: number) => {
                      const isUnchanged = sec.status === 'UNCHANGED';
                      const isModified = sec.status === 'MODIFIED';
                      const isDeleted = sec.status === 'DELETED';
                      const isNew = sec.status === 'NEW';

                      return (
                        <div
                          key={idx}
                          className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center space-x-2">
                              <span className="px-2 py-0.5 text-[10px] font-bold font-mono bg-brand-500/20 text-brand-300 rounded border border-brand-500/30">
                                {sec.section_number}
                              </span>
                              <h3 className="text-xs font-bold text-white">{sec.title}</h3>
                            </div>
                            <p className="text-xs text-slate-400 leading-relaxed">
                              {sec.diff_summary}
                            </p>
                          </div>

                          <div className="shrink-0">
                            {isUnchanged && (
                              <span className="px-3 py-1 text-xs font-bold bg-emerald-500/15 text-emerald-300 rounded-xl border border-emerald-500/30">
                                UNCHANGED
                              </span>
                            )}
                            {isModified && (
                              <span className="px-3 py-1 text-xs font-bold bg-amber-500/15 text-amber-300 rounded-xl border border-amber-500/30">
                                MODIFIED
                              </span>
                            )}
                            {isDeleted && (
                              <span className="px-3 py-1 text-xs font-bold bg-rose-500/15 text-rose-300 rounded-xl border border-rose-500/30">
                                DELETED
                              </span>
                            )}
                            {isNew && (
                              <span className="px-3 py-1 text-xs font-bold bg-cyan-500/15 text-cyan-300 rounded-xl border border-cyan-500/30">
                                NEW SECTION
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-8 text-center glass-panel rounded-2xl border border-slate-800 text-xs text-slate-400">
                      No semantic section breakdown available.
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: RECOMMENDATIONS */}
              {activeTab === 'RECOMMENDATIONS' && (
                <div className="space-y-3">
                  <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-2">
                    <h3 className="font-bold text-sm text-white flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-amber-400" />
                      Compliance Officer Action Recommendations
                    </h3>
                    <p className="text-slate-300 leading-relaxed">
                      Based on semantic drift detection between our system copy and the live official source:
                    </p>
                  </div>

                  <div className="space-y-2">
                    {diffData?.recommendations?.map((rec: string, idx: number) => (
                      <div key={idx} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 flex items-start space-x-3">
                        <span className="w-5 h-5 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center shrink-0 text-[11px] font-bold mt-0.5 border border-brand-500/30">
                          {idx + 1}
                        </span>
                        <p className="leading-relaxed">{rec}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 4: RAW TEXT COMPARISON */}
              {activeTab === 'RAW' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-2">
                    <span className="font-bold text-slate-300 uppercase tracking-wider block">Stored Text Copy</span>
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 max-h-96 overflow-y-auto leading-relaxed whitespace-pre-wrap">
                      {regulation.content_text}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <span className="font-bold text-brand-300 uppercase tracking-wider block">Live Source Fetched Text</span>
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 max-h-96 overflow-y-auto leading-relaxed whitespace-pre-wrap">
                      {diffData?.live_text || 'No live text available'}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between pt-3 border-t border-slate-800 text-xs text-slate-400 gap-3 shrink-0">
          <div className="flex items-center space-x-2 font-mono text-[11px]">
            <Sparkles className="w-3.5 h-3.5 text-brand-400" />
            <span>Semantic Clause Diff Engine v1.0 • Aegis AI</span>
          </div>

          <button
            onClick={onClose}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-xl shadow transition-all shrink-0"
          >
            Close Diff Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
