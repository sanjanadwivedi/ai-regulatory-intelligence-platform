import React, { useState } from 'react';
import {
  Plus,
  CheckCircle2,
  User,
  ShieldCheck,
  ArrowRight,
  Layers,
  Sparkles,
  ExternalLink,
  Clock,
  Building2,
  FileCheck,
  AlertCircle,
  X,
  RefreshCw,
  Scale,
  Zap,
  Paperclip,
  Activity,
  AlertTriangle
} from 'lucide-react';
import { ComplianceTask, TaskStatus } from '../../types';
import { Badge } from '../common/Badge';
import { apiService } from '../../services/api';
import { ComplianceTaskDetail } from './ComplianceTaskDetail';
import { RecordTriggerModal } from './RecordTriggerModal';

interface TaskKanbanBoardProps {
  tasks: ComplianceTask[];
  onUpdateStatus: (taskId: string, status: TaskStatus) => void;
  onCreateTaskClick: () => void;
  onTasksGenerated?: () => void;
}

export const TaskKanbanBoard: React.FC<TaskKanbanBoardProps> = ({
  tasks,
  onUpdateStatus,
  onCreateTaskClick,
  onTasksGenerated,
}) => {
  const [filterType, setFilterType] = useState<'ALL' | 'STATUTORY' | 'MANUAL'>('ALL');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<string | null>(null);
  const [selectedTaskForDetail, setSelectedTaskForDetail] = useState<ComplianceTask | null>(null);
  const [isTriggerModalOpen, setIsTriggerModalOpen] = useState(false);

  const handleGenerateTasks = async () => {
    setIsGenerating(true);
    setGenerateMsg(null);
    try {
      const generated = await apiService.generateComplianceTasks();
      setGenerateMsg(`Successfully generated ${generated.length} compliance tasks from ACTIVE obligations.`);
      if (onTasksGenerated) {
        onTasksGenerated();
      }
    } catch (err: any) {
      setGenerateMsg(err.response?.data?.detail || 'Failed to generate tasks from active obligations.');
    } finally {
      setIsGenerating(false);
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (filterType === 'STATUTORY') return !!t.regulatory_obligation_id;
    if (filterType === 'MANUAL') return !t.regulatory_obligation_id;
    return true;
  });

  const columns: { id: TaskStatus; label: string; color: string; border: string }[] = [
    { id: 'OPEN', label: 'Open / Needs Review', color: 'bg-amber-500/10 text-amber-300', border: 'border-amber-500/40' },
    { id: 'IN_PROGRESS', label: 'In Progress / Assigned', color: 'bg-sky-500/10 text-sky-300', border: 'border-sky-500/40' },
    { id: 'BLOCKED', label: 'Blocked / Under Audit', color: 'bg-red-500/10 text-red-300', border: 'border-red-500/40' },
    { id: 'COMPLETED', label: 'Completed', color: 'bg-emerald-500/10 text-emerald-300', border: 'border-emerald-500/40' },
  ];

  const isSparseLayout = filteredTasks.length < 8;

  return (
    <div className="space-y-6">
      {/* Top Action & Generation Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-brand-950/40 to-slate-900 border border-brand-500/20 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-white tracking-tight">Compliance Execution & Monitoring Engine</h1>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/30">
              v1.0.0-deterministic
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl">
            Orchestrate operational tasks instantiated strictly from <span className="text-emerald-400 font-semibold">ACTIVE</span> statutory obligations. Preserves authoritative citations and strict deadline safety.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsTriggerModalOpen(true)}
            className="flex items-center space-x-2 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-semibold text-xs px-3.5 py-2.5 rounded-xl shadow-lg shadow-amber-600/20 transition-all cursor-pointer"
          >
            <Zap className="w-4 h-4 text-amber-200" />
            <span>Record Trigger Event</span>
          </button>

          <button
            onClick={handleGenerateTasks}
            disabled={isGenerating}
            className="flex items-center space-x-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-semibold text-xs px-3.5 py-2.5 rounded-xl shadow-lg shadow-emerald-600/20 transition-all cursor-pointer"
          >
            {isGenerating ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4 text-emerald-200" />
            )}
            <span>{isGenerating ? 'Generating Tasks...' : 'Instantiate from Obligations'}</span>
          </button>

          <button
            onClick={onCreateTaskClick}
            className="flex items-center space-x-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs px-3.5 py-2.5 rounded-xl border border-slate-700 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>New Manual Task</span>
          </button>
        </div>
      </div>

      {generateMsg && (
        <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{generateMsg}</span>
          </div>
          <button onClick={() => setGenerateMsg(null)} className="text-emerald-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setFilterType('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              filterType === 'ALL'
                ? 'bg-brand-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            All Tasks ({tasks.length})
          </button>
          <button
            onClick={() => setFilterType('STATUTORY')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              filterType === 'STATUTORY'
                ? 'bg-brand-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Scale className="w-3.5 h-3.5 text-brand-300" />
            Statutory Obligations ({tasks.filter((t) => !!t.regulatory_obligation_id).length})
          </button>
          <button
            onClick={() => setFilterType('MANUAL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              filterType === 'MANUAL'
                ? 'bg-brand-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <User className="w-3.5 h-3.5 text-slate-400" />
            Manual Tasks ({tasks.filter((t) => !t.regulatory_obligation_id).length})
          </button>
        </div>
      </div>

      {/* Conditional Layout */}
      {isSparseLayout ? (
        <div className="space-y-4">
          <div className="flex items-center gap-4 bg-slate-900 p-4 rounded-xl border border-slate-800">
            {columns.map(col => {
              const count = filteredTasks.filter((t) => {
                if (col.id === 'OPEN') return t.status === 'OPEN' || t.status === 'NEEDS_REVIEW' || t.status === 'NEW' || t.status === 'REOPENED';
                if (col.id === 'IN_PROGRESS') return t.status === 'IN_PROGRESS' || t.status === 'MY_TASKS' || t.status === 'DUE_TODAY' || t.status === 'WAITING_APPROVAL';
                return t.status === col.id;
              }).length;
              return (
                <div key={col.id} className="flex flex-col items-center flex-1 border-r last:border-0 border-slate-800">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{col.label.split(' / ')[0]}</span>
                  <span className={`text-xl font-bold ${count > 0 ? col.color.split(' ')[1] : 'text-slate-600'}`}>{count}</span>
                </div>
              );
            })}
          </div>
          <div className="flex flex-col gap-3 mt-4">
            {filteredTasks.map((task) => {
              const isStatutory = !!task.regulatory_obligation_id;
              return (
                <div
                  key={task.id}
                  onClick={() => setSelectedTaskForDetail(task)}
                  className={`p-3 rounded-xl bg-slate-900 border flex items-center justify-between transition shadow-sm cursor-pointer group ${
                    task.is_overdue
                      ? 'border-red-500/50 hover:border-red-400'
                      : isStatutory
                      ? 'border-brand-500/30 hover:border-brand-400/60'
                      : 'border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className="flex flex-col gap-1 w-[140px] shrink-0">
                      {isStatutory ? (
                        <span className="text-[9px] font-bold text-brand-400 uppercase tracking-wider flex items-center gap-1">
                          <Scale className="w-3 h-3" /> STATUTORY REQUIREMENT
                        </span>
                      ) : (
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                          <User className="w-3 h-3" /> INTERNAL / OPERATIONAL
                        </span>
                      )}
                      <Badge level={task.priority}>{task.priority}</Badge>
                    </div>
                    
                    <div className="flex-1">
                      <h3 className="text-sm font-bold text-white group-hover:text-brand-300 transition-colors truncate">
                        {task.title}
                      </h3>
                      <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-400">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3 text-slate-500 shrink-0" />
                          {task.responsible_function || task.assignee}
                        </span>
                        {task.due_date && (
                          <span className={`flex items-center gap-1 ${new Date(task.due_date) < new Date() ? 'text-rose-400' : ''}`}>
                            <Clock className="w-3 h-3 shrink-0" />
                            {new Date(task.due_date) < new Date() ? 'OVERDUE: ' : 'Due: '}{task.due_date}
                          </span>
                        )}
                        {task.status === 'COMPLETED' && (task.evidence_file_path || task.evidence_url) && (
                          <span className="flex items-center gap-1 text-emerald-400 font-bold bg-emerald-950/50 px-1.5 py-0.5 rounded">
                            <ShieldCheck className="w-3 h-3" /> EVIDENCE ATTACHED
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="shrink-0 flex items-center gap-2">
                    <span className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-[11px] font-bold border border-slate-700 group-hover:bg-brand-900/60 group-hover:text-brand-200 group-hover:border-brand-500/30 transition">
                      Open Task
                    </span>
                  </div>
                </div>
              );
            })}
            {filteredTasks.length === 0 && (
              <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl">
                <p className="text-[11px] text-slate-500 font-medium">No tasks found.</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto pb-4">
          {columns.map((col) => {
            const colTasks = filteredTasks.filter((t) => {
              if (col.id === 'OPEN') return t.status === 'OPEN' || t.status === 'NEEDS_REVIEW' || t.status === 'NEW' || t.status === 'REOPENED';
              if (col.id === 'IN_PROGRESS') return t.status === 'IN_PROGRESS' || t.status === 'MY_TASKS' || t.status === 'DUE_TODAY' || t.status === 'WAITING_APPROVAL';
              return t.status === col.id;
            });
            return (
              <div key={col.id} className="glass-panel p-4 rounded-2xl border border-slate-800 flex flex-col min-h-[520px]">
                <div className={`flex items-center justify-between pb-3 mb-3 border-b ${col.border}`}>
                  <span className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${col.color}`}>
                    {col.label}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] font-extrabold bg-slate-900 text-slate-300 rounded-full border border-slate-800">
                    {colTasks.length}
                  </span>
                </div>

                <div className="space-y-3 flex-1 overflow-y-auto pr-1">
                  {colTasks.map((task) => {
                    const isStatutory = !!task.regulatory_obligation_id;
                    return (
                      <div
                        key={task.id}
                        onClick={() => setSelectedTaskForDetail(task)}
                        className={`p-4 rounded-xl bg-slate-900/90 border transition-all space-y-3 shadow-md cursor-pointer group ${
                          task.is_overdue
                            ? 'border-red-500/50 bg-red-950/10 hover:border-red-400'
                            : isStatutory
                            ? 'border-brand-500/30 hover:border-brand-400/60'
                            : 'border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          {isStatutory ? (
                            <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-brand-500/20 text-brand-300 border border-brand-500/30 flex items-center gap-1 uppercase tracking-wider">
                              <Scale className="w-2.5 h-2.5" />
                              STATUTORY REQUIREMENT
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1 uppercase tracking-wider">
                              <User className="w-2.5 h-2.5" />
                              INTERNAL / OPERATIONAL
                            </span>
                          )}
                          <Badge level={task.priority}>{task.priority}</Badge>
                        </div>

                        <h3 className="text-xs font-bold text-white leading-snug group-hover:text-brand-300 transition-colors">
                          {task.title}
                        </h3>

                        {isStatutory ? (
                          <div className="space-y-1.5 p-2 rounded bg-slate-950/50 border border-slate-800/80">
                            <div className="text-[10px] text-slate-400 font-mono flex flex-col gap-0.5">
                              <span className="text-brand-400">{task.obligation_code || 'Statutory Mandate'}</span>
                              <span className="text-slate-500">{task.due_rule || 'Rule: See Regulation'}</span>
                            </div>
                            <div className="pt-1">
                              {task.frequency === 'CONTINUOUS' ? (
                                <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                                  Continuous obligation — no calendar deadline
                                </span>
                              ) : task.trigger_type ? (
                                task.due_date ? (
                                  <span className={`px-2 py-0.5 rounded text-[9px] font-semibold flex items-center gap-1 ${new Date(task.due_date) < new Date() ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'}`}>
                                    {new Date(task.due_date) < new Date() ? 'OVERDUE: ' : 'DUE: '}{task.due_date}
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded text-[9px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                    AWAITING TRIGGER: {task.trigger_type}
                                  </span>
                                )
                              ) : (
                                task.due_date && (
                                  <span className={`px-2 py-0.5 rounded text-[9px] font-semibold flex items-center gap-1 ${new Date(task.due_date) < new Date() ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'}`}>
                                    {new Date(task.due_date) < new Date() ? 'OVERDUE: ' : 'DUE: '}{task.due_date}
                                  </span>
                                )
                              )}
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-1 p-2 rounded bg-slate-950/50 border border-slate-800/80">
                            <div className="text-[10px] text-slate-400">
                              {task.due_date ? `Target: ${task.due_date}` : 'No target date'}
                            </div>
                          </div>
                        )}

                        <div className="pt-2 border-t border-slate-800/80 space-y-2 text-[11px] text-slate-400">
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1 text-[10px] text-slate-300 truncate max-w-[150px]">
                              <User className="w-3 h-3 text-brand-400 shrink-0" />
                              {task.responsible_function || task.assignee}
                            </span>
                            <div className="flex items-center space-x-2 text-[10px] text-slate-400 font-mono">
                              {task.evidence_count !== undefined && task.evidence_count > 0 && (
                                <span className="flex items-center gap-0.5 text-indigo-300">
                                  <Paperclip className="w-3 h-3" />
                                  {task.evidence_count}
                                </span>
                              )}
                              {task.activity_count !== undefined && task.activity_count > 0 && (
                                <span className="flex items-center gap-0.5 text-slate-400">
                                  <Activity className="w-3 h-3" />
                                  {task.activity_count}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-1">
                            {task.status === 'COMPLETED' && (task.evidence_file_path || task.evidence_url) ? (
                              <span className="w-full py-1 text-[10px] font-bold text-emerald-400 bg-emerald-950/40 rounded border border-emerald-500/20 flex items-center justify-center gap-1">
                                <ShieldCheck className="w-3 h-3" />
                                EVIDENCE ATTACHED
                              </span>
                            ) : (
                              <span className="w-full py-1 text-[10px] font-semibold text-brand-300 hover:text-brand-200 bg-brand-950/40 hover:bg-brand-900/60 rounded border border-brand-500/20 flex items-center justify-center gap-1 transition-all">
                                <FileCheck className="w-3 h-3" />
                                <span>Execution & Provenance Details</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {colTasks.length === 0 && (
                    <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl">
                      <p className="text-[11px] text-slate-500 font-medium">No tasks in {col.label.toLowerCase()}</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Interactive Compliance Task Detail Drawer / Modal */}
      {selectedTaskForDetail && (
        <ComplianceTaskDetail
          task={selectedTaskForDetail}
          isOpen={!!selectedTaskForDetail}
          onClose={() => setSelectedTaskForDetail(null)}
          onTaskUpdated={() => {
            if (onTasksGenerated) onTasksGenerated();
          }}
        />
      )}

      {/* Record Statutory Trigger Event Modal */}
      <RecordTriggerModal
        isOpen={isTriggerModalOpen}
        onClose={() => setIsTriggerModalOpen(false)}
        onEventRecorded={() => {
          if (onTasksGenerated) onTasksGenerated();
        }}
      />
    </div>
  );
};
