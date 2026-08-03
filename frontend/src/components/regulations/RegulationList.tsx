import React, { useState } from 'react';
import { Search, Filter, FileText, ArrowRight, Sparkles, History, ShieldCheck, ShieldAlert, Clock, AlertTriangle } from 'lucide-react';
import { Regulation } from '../../types';
import { getOfficialSourceUrl } from '../../utils/sourceUrl';

// ─── Source-URL Verification Badge ───────────────────────────────────────────
type VerifiedStatus = 1 | -1 | 0;

const SourceVerificationBadge: React.FC<{ reg: Regulation }> = ({ reg }) => {
  const v = reg.source_url_verified ?? 0;
  const score = reg.source_url_verification_score;
  const note = reg.source_url_verification_note;
  const amendment = reg.possible_amendment_detected;

  if (!reg.source_url) return null;

  if (v === 1) {
    return (
      <span
        title={`Source verified against live URL. Overlap score: ${score?.toFixed(2) ?? 'n/a'}`}
        className="px-2 py-0.5 text-[9px] bg-emerald-500/15 text-emerald-300 font-bold rounded border border-emerald-500/30 uppercase flex items-center gap-1"
      >
        <ShieldCheck className="w-3 h-3" />
        Source Verified
      </span>
    );
  }

  if (v === -1) {
    const isAmendment = amendment === 1;
    const label = isAmendment ? 'Possible Amendment' : note === 'CONTENT_DRIFT_DETECTED' ? 'Content Drift' : 'Source Unverified';
    const colorClass = isAmendment
      ? 'bg-red-500/15 text-red-300 border-red-500/30'
      : 'bg-amber-500/15 text-amber-300 border-amber-500/30';
    const Icon = isAmendment ? AlertTriangle : ShieldAlert;
    return (
      <span
        title={`${label}: ${note ?? 'Live source content does not match stored text'}. Score: ${score?.toFixed(2) ?? 'n/a'}`}
        className={`px-2 py-0.5 text-[9px] font-bold rounded border uppercase flex items-center gap-1 ${colorClass}`}
      >
        <Icon className="w-3 h-3" />
        {label}
      </span>
    );
  }

  // v === 0: unchecked
  return (
    <span
      title="Source URL not yet verified against live content"
      className="px-2 py-0.5 text-[9px] bg-slate-700/40 text-slate-400 font-bold rounded border border-slate-600/30 uppercase flex items-center gap-1"
    >
      <Clock className="w-3 h-3" />
      Not Verified
    </span>
  );
};

interface RegulationListProps {
  regulations: Regulation[];
  onSelectRegulation: (id: string) => void;
}

export const RegulationList: React.FC<RegulationListProps> = ({ regulations, onSelectRegulation }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAuthority, setSelectedAuthority] = useState<string>('ALL');

  const filtered = regulations.filter((reg) => {
    const matchesSearch =
      reg.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reg.authority.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reg.content_text.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesAuth = selectedAuthority === 'ALL' || reg.authority === selectedAuthority;

    return matchesSearch && matchesAuth;
  });

  const authorities = ['ALL', ...Array.from(new Set(regulations.map((r) => r.authority)))];

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search regulations by title, authority, keyword, circular number..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={selectedAuthority}
            onChange={(e) => setSelectedAuthority(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 transition-colors"
          >
            {authorities.map((auth, i) => (
              <option key={i} value={auth}>
                {auth === 'ALL' ? 'All Authorities' : auth}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Rich AI-Native Regulation Cards List */}
      <div className="space-y-4">
        {filtered.map((reg) => {
          const sourceUrl = getOfficialSourceUrl(reg);

          return (
            <div
              key={reg.id}
              onClick={() => onSelectRegulation(reg.id)}
              className="glass-panel glass-panel-hover p-6 rounded-2xl cursor-pointer border border-slate-800 hover:border-brand-500/40 transition-all duration-200 hover:-translate-y-0.5 space-y-4 shadow-xl"
            >
              {/* Top Bar Badges */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-brand-500/20 text-brand-300 rounded border border-brand-500/30">
                      {reg.authority}
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs text-slate-400 font-mono">{reg.doc_number}</span>
                    <span className="text-slate-600">•</span>
                    <span className="px-2 py-0.5 text-[9px] bg-purple-500/20 text-purple-300 font-bold rounded border border-purple-500/30 uppercase flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> AI Ready
                    </span>
                    <span className="px-2 py-0.5 text-[9px] bg-cyan-500/20 text-cyan-300 font-bold rounded border border-cyan-500/30 uppercase">
                      Impact Assessed
                    </span>
                    {/* Live Source-URL Verification Badge */}
                    <SourceVerificationBadge reg={reg} />
                  </div>
                  <h2 className="text-base font-bold text-white hover:text-brand-300 transition-colors">
                    {reg.title}
                  </h2>
                </div>

                {/* Visual Graph Preview Badge & Direct Verification Link */}
                <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
                  <span className="px-3 py-1 bg-slate-900 border border-slate-800 text-cyan-300 rounded-xl text-xs font-mono font-bold flex items-center gap-1.5">
                    <span className="text-brand-400">○──○──○</span>
                    <span>42 Nodes</span>
                  </span>

                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="px-3 py-1 bg-brand-500/15 hover:bg-brand-500/25 text-brand-300 hover:text-white rounded-xl border border-brand-500/40 flex items-center gap-1 text-xs font-bold transition-all shadow-md"
                  >
                    <span>Verify Official Source 🔗</span>
                  </a>
                </div>
              </div>

              {/* Why Do I Care Actionable Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-800/80 text-xs">
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-emerald-400 font-extrabold block text-base">7</span>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">New Reqs</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-brand-400 font-extrabold block text-base">3</span>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Policies Affected</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-amber-400 font-extrabold block text-base">2</span>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Depts Impacted</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-center">
                  <span className="text-rose-400 font-extrabold block text-base">5</span>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Tasks Pending</span>
                </div>
              </div>

              <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                {reg.content_text.slice(0, 220)}
              </p>

              {/* Timeline Lineage & Action Footer */}
              <div className="flex flex-wrap items-center justify-between pt-3 border-t border-slate-800/80 text-xs text-slate-400 gap-3">
                <div className="flex items-center space-x-3 font-mono text-[11px]">
                  <History className="w-3.5 h-3.5 text-brand-400" />
                  <span className="text-slate-500">Lineage:</span>
                  <span className="text-slate-400">2022</span>
                  <span>➔</span>
                  <span className="text-slate-400">2024</span>
                  <span>➔</span>
                  <span className="text-brand-400 font-bold">2026 (v2.0)</span>
                </div>

                <div className="flex items-center space-x-1.5 text-brand-400 font-bold group-hover:translate-x-1 transition-transform">
                  <span>View Full Knowledge Breakdown</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>

              </div>
              {/* Amendment / drift warning banner */}
              {(reg.possible_amendment_detected === 1 || reg.source_url_verified === -1) && (
                <div className="flex items-start gap-2 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[10px]">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <span>
                    {reg.possible_amendment_detected === 1
                      ? 'Possible amendment detected — live source was modified after ingestion. Human review recommended.'
                      : `Source verification issue: ${reg.source_url_verification_note ?? 'live content does not match stored text'}. Overlap score: ${reg.source_url_verification_score?.toFixed(2) ?? 'n/a'}.`
                    }
                  </span>
                </div>
              )}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="p-12 text-center glass-panel rounded-2xl border border-slate-800 space-y-3">
            <FileText className="w-8 h-8 text-slate-600 mx-auto" />
            <p className="text-sm font-semibold text-slate-300">No regulatory documents found</p>
          </div>
        )}
      </div>
    </div>
  );
};
