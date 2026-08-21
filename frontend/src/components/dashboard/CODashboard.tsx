import React, { useState, useEffect } from 'react';
import {
  FileText,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  Building2,
  AlertOctagon,
  HelpCircle,
  FolderLock,
  ChevronRight,
  ShieldAlert
} from 'lucide-react';
import {
  Regulation,
  ComplianceTask,
  TaskStatus,
  CompliancePostureResponse,
  ComplianceAlert,
  PostureStatus
} from '../../types';
import { UserPersona } from '../common/Navbar';
import { apiService } from '../../services/api';
import { ComplianceActionCenter } from './ComplianceActionCenter';

interface CODashboardProps {
  regulations?: Regulation[];
  tasks?: ComplianceTask[];
  onSelectRegulation: (regId: string) => void;
  onUpdateTaskStatus: (taskId: string, status: TaskStatus) => void;
  onNavigate?: (section: string, id?: string) => void;
  onTriggerCrawl?: (sourceId: string) => Promise<any>;
  currentPersona?: UserPersona;
  enterpriseProfile?: any;
}

export const CODashboard: React.FC<CODashboardProps> = ({
  regulations = [],
  tasks = [],
  onSelectRegulation,
  onUpdateTaskStatus,
  onNavigate,
  currentPersona,
  enterpriseProfile
}) => {
  const [posture, setPosture] = useState<CompliancePostureResponse | null>(null);
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);
  const [loadingPosture, setLoadingPosture] = useState<boolean>(true);

  const fetchPostureAndAlerts = async () => {
    setLoadingPosture(true);
    try {
      const [posData, alertData] = await Promise.all([
        apiService.getCompliancePosture().catch(() => null),
        apiService.getComplianceAlerts().catch(() => [])
      ]);
      if (posData) setPosture(posData);
      if (Array.isArray(alertData)) setAlerts(alertData);
    } catch (err) {
      console.error('Error fetching compliance posture/alerts:', err);
    } finally {
      setLoadingPosture(false);
    }
  };

  useEffect(() => {
    fetchPostureAndAlerts();
  }, [enterpriseProfile?.id]);

  const activeSector = enterpriseProfile?.industry_sector || 'ICT & Technology';
  const orgName = enterpriseProfile?.organization_name || 'NEC India';

  const getPostureBadge = (status?: PostureStatus) => {
    switch (status) {
      case 'HEALTHY':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"><ShieldCheck className="w-4 h-4" /> HEALTHY</span>;
      case 'ATTENTION_REQUIRED':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30"><AlertTriangle className="w-4 h-4" /> ATTENTION REQUIRED</span>;
      case 'CRITICAL':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30 animate-pulse"><AlertOctagon className="w-4 h-4" /> CRITICAL</span>;
      case 'REQUIRES_REVIEW':
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30"><HelpCircle className="w-4 h-4" /> REQUIRES REVIEW</span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700"><RefreshCw className="w-3.5 h-3.5 animate-spin" /> EVALUATING</span>;
    }
  };

  if (loadingPosture && !posture) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  const activeAlerts = alerts.filter(a => a.status === 'ACTIVE');

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* LEVEL 1 — EXECUTIVE SUMMARY */}
      
      {/* A. CURRENT POSTURE */}
      <div className="p-6 md:p-8 rounded-2xl bg-gradient-to-br from-slate-900 via-brand-950/40 to-slate-900 border border-brand-500/20 shadow-2xl space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <Building2 className="w-3.5 h-3.5 text-slate-500" /> {orgName}
              </span>
              {currentPersona && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-xs font-semibold text-brand-300 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                    {currentPersona.role} View
                  </span>
                </>
              )}
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              Compliance Posture
            </h1>
            <div className="flex items-center gap-3 mt-2">
              {getPostureBadge(posture?.posture_status)}
            </div>
          </div>
          
          <div className="flex flex-col justify-end space-y-2 text-right">
            <div className="text-sm text-slate-300">
              <strong className="text-white">{posture?.operational_summary.open_count || 0}</strong> active obligations need attention.
            </div>
            <div className="text-sm text-slate-300">
              <strong className="text-white">{posture?.legal_summary.requires_review_count || 0}</strong> assessments require legal review.
            </div>
          </div>
        </div>
      </div>

      {/* B. ACTION REQUIRED (Action Center) */}
      <div className="space-y-3">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-brand-400" /> ACTION REQUIRED
        </h2>
        <ComplianceActionCenter 
          posture={posture} 
          alerts={alerts} 
          tasks={tasks} 
          onOpenTask={(id) => onNavigate && onNavigate('actions', id)}
          onReviewAssessments={() => onNavigate && onNavigate('repository')}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        {currentPersona?.role === 'Legal' || currentPersona?.role === 'Auditor' ? (
          <>
            {/* REGULATORY STATUS FIRST FOR LEGAL/AUDITOR */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-400" /> REGULATORY STATUS
                </h2>
              </div>
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-3xl font-bold text-emerald-400">{posture?.legal_summary.applicable_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Applicable</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-slate-400">{posture?.legal_summary.not_applicable_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Not Applicable</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-amber-400">{posture?.legal_summary.requires_review_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Requires Review</div>
                </div>
              </div>
              <button onClick={() => onNavigate && onNavigate('repository')} className="mt-4 w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2">
                Review Regulatory Assessments <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* TODAY'S COMPLIANCE WORK & EVIDENCE COVERAGE SECOND */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 flex flex-col justify-between">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-bold text-white flex items-center gap-2">
                      <Clock className="w-4 h-4 text-blue-400" /> TODAY'S WORK
                    </h2>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-white">{posture?.operational_summary.open_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Open</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-blue-400">{posture?.operational_summary.in_progress_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">In Progress</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-rose-400">{posture?.operational_summary.blocked_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Blocked</span>
                    </div>
                  </div>
                </div>
                
                <div className="pl-4 border-l border-slate-800">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-bold text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" /> EVIDENCE COVERAGE
                    </h2>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-rose-400">{alerts.filter(a => a.alert_type === 'COMPLETED_WITHOUT_EVIDENCE' || (a.alert_type as string) === 'EVIDENCE_GAP').length}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Evidence Gaps</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-emerald-400">{tasks.filter(t => t.evidence_file_path || t.evidence_url).length}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Tasks with Evidence</span>
                    </div>
                  </div>
                </div>
              </div>
              <button onClick={() => onNavigate && onNavigate('actions')} className="mt-4 w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2">
                Open Task Center <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          <>
            {/* TODAY'S COMPLIANCE WORK & EVIDENCE COVERAGE FIRST FOR OTHERS */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 flex flex-col justify-between">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-bold text-white flex items-center gap-2">
                      <Clock className="w-4 h-4 text-blue-400" /> TODAY'S WORK
                    </h2>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-white">{posture?.operational_summary.open_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Open</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-blue-400">{posture?.operational_summary.in_progress_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">In Progress</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-rose-400">{posture?.operational_summary.blocked_count || 0}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Blocked</span>
                    </div>
                  </div>
                </div>
                
                <div className="pl-4 border-l border-slate-800">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-bold text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" /> EVIDENCE COVERAGE
                    </h2>
                  </div>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-rose-400">{alerts.filter(a => a.alert_type === 'COMPLETED_WITHOUT_EVIDENCE' || (a.alert_type as string) === 'EVIDENCE_GAP').length}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Evidence Gaps</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-emerald-400">{tasks.filter(t => t.evidence_file_path || t.evidence_url).length}</span>
                      <span className="text-xs font-semibold text-slate-400 uppercase">Tasks with Evidence</span>
                    </div>
                  </div>
                </div>
              </div>
              <button onClick={() => onNavigate && onNavigate('actions')} className="mt-4 w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2">
                Open Task Center <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* REGULATORY STATUS SECOND */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-indigo-400" /> REGULATORY STATUS
                </h2>
              </div>
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-3xl font-bold text-emerald-400">{posture?.legal_summary.applicable_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Applicable</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-slate-400">{posture?.legal_summary.not_applicable_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Not Applicable</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-amber-400">{posture?.legal_summary.requires_review_count || 0}</div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">Requires Review</div>
                </div>
              </div>
              <button onClick={() => onNavigate && onNavigate('repository')} className="mt-4 w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition flex items-center justify-center gap-2">
                Review Regulatory Assessments <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </>
        )}
      </div>

      {/* E. RECENT ACTIVITY */}
      <div className="pt-4 space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <RefreshCw className="w-4 h-4 text-slate-400" /> RECENT ACTIVITY
        </h2>
        <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 text-center">
          <div className="text-sm text-slate-400 mb-4">No recent activity found.</div>
          <button onClick={() => onNavigate && onNavigate('audit')} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl transition inline-flex items-center justify-center gap-2">
            View Audit Log
          </button>
        </div>
      </div>
    </div>
  );
};
