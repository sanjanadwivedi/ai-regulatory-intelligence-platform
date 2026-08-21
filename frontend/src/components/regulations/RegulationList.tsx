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
  const [selectedSector, setSelectedSector] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest' | 'a-z'>('newest');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  const authorities = ['ALL', ...Array.from(new Set(regulations.map((r) => r.authority))).filter(Boolean)];
  const sectors = ['ALL', ...Array.from(new Set(regulations.map((r) => r.sector))).filter(Boolean)];
  const statuses = ['ALL', ...Array.from(new Set(regulations.map((r) => r.status))).filter(Boolean)];

  let filtered = regulations.filter((reg) => {
    const matchesSearch =
      reg.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reg.authority.toLowerCase().includes(searchTerm.toLowerCase()) ||
      reg.content_text.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesAuth = selectedAuthority === 'ALL' || reg.authority === selectedAuthority;
    const matchesSector = selectedSector === 'ALL' || reg.sector === selectedSector;
    const matchesStatus = selectedStatus === 'ALL' || reg.status === selectedStatus;

    return matchesSearch && matchesAuth && matchesSector && matchesStatus;
  });

  filtered.sort((a, b) => {
    if (sortOrder === 'newest') return new Date(b.publication_date).getTime() - new Date(a.publication_date).getTime();
    if (sortOrder === 'oldest') return new Date(a.publication_date).getTime() - new Date(b.publication_date).getTime();
    if (sortOrder === 'a-z') return a.title.localeCompare(b.title);
    return 0;
  });

  const totalPages = Math.ceil(filtered.length / itemsPerPage);
  const paginatedRegs = filtered.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="flex flex-col xl:flex-row items-stretch xl:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search regulations by title, authority, keyword, circular number..."
            value={searchTerm}
            onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={selectedAuthority}
            onChange={(e) => { setSelectedAuthority(e.target.value); setCurrentPage(1); }}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 transition-colors"
          >
            {authorities.map((auth, i) => (
              <option key={i} value={auth}>
                {auth === 'ALL' ? 'All Authorities' : auth}
              </option>
            ))}
          </select>

          <select
            value={selectedSector}
            onChange={(e) => { setSelectedSector(e.target.value); setCurrentPage(1); }}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 transition-colors"
          >
            {sectors.map((sec, i) => (
              <option key={i} value={sec}>
                {sec === 'ALL' ? 'All Sectors' : sec}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => { setSelectedStatus(e.target.value); setCurrentPage(1); }}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 transition-colors"
          >
            {statuses.map((stat, i) => (
              <option key={i} value={stat}>
                {stat === 'ALL' ? 'All Statuses' : stat}
              </option>
            ))}
          </select>

          <select
            value={sortOrder}
            onChange={(e) => { setSortOrder(e.target.value as any); setCurrentPage(1); }}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 transition-colors"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="a-z">A-Z</option>
          </select>
        </div>
      </div>

      {/* Compact Table Layout for Regulatory Repository */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-950/50 border-b border-slate-800 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="px-4 py-3 font-semibold">Regulation</th>
                <th className="px-4 py-3 font-semibold">Authority</th>
                <th className="px-4 py-3 font-semibold">Status / Verified</th>
                <th className="px-4 py-3 font-semibold text-center">Applicability</th>
                <th className="px-4 py-3 font-semibold text-center">Obligations</th>
                <th className="px-4 py-3 font-semibold">Last Updated</th>
                <th className="px-4 py-3 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {paginatedRegs.map((reg) => {
                const sourceUrl = getOfficialSourceUrl(reg);
                const requirementsCount = reg.sections ? reg.sections.reduce((acc, s) => acc + (s.obligations?.length || 1), 0) : 0;
                
                return (
                  <tr 
                    key={reg.id}
                    onClick={() => onSelectRegulation(reg.id)}
                    className="hover:bg-slate-800/50 transition-colors cursor-pointer group"
                  >
                    <td className="px-4 py-3 max-w-[300px]">
                      <div className="flex items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-bold text-white truncate group-hover:text-brand-300 transition-colors">
                            {reg.title}
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-slate-400 font-mono truncate">{reg.doc_number || "Generic Cyber Circular"}</span>
                          </div>
                          {(reg.possible_amendment_detected === 1 || reg.source_url_verified === -1) && (
                            <div className="text-[9px] text-amber-400 font-medium flex items-center gap-1 mt-1 truncate">
                              <AlertTriangle className="w-2.5 h-2.5" />
                              {reg.possible_amendment_detected === 1 ? 'Possible Amendment' : 'Source Drift'}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700 rounded whitespace-nowrap">
                        {reg.authority}
                      </span>
                    </td>
                    <td className="px-4 py-3 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${reg.status === 'ACTIVE' ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                        <span className="text-xs font-semibold text-slate-300">{reg.status}</span>
                      </div>
                      <div className="flex items-center">
                        <SourceVerificationBadge reg={reg} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {reg.needs_human_review ? (
                        <span className="inline-flex px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-bold rounded">Needs Review</span>
                      ) : (
                        <span className="inline-flex px-2 py-0.5 bg-brand-500/10 text-brand-400 border border-brand-500/20 text-[10px] font-bold rounded">Assessed</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-sm font-bold text-emerald-400">{requirementsCount}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
                        <History className="w-3 h-3 text-slate-500" />
                        {reg.effective_date || reg.publication_date || 'N/A'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {sourceUrl && (
                          <a
                            href={sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded transition-colors"
                            title="Verify Official Source"
                          >
                            <ShieldCheck className="w-4 h-4" />
                          </a>
                        )}
                        <button className="flex items-center gap-1 text-xs font-bold text-brand-400 group-hover:text-brand-300 transition-colors">
                          View <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="p-12 text-center border-t border-slate-800">
            <FileText className="w-8 h-8 text-slate-600 mx-auto" />
            <p className="mt-3 text-sm font-semibold text-slate-300">No regulatory documents found</p>
          </div>
        )}
      </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between py-4 border-t border-slate-800 mt-6">
            <span className="text-xs text-slate-400">
              Showing {(currentPage - 1) * itemsPerPage + 1} - {Math.min(currentPage * itemsPerPage, filtered.length)} of {filtered.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs disabled:opacity-50 hover:bg-slate-700 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs font-bold text-white px-2">Page {currentPage} of {totalPages}</span>
              <button
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs disabled:opacity-50 hover:bg-slate-700 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
    </div>
  );
};
