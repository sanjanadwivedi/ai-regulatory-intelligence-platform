import React, { useState } from 'react';
import {
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Play,
  Filter,
  Layers,
  Sparkles,
  Clock,
  ShieldCheck,
  Zap,
  CheckSquare,
  Search,
  FileText,
  TrendingUp,
  SlidersHorizontal
} from 'lucide-react';
import { ServiceAPI } from '../../services/api';

export const BatchReExtractionDashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    authority: 'RBI',
    sector: '',
    region: '',
    needs_revalidation: true,
    source_verified: false,
  });

  const [autoResolve, setAutoResolve] = useState(true);
  const [parallelWorkers, setParallelWorkers] = useState(10);
  const [skipOnError, setSkipOnError] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [resultFilter, setResultFilter] = useState<'ALL' | 'SUCCESS' | 'FAILED' | 'RESOLVED'>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const handleBatchReExtract = async () => {
    setLoading(true);
    setErrorMsg(null);
    setResults(null);

    try {
      const payload = {
        filters: {
          authority: filters.authority.trim() || undefined,
          sector: filters.sector.trim() || undefined,
          region: filters.region.trim() || undefined,
          needs_revalidation: filters.needs_revalidation ? true : undefined,

          source_verified: filters.source_verified ? 0 : undefined,
        },
        auto_resolve: autoResolve,
        parallel_workers: parallelWorkers,
        skip_on_error: skipOnError,
        dry_run: dryRun,
      };

      const data = await ServiceAPI.batch_re_extract(payload);
      if (data.status === 'FAILED' && data.error) {
        setErrorMsg(data.error);
      } else {
        setResults(data);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Batch re-extraction request failed';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const filteredResultsList = results?.results ? results.results.filter((r: any) => {
    if (resultFilter === 'SUCCESS' && r.status !== 'SUCCESS') return false;
    if (resultFilter === 'FAILED' && r.status !== 'FAILED') return false;
    if (resultFilter === 'RESOLVED' && !r.was_resolved) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        r.regulation_id?.toLowerCase().includes(term) ||
        r.doc_number?.toLowerCase().includes(term) ||
        r.authority?.toLowerCase().includes(term) ||
        r.original_source_url?.toLowerCase().includes(term)
      );
    }
    return true;
  }) : [];

  return (
    <div className="space-y-6 pb-12">
      {/* Top Banner Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-panel p-6 rounded-3xl border border-slate-800 shadow-xl">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/20 text-brand-400 border border-brand-500/30 flex items-center justify-center shrink-0">
            <RefreshCw className={`w-6 h-6 ${loading ? 'animate-spin' : ''}`} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              Batch Regulation Re-Extraction Engine
              <span className="px-2.5 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-extrabold bg-brand-500/15 text-brand-300 border border-brand-500/30">
                Parallel Pipeline v2.0
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Auto-detect catalog URLs, crawl direct target documents in parallel (up to 20 workers), and re-generate AI compliance ontologies.
            </p>
          </div>
        </div>

        <button
          onClick={handleBatchReExtract}
          disabled={loading}
          className="px-6 py-3 bg-brand-500 hover:bg-brand-400 active:bg-brand-600 text-white font-bold text-sm rounded-xl border border-brand-400/40 flex items-center justify-center gap-2 transition-all shadow-lg shadow-brand-500/20 disabled:opacity-50 shrink-0"
        >
          <Play className={`w-4 h-4 fill-current ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Executing Parallel Extraction...' : 'Start Batch Re-Extraction'}</span>
        </button>
      </div>

      {/* Filter & Execution Config Panel */}
      <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-5 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-brand-400" />
            <span>Batch Scope & Filter Configuration</span>
          </h2>
          {dryRun && (
            <span className="px-3 py-1 bg-amber-500/15 border border-amber-500/30 text-amber-300 rounded-lg text-xs font-bold flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5" /> Dry Run Mode Enabled (Preview Only)
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {/* Authority Filter */}
          <div className="space-y-1.5">
            <label className="text-slate-300 font-semibold block">Target Regulatory Authority</label>
            <div className="relative">
              <input
                type="text"
                placeholder="e.g. RBI, SEBI, CERT-In, HHS"
                value={filters.authority}
                onChange={(e) => setFilters({ ...filters, authority: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none transition-all"
              />
            </div>
          </div>

          {/* Sector Filter */}
          <div className="space-y-1.5">
            <label className="text-slate-300 font-semibold block">Industry Sector</label>
            <input
              type="text"
              placeholder="e.g. Banking, Capital Markets"
              value={filters.sector}
              onChange={(e) => setFilters({ ...filters, sector: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none transition-all"
            />
          </div>

          {/* Parallel Workers Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-slate-300 font-semibold">Concurrent Worker Threads</label>
              <span className="font-mono text-brand-400 font-bold">{parallelWorkers} Workers</span>
            </div>
            <input
              type="range"
              min="1"
              max="20"
              value={parallelWorkers}
              onChange={(e) => setParallelWorkers(parseInt(e.target.value) || 10)}
              className="w-full accent-brand-500 cursor-pointer h-2 bg-slate-950 rounded-lg"
            />
          </div>
        </div>

        {/* Toggles Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2 text-xs">
          <label className="flex items-center space-x-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800/80 cursor-pointer hover:border-slate-700 transition-all">
            <input
              type="checkbox"
              checked={filters.needs_revalidation}
              onChange={(e) => setFilters({ ...filters, needs_revalidation: e.target.checked })}
              className="rounded accent-brand-500 w-4 h-4"
            />
            <span className="text-slate-300 font-medium">Needs Revalidation Only</span>
          </label>

          <label className="flex items-center space-x-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800/80 cursor-pointer hover:border-slate-700 transition-all">
            <input
              type="checkbox"
              checked={filters.source_verified}
              onChange={(e) => setFilters({ ...filters, source_verified: e.target.checked })}
              className="rounded accent-brand-500 w-4 h-4"
            />
            <span className="text-slate-300 font-medium">Unverified Sources Only</span>
          </label>

          <label className="flex items-center space-x-2.5 p-3 rounded-xl bg-slate-950 border border-slate-800/80 cursor-pointer hover:border-slate-700 transition-all">
            <input
              type="checkbox"
              checked={autoResolve}
              onChange={(e) => setAutoResolve(e.target.checked)}
              className="rounded accent-brand-500 w-4 h-4"
            />
            <span className="text-indigo-300 font-medium flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Auto-Resolve Index URLs
            </span>
          </label>

          <label className="flex items-center space-x-2.5 p-3 rounded-xl bg-slate-950 border border-amber-500/30 cursor-pointer hover:bg-amber-500/5 transition-all">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="rounded accent-amber-500 w-4 h-4"
            />
            <span className="text-amber-300 font-medium">Dry Run (Preview Changes)</span>
          </label>
        </div>
      </div>

      {/* Error Notice */}
      {errorMsg && (
        <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Results Dashboard Section */}
      {results && (
        <div className="space-y-6">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="glass-panel p-5 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 text-center space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">Succeeded</span>
              <p className="text-3xl font-extrabold text-emerald-400">{results.summary?.succeeded ?? 0}</p>
              <span className="text-[11px] text-slate-400 font-mono">of {results.total_regulations_found} regulations</span>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-rose-500/30 bg-rose-950/20 text-center space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">Failed</span>
              <p className="text-3xl font-extrabold text-rose-400">{results.summary?.failed ?? 0}</p>
              <span className="text-[11px] text-slate-400 font-mono">errors encountered</span>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-indigo-500/30 bg-indigo-950/20 text-center space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">URLs Auto-Resolved</span>
              <p className="text-3xl font-extrabold text-indigo-400">{results.summary?.urls_auto_resolved ?? 0}</p>
              <span className="text-[11px] text-slate-400 font-mono">index URLs resolved</span>
            </div>

            <div className="glass-panel p-5 rounded-2xl border border-brand-500/30 bg-brand-950/20 text-center space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">Execution Time</span>
              <p className="text-3xl font-extrabold text-brand-400">{results.summary?.total_time_seconds ?? 0}s</p>
              <span className="text-[11px] text-slate-400 font-mono">{parallelWorkers} parallel workers</span>
            </div>
          </div>

          {/* Content Quality Improvement Banner */}
          <div className="glass-panel p-5 rounded-2xl border border-emerald-500/40 bg-emerald-950/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  Total Statutory Content Quality Improvement:
                  <span className="text-emerald-400 font-mono text-base font-extrabold">
                    +{results.summary?.total_content_improvement?.improvement_percentage}%
                  </span>
                </h3>
                <p className="text-xs text-slate-300 mt-0.5">
                  Character footprint expanded from{' '}
                  <strong className="text-slate-200">
                    {results.summary?.total_content_improvement?.before_total_chars?.toLocaleString()}
                  </strong>{' '}
                  to{' '}
                  <strong className="text-emerald-400">
                    {results.summary?.total_content_improvement?.after_total_chars?.toLocaleString()}
                  </strong>{' '}
                  characters of clean statutory text.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono shrink-0">
              <div className="text-right">
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Avg OCR Conf.</span>
                <span className="text-emerald-400 font-bold text-sm">
                  {Math.round((results.summary?.average_ocr_confidence ?? 0.95) * 100)}%
                </span>
              </div>
              <div className="text-right">
                <span className="text-slate-400 block text-[10px] uppercase font-semibold">Avg Calibration</span>
                <span className="text-indigo-400 font-bold text-sm">
                  {Math.round((results.summary?.average_calibration_score ?? 0.90) * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Individual Regulation Results Table */}
          <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Detailed Batch Results ({filteredResultsList.length})
                </h3>
              </div>

              {/* Result Filter Tabs & Search */}
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Search results..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none"
                  />
                </div>

                <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800 text-[11px] font-semibold">
                  <button
                    onClick={() => setResultFilter('ALL')}
                    className={`px-2.5 py-1 rounded-lg transition-all ${resultFilter === 'ALL' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'}`}
                  >
                    All ({results.results?.length ?? 0})
                  </button>
                  <button
                    onClick={() => setResultFilter('SUCCESS')}
                    className={`px-2.5 py-1 rounded-lg transition-all ${resultFilter === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:text-white'}`}
                  >
                    Success ({results.summary?.succeeded ?? 0})
                  </button>
                  <button
                    onClick={() => setResultFilter('FAILED')}
                    className={`px-2.5 py-1 rounded-lg transition-all ${resultFilter === 'FAILED' ? 'bg-rose-500/20 text-rose-300' : 'text-slate-400 hover:text-white'}`}
                  >
                    Failed ({results.summary?.failed ?? 0})
                  </button>
                  <button
                    onClick={() => setResultFilter('RESOLVED')}
                    className={`px-2.5 py-1 rounded-lg transition-all ${resultFilter === 'RESOLVED' ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-400 hover:text-white'}`}
                  >
                    Resolved ({results.summary?.urls_auto_resolved ?? 0})
                  </button>
                </div>
              </div>
            </div>

            {/* Results Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Regulation ID & Doc Number</th>
                    <th className="py-3 px-3">Authority</th>
                    <th className="py-3 px-3">Source URL Resolution</th>
                    <th className="py-3 px-3 text-right">Chars (Before → After)</th>
                    <th className="py-3 px-3 text-right">Ext. Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {filteredResultsList.map((res: any, idx: number) => (
                    <tr key={res.regulation_id || idx} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-3 whitespace-nowrap">
                        {res.status === 'SUCCESS' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            <CheckCircle2 className="w-3 h-3" /> SUCCESS
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                            <AlertCircle className="w-3 h-3" /> FAILED
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-3">
                        <div className="font-bold text-white font-mono">{res.regulation_id}</div>
                        <div className="text-[11px] text-slate-400">{res.doc_number || 'N/A'}</div>
                      </td>

                      <td className="py-3 px-3 whitespace-nowrap font-medium text-slate-300">
                        {res.authority || 'N/A'}
                      </td>

                      <td className="py-3 px-3 max-w-xs">
                        <div className="truncate text-slate-300 font-mono text-[11px]" title={res.resolved_source_url || res.original_source_url}>
                          {res.resolved_source_url || res.original_source_url || 'N/A'}
                        </div>
                        {res.was_resolved && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-indigo-400 mt-0.5">
                            <Sparkles className="w-3 h-3" /> URL Auto-Resolved
                          </span>
                        )}
                        {res.error && (
                          <span className="text-[10px] text-rose-400 font-mono block mt-0.5 truncate" title={res.error}>
                            {res.error}
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-3 text-right font-mono whitespace-nowrap">
                        {res.status === 'SUCCESS' ? (
                          <span className="text-slate-300">
                            {res.content_length_before?.toLocaleString()} →{' '}
                            <strong className="text-emerald-400">{res.content_length_after?.toLocaleString()}</strong>
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>

                      <td className="py-3 px-3 text-right font-mono text-slate-400 whitespace-nowrap">
                        {typeof res.extraction_time_seconds === 'number' ? `${res.extraction_time_seconds}s` : '0s'}
                      </td>
                    </tr>
                  ))}

                  {filteredResultsList.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-500 italic">
                        No batch results match the active filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
