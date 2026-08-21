import React, { useState, useMemo } from 'react';
import { ComplianceAlert, ComplianceTask, CompliancePostureResponse, AlertSeverity } from '../../types';
import { AlertTriangle, AlertOctagon, CheckCircle, Clock, ShieldAlert, ArrowRight, CheckCircle2, ChevronRight, XCircle } from 'lucide-react';
import { ReasoningDrawer } from '../common/ReasoningDrawer';

interface ComplianceActionCenterProps {
  posture: CompliancePostureResponse | null;
  alerts: ComplianceAlert[];
  tasks: ComplianceTask[];
  onOpenTask: (taskId: string) => void;
  onReviewAssessments: () => void;
}

export interface UnifiedAction {
  id: string;
  type: string;
  title: string;
  why: string;
  source: string;
  severity: AlertSeverity;
  priority_rank: number;
  action_label: string;
  action_handler: () => void;
  context_data?: any;
}

export const ComplianceActionCenter: React.FC<ComplianceActionCenterProps> = ({
  posture,
  alerts,
  tasks,
  onOpenTask,
  onReviewAssessments
}) => {
  const [showAll, setShowAll] = useState(false);
  const [reasoningData, setReasoningData] = useState<any>(null);

  const actions = useMemo(() => {
    const act: UnifiedAction[] = [];

    // 1. Map Alerts to actions
    alerts.filter(a => a.status === 'ACTIVE').forEach(a => {
      let priority = 7;
      let why = a.description;
      let actionLabel = 'Review Task';
      let actionHandler = () => onOpenTask(a.task_id || a.source_entity_id || '');
      
      let displayTitle = a.title;
      // Hide technical IDs like OBL-CERTIN-POC-DESIGNATION
      if (displayTitle.includes('for Obligation OBL-') || displayTitle.includes('OBL-')) {
        displayTitle = displayTitle.split('for Obligation')[0].trim();
        if (displayTitle === 'Evidence Gap' || displayTitle === 'Evidence gap') {
          displayTitle = a.context_data?.task_title || 'Regulatory requirement';
        }
      }
      if (!displayTitle || displayTitle.match(/^OBL-|^TASK-/)) {
        displayTitle = 'Regulatory item requires review';
      }

      if (a.severity === 'CRITICAL') priority = 1;
      else if (a.alert_type as string === 'EVIDENCE_GAP' || a.alert_type === 'COMPLETED_WITHOUT_EVIDENCE') {
        priority = 4;
        why = 'Operational evidence is missing for this task.';
      }
      else if (a.alert_type as string === 'LEGAL_REVIEW_REQUIRED' || a.alert_type === 'REVIEW_REQUIRED') priority = 5;
      else if (a.alert_type as string === 'MISSING_TRIGGER_INFORMATION' || a.alert_type === 'MISSING_TRIGGER_METADATA') priority = 6;
      else if (a.severity === 'HIGH') priority = 3;

      act.push({
        id: a.id,
        type: a.alert_type.replace(/_/g, ' '),
        title: displayTitle,
        why: why,
        source: 'Automated Monitoring',
        severity: a.severity,
        priority_rank: priority,
        action_label: actionLabel,
        action_handler: actionHandler,
        context_data: a
      });
    });

    // Deduplicate Legal Reviews
    const reviewAlerts = act.filter(a => a.priority_rank === 5);
    const nonReviewAlerts = act.filter(a => a.priority_rank !== 5);

    const finalActions: UnifiedAction[] = [...nonReviewAlerts];

    if (reviewAlerts.length > 0) {
      finalActions.push({
        id: 'group_review',
        type: 'LEGAL REVIEW REQUIRED',
        title: `${reviewAlerts.length} assessments require legal review.`,
        why: 'Authoritative applicability criteria are incomplete or inconclusive. Legal review is required.',
        source: 'Applicability Engine',
        severity: 'HIGH',
        priority_rank: 5,
        action_label: 'Review Assessments',
        action_handler: onReviewAssessments,
      });
    }

    // Sort by priority rank
    finalActions.sort((a, b) => a.priority_rank - b.priority_rank);
    return finalActions;
  }, [alerts, onReviewAssessments]);

  const getSeverityIcon = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return <AlertOctagon className="w-5 h-5 text-rose-400" />;
      case 'HIGH': return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case 'MEDIUM': return <ShieldAlert className="w-5 h-5 text-blue-400" />;
      default: return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getSeverityStyle = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return 'bg-rose-500/10 border-rose-500/30';
      case 'HIGH': return 'bg-amber-500/10 border-amber-500/30';
      default: return 'bg-slate-800/50 border-slate-700';
    }
  };

  const displayedActions = showAll ? actions : actions.slice(0, 3);

  return (
    <div className="space-y-4">
      {actions.length === 0 ? (
        <div className="p-8 text-center rounded-xl bg-slate-900 border border-slate-800">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <div className="text-sm font-bold text-white">No Priority Actions Required</div>
          <div className="text-xs text-slate-400">All compliance operations are up to date.</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3">
            {displayedActions.map(action => (
              <div key={action.id} className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-start justify-between gap-4 transition ${getSeverityStyle(action.severity)}`}>
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    {getSeverityIcon(action.severity)}
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-300">{action.type}</span>
                  </div>
                  <h4 className="text-base font-bold text-white">{action.title}</h4>
                  
                  <div className="pt-1 space-y-1">
                    <div className="text-xs font-semibold text-slate-400">Why:</div>
                    <div className="text-sm text-slate-300 leading-relaxed">{action.why}</div>
                  </div>

                  {action.source && (
                    <div className="pt-1">
                      <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">Source: </span>
                      <span className="text-xs text-slate-400">{action.source}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 md:self-end">
                  <button
                    onClick={() => setReasoningData({ type: 'ALERT', data: action.context_data })}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 border border-slate-700 transition"
                  >
                    Why?
                  </button>
                  <button
                    onClick={action.action_handler}
                    className="px-4 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-400 text-slate-950 text-xs font-bold shadow-md transition flex items-center gap-1.5"
                  >
                    {action.action_label} <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          {actions.length > 3 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full py-2 text-xs font-bold text-slate-400 hover:text-white bg-slate-900 border border-slate-800 rounded-xl transition flex items-center justify-center gap-2"
            >
              {showAll ? 'Collapse Actions' : `View All Actions (${actions.length})`} <ChevronRight className={`w-3.5 h-3.5 transform transition ${showAll ? '-rotate-90' : 'rotate-90'}`} />
            </button>
          )}
        </>
      )}

      {reasoningData && (
        <ReasoningDrawer 
          data={reasoningData} 
          onClose={() => setReasoningData(null)} 
        />
      )}
    </div>
  );
};
