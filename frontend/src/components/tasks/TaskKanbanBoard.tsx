import React from 'react';
import {
  Plus,
  CheckCircle2,
  User,
  ShieldCheck,
  ArrowRight,
  Layers
} from 'lucide-react';
import { ComplianceTask, TaskStatus } from '../../types';
import { Badge } from '../common/Badge';

interface TaskKanbanBoardProps {
  tasks: ComplianceTask[];
  onUpdateStatus: (taskId: string, status: TaskStatus) => void;
  onCreateTaskClick: () => void;
}

export const TaskKanbanBoard: React.FC<TaskKanbanBoardProps> = ({
  tasks,
  onUpdateStatus,
  onCreateTaskClick,
}) => {
  const columns: { id: TaskStatus; label: string; color: string }[] = [
    { id: 'NEEDS_REVIEW', label: 'Needs Review', color: 'border-amber-500/40' },
    { id: 'MY_TASKS', label: 'My Active Tasks', color: 'border-brand-500/40' },
    { id: 'WAITING_APPROVAL', label: 'Waiting Sign-off', color: 'border-indigo-500/40' },
    { id: 'COMPLETED', label: 'Completed & Audited', color: 'border-emerald-500/40' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Compliance Workflow Board</h1>
          <p className="text-xs text-slate-400">
            Orchestrate compliance tasks, legal review sign-offs, and audit resolution states.
          </p>
        </div>
        <button
          onClick={onCreateTaskClick}
          className="flex items-center space-x-2 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-brand-600/30 transition-all self-start"
        >
          <Plus className="w-4 h-4" />
          <span>New Compliance Task</span>
        </button>
      </div>

      {/* Kanban Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto pb-4">
        {columns.map((col) => {
          const colTasks = tasks.filter((t) => {
            if (col.id === 'MY_TASKS') return t.status === 'MY_TASKS' || t.status === 'NEW' || t.status === 'DUE_TODAY';
            return t.status === col.id;
          });
          return (
            <div key={col.id} className="glass-panel p-4 rounded-2xl border border-slate-800 flex flex-col min-h-[500px]">
              <div className={`flex items-center justify-between pb-3 mb-3 border-b ${col.color}`}>
                <span className="text-xs font-bold text-white uppercase tracking-wider">{col.label}</span>
                <span className="px-2 py-0.5 text-[10px] font-extrabold bg-slate-900 text-slate-300 rounded-full border border-slate-800">
                  {colTasks.length}
                </span>
              </div>

              <div className="space-y-3 flex-1 overflow-y-auto pr-1">
                {colTasks.map((task) => (
                  <div
                    key={task.id}
                    className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-md hover:border-slate-700 transition-all"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <Badge level={task.priority}>{task.priority}</Badge>
                      <span className="text-[10px] text-slate-500 font-mono">Due: {task.due_date}</span>
                    </div>

                    <h3 className="text-xs font-bold text-white leading-snug">{task.title}</h3>
                    {task.description && (
                      <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">{task.description}</p>
                    )}

                    <div className="pt-2 border-t border-slate-800/80 space-y-2 text-[11px] text-slate-400">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3 text-brand-400" /> {task.assignee.split(' ')[0]}
                        </span>
                        {task.control_code && (
                          <span className="text-brand-300 font-mono text-[10px] flex items-center gap-1">
                            <Layers className="w-3 h-3" /> {task.control_code}
                          </span>
                        )}
                      </div>

                      {/* Action Transition Buttons */}
                      <div className="flex items-center justify-between pt-1">
                        {col.id === 'NEEDS_REVIEW' && (
                          <button
                            onClick={() => onUpdateStatus(task.id, 'WAITING_APPROVAL')}
                            className="w-full py-1.5 px-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 rounded-lg text-[10px] font-bold border border-indigo-500/30 transition-all flex items-center justify-center gap-1"
                          >
                            <span>Submit for Legal Sign-off</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                        {col.id === 'WAITING_APPROVAL' && (
                          <button
                            onClick={() => onUpdateStatus(task.id, 'COMPLETED')}
                            className="w-full py-1.5 px-2 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 rounded-lg text-[10px] font-bold border border-emerald-500/30 transition-all flex items-center justify-center gap-1"
                          >
                            <ShieldCheck className="w-3 h-3" />
                            <span>Approve Sign-off</span>
                          </button>
                        )}
                        {col.id === 'MY_TASKS' && (
                          <button
                            onClick={() => onUpdateStatus(task.id, 'WAITING_APPROVAL')}
                            className="w-full py-1.5 px-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-[10px] font-bold shadow transition-all flex items-center justify-center gap-1"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Submit Resolution</span>
                          </button>
                        )}
                        {col.id === 'COMPLETED' && (
                          <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Archived in Audit Log
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

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
    </div>
  );
};
