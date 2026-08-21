import React from 'react';
import {
  FileCheck2,
  Clock,
  Shield,
  Building2,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Users,
  Repeat,
  Scale,
  Calendar
} from 'lucide-react';
import { RegulatoryObligation } from '../../types';

interface RegulatoryObligationCardProps {
  obligation: RegulatoryObligation;
}

export const RegulatoryObligationCard: React.FC<RegulatoryObligationCardProps> = ({ obligation }) => {
  const getStatusBadge = () => {
    switch (obligation.status) {
      case 'ACTIVE':
        return {
          label: 'Active Obligation',
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          icon: <CheckCircle2 className="w-3.5 h-3.5" />
        };
      case 'REQUIRES_REVIEW':
        return {
          label: 'Requires Review',
          bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
          icon: <AlertCircle className="w-3.5 h-3.5" />
        };
      case 'SUPERSEDED':
      default:
        return {
          label: 'Superseded',
          bg: 'bg-slate-800 border-slate-700 text-slate-400',
          icon: <Shield className="w-3.5 h-3.5" />
        };
    }
  };

  const getPriorityBadge = () => {
    switch (obligation.priority) {
      case 'CRITICAL':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'HIGH':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'MEDIUM':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  const statusBadge = getStatusBadge();

  return (
    <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-4 hover:border-slate-700 transition-all shadow-md">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-slate-800/60">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-brand-500/10 text-brand-400 border border-brand-500/20">
              {obligation.obligation_code}
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
              {obligation.obligation_type}
            </span>
          </div>
          <h4 className="text-base font-bold text-white tracking-tight">
            {obligation.title}
          </h4>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 ${statusBadge.bg}`}>
            {statusBadge.icon}
            {statusBadge.label}
          </span>
          <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${getPriorityBadge()}`}>
            {obligation.priority}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-300 leading-relaxed">
        {obligation.description}
      </p>

      {/* Key Specifications Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
        {obligation.due_rule && (
          <div className="p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Clock className="w-3 h-3 text-amber-400" />
              Statutory Due Rule
            </span>
            <p className="font-semibold text-slate-200 text-xs truncate" title={obligation.due_rule}>
              {obligation.due_rule}
            </p>
          </div>
        )}

        {obligation.frequency && (
          <div className="p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Repeat className="w-3 h-3 text-blue-400" />
              Frequency
            </span>
            <p className="font-semibold text-slate-200 text-xs">
              {obligation.frequency}
            </p>
          </div>
        )}

        {obligation.responsible_function && (
          <div className="p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Users className="w-3 h-3 text-purple-400" />
              Responsible Function
            </span>
            <p className="font-semibold text-slate-200 text-xs truncate" title={obligation.responsible_function}>
              {obligation.responsible_function}
            </p>
          </div>
        )}

        {obligation.effective_date && (
          <div className="p-2.5 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Calendar className="w-3 h-3 text-emerald-400" />
              Effective Date
            </span>
            <p className="font-semibold text-slate-200 text-xs">
              {obligation.effective_date}
            </p>
          </div>
        )}
      </div>

      {/* Statutory Citation & Authoritative Source Link */}
      <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div className="space-y-0.5">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1">
            <Scale className="w-3 h-3 text-brand-400" />
            Statutory Citation
          </span>
          <p className="font-mono text-xs text-slate-200">
            {obligation.source_citation}
          </p>
        </div>

        {obligation.authoritative_source_url && (
          <a
            href={obligation.authoritative_source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 self-start sm:self-center font-semibold"
          >
            Authoritative Source <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {/* Segregated Evidence Provenance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        {/* Authoritative Regulatory Evidence */}
        <div className="p-3 rounded-xl bg-slate-950/30 border border-purple-500/20 space-y-1 text-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400">
            Authoritative Regulatory Evidence
          </span>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Statutory requirement mandated under Section 70B(6) of IT Act, 2000 directions issued by CERT-In.
          </p>
        </div>

        {/* Organization Context Evidence */}
        <div className="p-3 rounded-xl bg-slate-950/30 border border-blue-500/20 space-y-1 text-xs">
          <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400">
            Organization Context Evidence
          </span>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Applies to confirmed organization presence in India operating Cloud & ICT solutions.
          </p>
        </div>
      </div>
    </div>
  );
};
