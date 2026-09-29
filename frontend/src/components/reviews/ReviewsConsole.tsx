import React, { useState } from 'react';
import { CheckCircle2, ShieldCheck, Clock, User, AlertCircle, AlertTriangle, FileCheck, ArrowRight, XCircle, Key, MessageSquare } from 'lucide-react';

import { ComplianceTask, TaskStatus } from '../../types';
import { Badge } from '../common/Badge';
import { ServiceAPI } from '../../services/api';

interface ReviewsConsoleProps {
  tasks: ComplianceTask[];
  onUpdateStatus: (taskId: string, newStatus: TaskStatus, notes?: string) => void;
  onRefreshTasks?: () => Promise<void>;
}

export const ReviewsConsole: React.FC<ReviewsConsoleProps> = ({ tasks = [], onUpdateStatus, onRefreshTasks }) => {
  const [activeTab, setActiveTab] = useState<'WAITING_APPROVAL' | 'NEEDS_REVIEW' | 'COMPLETED'>('WAITING_APPROVAL');
  const [selectedTask, setSelectedTask] = useState<ComplianceTask | null>(tasks[0] || null);
  const [legalNote, setLegalNote] = useState('');

  const filteredTasks = (tasks || []).filter((t) => {
    if (!t) return false;
    if (activeTab === 'WAITING_APPROVAL') return t.status === 'WAITING_APPROVAL';
    if (activeTab === 'NEEDS_REVIEW') return t.status === 'NEEDS_REVIEW' || t.status === 'MY_TASKS';
    return t.status === 'COMPLETED';
  });

  const handleApprove = async (taskId: string) => {
    try {
      await ServiceAPI.completeTask(taskId, legalNote || undefined);
      setLegalNote('');
      if (onRefreshTasks) {
        await onRefreshTasks();
      }
    } catch (error: any) {
      if (error.response?.data?.detail) {
        alert(`Completion failed: ${error.response.data.detail}`);
      } else {
        alert('An unexpected error occurred during approval.');
      }
    }
  };

  const handleRequestRevision = (taskId: string) => {
    onUpdateStatus(taskId, 'NEEDS_REVIEW');
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/20 shadow-xl flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
            <h1 className="text-xl font-bold text-white tracking-tight">Compliance Reviews & Dual Sign-off Workspace</h1>
            <span className="px-2.5 py-0.5 text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-full">
              4-Eyes Principle Enforced
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Dual-control approval workspace for Legal Counsel, Chief Compliance Officer sign-offs, and SOC2 audit verification.
          </p>
        </div>
      </div>

      {/* Reviews Tab Navigation */}
      <div className="flex items-center space-x-2 p-1.5 rounded-xl glass-panel border border-slate-800 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('WAITING_APPROVAL')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-all ${
            activeTab === 'WAITING_APPROVAL' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Clock className="w-4 h-4 text-indigo-300" />
          <span>Pending Legal Sign-off</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-indigo-300 rounded font-mono">
            {tasks.filter((t) => t && t.status === 'WAITING_APPROVAL').length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('NEEDS_REVIEW')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-all ${
            activeTab === 'NEEDS_REVIEW' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-4 h-4 text-amber-300" />
          <span>Needs Officer Review</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-amber-300 rounded font-mono">
            {tasks.filter((t) => t && (t.status === 'NEEDS_REVIEW' || t.status === 'MY_TASKS')).length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('COMPLETED')}
          className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-all ${
            activeTab === 'COMPLETED' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-300" />
          <span>Signed Off & Audited</span>
          <span className="px-1.5 py-0.5 text-[10px] bg-slate-900 text-emerald-300 rounded font-mono">
            {tasks.filter((t) => t && t.status === 'COMPLETED').length}
          </span>
        </button>
      </div>

      {/* Main Review Queue Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Review Queue Items List */}
        <div className="lg:col-span-2 space-y-3">
          {filteredTasks.map((task) => {
            const isSelected = selectedTask?.id === task.id;

            return (
              <div
                key={task.id}
                onClick={() => setSelectedTask(task)}
                className={`glass-panel p-5 rounded-2xl cursor-pointer border transition-all space-y-3 ${
                  isSelected ? 'border-indigo-500/50 bg-indigo-950/20 ring-1 ring-indigo-500/30' : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <Badge level={task.priority}>{task.priority}</Badge>
                      {task.control_code && (
                        <span className="px-2 py-0.5 text-[10px] bg-slate-900 text-brand-300 font-mono rounded border border-slate-800">
                          {task.control_code}
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-bold text-white mt-1">{task.title}</h3>
                  </div>

                  {task.completion_signature && (
                    <span className="px-2 py-0.5 text-[9px] bg-emerald-500/20 text-emerald-400 font-mono font-bold rounded border border-emerald-500/30 flex items-center gap-1">
                      <Key className="w-3 h-3" /> Server Signed: {task.completion_signature.substring(0, 16)}...
                    </span>
                  )}
                </div>

                {task.description && (
                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
                    {task.description}
                  </p>
                )}

                {/* 4-Eyes Dual Control Sign-off Matrix */}
                <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 text-[11px] text-slate-400 gap-2">
                  <div>
                    <span className="block text-[10px] text-slate-500 uppercase font-semibold">1. Compliance Officer Review</span>
                    <span className="font-semibold text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> {task.assignee}
                    </span>
                  </div>

                  <div>
                    <span className="block text-[10px] text-slate-500 uppercase font-semibold">2. General Counsel Sign-off</span>
                    <span className="font-semibold text-indigo-300 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-indigo-400" /> {task.reviewer}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {filteredTasks.length === 0 && (
            <div className="p-12 text-center glass-panel rounded-2xl border border-slate-800 space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
              <p className="text-sm font-semibold text-slate-200">No items pending in this sign-off queue</p>
            </div>
          )}
        </div>

        {/* Selected Task Sign-off Control Drawer */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-5">
          <div className="pb-3 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <FileCheck className="w-4 h-4 text-indigo-400" /> 4-Eyes Sign-off Controls
            </h2>
          </div>

          {selectedTask ? (
            <div className="space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                <span className="text-[10px] font-bold text-brand-400 uppercase tracking-wider">Review Target</span>
                <h4 className="text-sm font-bold text-white">{selectedTask.title}</h4>
                <p className="text-[10px] text-slate-400 font-mono">Due: {selectedTask.due_date}</p>
              </div>

              {/* Legal Notes Input */}
              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block flex items-center gap-1">
                  <MessageSquare className="w-3.5 h-3.5 text-indigo-400" /> Legal & Governance Notes
                </label>
                <textarea
                  rows={3}
                  placeholder="Enter legal sign-off notes or revision requests..."
                  value={legalNote}
                  onChange={(e) => setLegalNote(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-indigo-500 text-xs"
                />
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <button
                  onClick={() => handleApprove(selectedTask.id)}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-emerald-600/30 transition-all flex items-center justify-center gap-2"
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>Approve & Sign Off (Cryptographic Hash)</span>
                </button>

                <button
                  onClick={() => handleRequestRevision(selectedTask.id)}
                  className="w-full py-2 bg-slate-900 hover:bg-slate-850 text-rose-300 font-bold text-xs rounded-xl border border-rose-500/30 transition-all flex items-center justify-center gap-1.5"
                >
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  <span>Request Legal Revision</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500 text-xs font-medium">
              Select any compliance task to execute 4-Eyes sign-off.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
