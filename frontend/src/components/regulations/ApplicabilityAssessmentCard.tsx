import React from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FileText,
  Building2,
  Globe,
  ExternalLink,
  Sparkles,
  HelpCircle
} from 'lucide-react';
import { RegulatoryApplicabilityAssessment } from '../../types';

interface ApplicabilityAssessmentCardProps {
  assessment: RegulatoryApplicabilityAssessment;
  onReevaluate?: () => void;
  isLoading?: boolean;
}

export const ApplicabilityAssessmentCard: React.FC<ApplicabilityAssessmentCardProps> = ({
  assessment,
  onReevaluate,
  isLoading
}) => {
  const getStatusBadge = () => {
    switch (assessment.status) {
      case 'APPLICABLE':
        return {
          icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
          label: 'Statutorily Applicable',
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
          desc: 'Authoritative statutory criteria satisfied based on confirmed organization profile.'
        };
      case 'NOT_APPLICABLE':
        return {
          icon: <ShieldOff className="w-5 h-5 text-slate-400" />,
          label: 'Not Applicable',
          bg: 'bg-slate-800/80 border-slate-700 text-slate-300',
          desc: 'Organization operates outside the statutory territorial or covered entity scope.'
        };
      case 'REQUIRES_REVIEW':
      default:
        return {
          icon: <ShieldAlert className="w-5 h-5 text-amber-400" />,
          label: 'Requires Review',
          bg: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
          desc: 'Statutory criteria incomplete or ambiguous. Human regulatory review required.'
        };
    }
  };

  const badge = getStatusBadge();

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-xl backdrop-blur-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-400">
              Regulatory Applicability Determination
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              ({assessment.engine_version})
            </span>
          </div>
          <h3 className="text-xl font-bold text-white">
            {assessment.regulation_title || 'Applicability Assessment'}
          </h3>
          <p className="text-xs text-slate-400">
            {assessment.regulation_authority} &middot; Region: {assessment.regulation_region || 'National'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className={`px-4 py-2 rounded-xl border flex items-center gap-2.5 font-semibold text-sm ${badge.bg}`}>
            {badge.icon}
            <span>{badge.label}</span>
          </div>
        </div>
      </div>

      {/* Rationale / Summary */}
      <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-400" />
          Assessment Summary
        </div>
        <p className="text-sm text-slate-300 whitespace-pre-line leading-relaxed">
          {assessment.rationale}
        </p>
      </div>

      {/* Matched Criteria */}
      {assessment.matched_criteria && assessment.matched_criteria.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            Matched Statutory Criteria
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {assessment.matched_criteria.map((c, idx) => (
              <div key={idx} className="p-3.5 rounded-xl bg-slate-950/40 border border-emerald-500/20 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-semibold text-white">
                  <span>{c.criterion_name}</span>
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    MATCH
                  </span>
                </div>
                <p className="text-xs text-slate-300">{c.evidence}</p>
                {c.authoritative_source && (
                  <p className="text-[11px] text-slate-500 italic">
                    Source: {c.authoritative_source}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unmet Criteria */}
      {assessment.unmet_criteria && assessment.unmet_criteria.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-400" />
            Unmet Scope Criteria / Authoritative Exclusions
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {assessment.unmet_criteria.map((u, idx) => (
              <div key={idx} className="p-3.5 rounded-xl bg-slate-950/40 border border-slate-800 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                  <span>{u.criterion_name}</span>
                  <span className="text-[10px] text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                    NO MATCH
                  </span>
                </div>
                <p className="text-xs text-slate-400">{u.reason}</p>
                {u.authoritative_source && (
                  <p className="text-[11px] text-slate-500 italic">
                    Authority: {u.authoritative_source}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing Information / Human Review Required Notice */}
      {assessment.missing_information && assessment.missing_information.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
            <AlertTriangle className="w-4 h-4" />
            Human Review Required & Missing Determination
          </div>
          <ul className="space-y-2 text-xs text-slate-300">
            {assessment.missing_information.map((item, idx) => (
              <li key={item.criterion_id || idx} className="leading-relaxed bg-amber-950/30 p-3 rounded-xl border border-amber-500/20 space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-amber-300">{item.criterion || 'Pending Criterion'}</div>
                  {item.is_mandatory && (
                    <span className="text-[10px] text-amber-200 bg-amber-500/20 px-2 py-0.5 rounded border border-amber-500/30">MANDATORY</span>
                  )}
                </div>
                {item.question && (
                  <p className="text-slate-300">
                    <span className="text-amber-500/70 font-medium">Question:</span> {item.question}
                  </p>
                )}
                {item.reason && (
                  <p className="text-slate-400 italic">
                    {item.reason}
                  </p>
                )}
                {item.evidence_required && (
                  <p className="text-[11px] text-slate-400">
                    <span className="text-slate-500">Evidence Required:</span> {item.evidence_required}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-amber-400/80 italic pt-1">
            Disclaimer: Applicability could not be conclusively established from the available authoritative criteria. Human regulatory review is required.
          </p>
        </div>
      )}

      {/* Three Segregated Evidence Layers */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-2 border-t border-slate-800/80">
        {/* Layer 1: Organization Evidence */}
        <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-blue-400 flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5" />
            Organization Evidence
          </div>
          {assessment.organization_evidence_refs && assessment.organization_evidence_refs.length > 0 ? (
            <div className="space-y-2">
              {assessment.organization_evidence_refs.map((ref, idx) => (
                <div key={idx} className="text-xs text-slate-300 bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
                  <span className="font-semibold text-white">{ref.value}</span>
                  <div className="text-[10px] text-slate-500">{ref.source}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">Derived from confirmed enterprise profile attributes.</p>
          )}
        </div>

        {/* Layer 2: Regulatory Evidence */}
        <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5" />
            Regulatory Evidence
          </div>
          {assessment.regulatory_evidence_refs && assessment.regulatory_evidence_refs.length > 0 ? (
            <div className="space-y-2">
              {assessment.regulatory_evidence_refs.map((ref, idx) => (
                <div key={idx} className="text-xs text-slate-300 bg-slate-900/60 p-2 rounded-lg border border-slate-800/50 space-y-1">
                  <div className="font-semibold text-white truncate">{ref.authority}</div>
                  <div className="text-[11px] text-slate-400">Region: {ref.statutory_region}</div>
                  {ref.source_url && (
                    <a
                      href={ref.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[10px] text-brand-400 hover:text-brand-300 flex items-center gap-1"
                    >
                      Official Source <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No regulatory source metadata attached.</p>
          )}
        </div>

        {/* Layer 3: Regulatory Signal Evidence */}
        <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Discovered Signals
          </div>
          {assessment.regulatory_signal_refs && assessment.regulatory_signal_refs.length > 0 ? (
            <div className="space-y-2">
              {assessment.regulatory_signal_refs.map((sig, idx) => (
                <div key={idx} className="text-xs text-slate-300 bg-slate-900/60 p-2 rounded-lg border border-cyan-500/20 space-y-1">
                  <div className="font-semibold text-cyan-300">{sig.signal_name}</div>
                  <p className="text-[11px] text-slate-400 italic leading-snug">"{sig.evidence_quote}"</p>
                  <p className="text-[10px] text-cyan-400/70 pt-0.5">{sig.interpretation}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No website regulatory signals matched for this regulation family.</p>
          )}
        </div>
      </div>
    </div>
  );
};
