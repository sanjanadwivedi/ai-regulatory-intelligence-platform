import React from 'react';
import { History, CheckCircle2, Clock, Calendar, ArrowRight, ShieldCheck } from 'lucide-react';

export interface TimelineMilestone {
  year: string;
  date: string;
  title: string;
  version: string;
  status: 'ACTIVE_ENFORCED' | 'SUPERSEDED' | 'PROPOSED';
  summary: string;
  affected_policies: string[];
  completed_task_count: number;
}

interface RegulatoryTimelineProps {
  milestones?: TimelineMilestone[];
}

const DEFAULT_MILESTONES: TimelineMilestone[] = [
  {
    year: '2026',
    date: 'July 15, 2026',
    title: 'Master Direction Amendment – Mandatory 2-Year Cadence & 24-Hr FIU Threshold',
    version: 'v2.0',
    status: 'ACTIVE_ENFORCED',
    summary: 'Shortened high-risk KYC re-verification cadence to 24 months and mandated encrypted V-CIP geotagging logs.',
    affected_policies: ['POL-KYC-2026 (v3.2)', 'SOP-KYC-3.2', 'CTRL-KYC-04'],
    completed_task_count: 4
  },
  {
    year: '2024',
    date: 'May 10, 2024',
    title: 'V-CIP Digital Onboarding Framework Introduction',
    version: 'v1.5',
    status: 'SUPERSEDED',
    summary: 'Introduced initial video-based identification guidelines for remote customer onboarding.',
    affected_policies: ['POL-KYC-2024 (v2.1)', 'CTRL-KYC-02'],
    completed_task_count: 8
  },
  {
    year: '2022',
    date: 'January 20, 2022',
    title: 'Master Direction – Know Your Customer (KYC) Baseline Issue',
    version: 'v1.0',
    status: 'SUPERSEDED',
    summary: 'Established baseline periodic re-verification requirements (3-year high risk / 8-year low risk).',
    affected_policies: ['POL-KYC-2022 (v1.0)'],
    completed_task_count: 12
  }
];

export const RegulatoryTimeline: React.FC<RegulatoryTimelineProps> = ({
  milestones = DEFAULT_MILESTONES,
}) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <History className="w-5 h-5 text-brand-400" />
            Regulatory Amendment History & Time-Travel Lineage
          </h2>
          <p className="text-xs text-slate-400">
            Chronological audit evolution of statutory amendments, policy revisions, and completed compliance tasks.
          </p>
        </div>
      </div>

      {/* Timeline Steps */}
      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">
        {milestones.map((m, idx) => (
          <div key={idx} className="relative group">
            {/* Timeline Dot */}
            <div className={`absolute -left-6 top-1.5 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-bold ${
              m.status === 'ACTIVE_ENFORCED'
                ? 'border-emerald-500 bg-emerald-950 text-emerald-300 ring-4 ring-emerald-500/20'
                : 'border-slate-700 bg-slate-900 text-slate-400'
            }`}>
              {idx + 1}
            </div>

            {/* Timeline Card */}
            <div className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-3 shadow-lg">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-brand-400 font-mono">{m.year}</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs text-slate-400">{m.date}</span>
                    <span className="text-slate-600">•</span>
                    <span className="px-2 py-0.5 text-[10px] font-mono bg-slate-900 text-slate-300 rounded border border-slate-800 font-bold">
                      {m.version}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-white">{m.title}</h3>
                </div>

                <span className={`px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full self-start sm:self-auto border ${
                  m.status === 'ACTIVE_ENFORCED'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}>
                  {m.status.replace('_', ' ')}
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{m.summary}</p>

              <div className="pt-2 flex flex-wrap items-center justify-between gap-4 text-xs border-t border-slate-800/80">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-slate-500 text-[10px] font-semibold">Affected Policies:</span>
                  {m.affected_policies.map((pol, pIdx) => (
                    <span key={pIdx} className="px-2 py-0.5 text-[10px] bg-slate-900 text-brand-300 font-mono rounded border border-slate-800">
                      {pol}
                    </span>
                  ))}
                </div>

                <div className="flex items-center space-x-1.5 text-emerald-400 font-semibold text-[11px]">
                  <ShieldCheck className="w-4 h-4" />
                  <span>{m.completed_task_count} Tasks Completed & Audited</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
