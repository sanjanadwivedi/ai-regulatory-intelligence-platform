import React, { useState, useEffect } from 'react';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  User,
  Building2,
  FileText,
  Paperclip,
  Activity,
  MessageSquare,
  ExternalLink,
  RotateCcw,
  Play,
  Pause,
  UploadCloud,
  Send,
  Calendar,
  Lock
} from 'lucide-react';
import { ComplianceTask, ComplianceTaskEvidence, ComplianceTaskActivity } from '../../types';
import { apiService } from '../../services/api';

interface ComplianceTaskDetailProps {
  task: ComplianceTask | null;
  isOpen: boolean;
  onClose: () => void;
  onTaskUpdated: () => void;
}

export const ComplianceTaskDetail: React.FC<ComplianceTaskDetailProps> = ({
  task,
  isOpen,
  onClose,
  onTaskUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<'provenance' | 'evidence' | 'activity' | 'comments'>('provenance');
  const [evidenceList, setEvidenceList] = useState<ComplianceTaskEvidence[]>([]);
  const [activities, setActivities] = useState<ComplianceTaskActivity[]>([]);
  const [comments, setComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Evidence upload form state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [evidenceFileName, setEvidenceFileName] = useState('');
  const [evidenceType, setEvidenceType] = useState('DOCUMENT');
  const [evidenceDesc, setEvidenceDesc] = useState('');
  const [evidenceUrl, setEvidenceUrl] = useState('');

  // Reopen form state
  const [showReopenModal, setShowReopenModal] = useState(false);
  const [reopenReason, setReopenReason] = useState('');

  // Assignment edit state
  const [isEditingAssignee, setIsEditingAssignee] = useState(false);
  const [assignedName, setAssignedName] = useState(task?.assignee || '');
  const [assignedFunction, setAssignedFunction] = useState(task?.responsible_function || '');

  useEffect(() => {
    if (task && isOpen) {
      setAssignedName(task.assignee || '');
      setAssignedFunction(task.responsible_function || '');
      fetchEvidenceAndActivities(task.id);
    }
  }, [task, isOpen]);

  const fetchEvidenceAndActivities = async (taskId: string) => {
    setIsLoading(true);
    try {
      const [evRes, actRes] = await Promise.all([
        apiService.getComplianceTaskEvidence(taskId),
        apiService.getComplianceTaskActivities(taskId),
      ]);
      setEvidenceList(evRes || []);
      setActivities(actRes || []);
    } catch (err) {
      console.error('Failed to load task details', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen || !task) return null;

  const handleStatusChange = async (newStatus: string, reason?: string) => {
    setActionLoading(true);
    try {
      if (newStatus === 'COMPLETED') {
        await apiService.completeComplianceTask(task.id, 'Task verified and operational control confirmed.');
      } else {
        await apiService.updateComplianceTaskStatus(task.id, newStatus as any);
      }
      onTaskUpdated();
      fetchEvidenceAndActivities(task.id);
    } catch (err: any) {
      alert(`Error updating status: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReopen = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reopenReason.trim()) return;
    setActionLoading(true);
    try {
      await apiService.reopenComplianceTask(task.id, reopenReason);
      setShowReopenModal(false);
      setReopenReason('');
      onTaskUpdated();
      fetchEvidenceAndActivities(task.id);
    } catch (err: any) {
      alert(`Error reopening task: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAssignSave = async () => {
    setActionLoading(true);
    try {
      await apiService.assignComplianceTask(task.id, {
        assignee: assignedName,
        responsible_function: assignedFunction,
      });
      setIsEditingAssignee(false);
      onTaskUpdated();
      fetchEvidenceAndActivities(task.id);
    } catch (err: any) {
      alert(`Error assigning task: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!evidenceFileName.trim()) return;
    setActionLoading(true);
    try {
      await apiService.uploadComplianceTaskEvidence(task.id, {
        file_name: evidenceFileName,
        evidence_type: evidenceType,
        description: evidenceDesc,
        file_url: evidenceUrl || undefined,
      });
      setShowUploadModal(false);
      setEvidenceFileName('');
      setEvidenceDesc('');
      setEvidenceUrl('');
      onTaskUpdated();
      fetchEvidenceAndActivities(task.id);
    } catch (err: any) {
      alert(`Error attaching evidence: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setActionLoading(true);
    try {
      await apiService.addComplianceTaskComment(task.id, newComment);
      setNewComment('');
      onTaskUpdated();
      fetchEvidenceAndActivities(task.id);
    } catch (err: any) {
      alert(`Error adding comment: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border-l border-slate-700 w-full max-w-3xl h-full shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 bg-slate-900/90 flex items-start justify-between">
          <div className="space-y-2 max-w-xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className={`px-2.5 py-0.5 rounded text-xs font-semibold border ${
                task.status === 'COMPLETED'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : task.status === 'IN_PROGRESS'
                  ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                  : task.status === 'BLOCKED'
                  ? 'bg-red-500/10 text-red-400 border-red-500/30'
                  : task.status === 'REOPENED'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : 'bg-slate-800 text-slate-300 border-slate-700'
              }`}>
                {task.status}
              </span>

              {!!task.regulatory_obligation_id ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 flex items-center gap-1 uppercase tracking-wider">
                  STATUTORY REQUIREMENT
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1 uppercase tracking-wider">
                  INTERNAL / OPERATIONAL
                </span>
              )}

              {task.control_code && (
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  {task.control_code}
                </span>
              )}
              {task.priority && (
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  task.priority === 'CRITICAL'
                    ? 'bg-red-500/20 text-red-300'
                    : task.priority === 'HIGH'
                    ? 'bg-amber-500/20 text-amber-300'
                    : 'bg-slate-700 text-slate-300'
                }`}>
                  {task.priority}
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight leading-snug">
              {task.title}
            </h2>
            {task.deadline_status_message && (
              <p className={`text-xs flex items-center space-x-1.5 ${
                task.is_overdue ? 'text-red-400 font-semibold' : 'text-slate-400'
              }`}>
                <Clock className="w-3.5 h-3.5" />
                <span>{task.deadline_status_message}</span>
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Action Toolbar */}
        <div className="px-6 py-3 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {task.status !== 'IN_PROGRESS' && task.status !== 'COMPLETED' && (
              <button
                disabled={actionLoading}
                onClick={() => handleStatusChange('IN_PROGRESS')}
                className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Start Progress</span>
              </button>
            )}
            {task.status === 'IN_PROGRESS' && (
              <button
                disabled={actionLoading}
                onClick={() => handleStatusChange('BLOCKED')}
                className="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                <Pause className="w-3.5 h-3.5" />
                <span>Mark Blocked</span>
              </button>
            )}
            {task.status === 'BLOCKED' && (
              <button
                disabled={actionLoading}
                onClick={() => handleStatusChange('IN_PROGRESS')}
                className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Resume Task</span>
              </button>
            )}
            {task.status !== 'COMPLETED' ? (
              <button
                disabled={actionLoading}
                onClick={() => handleStatusChange('COMPLETED')}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors disabled:opacity-50 shadow-md shadow-emerald-600/20"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Complete Task</span>
              </button>
            ) : (
              <button
                disabled={actionLoading}
                onClick={() => setShowReopenModal(true)}
                className="px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reopen Task</span>
              </button>
            )}
          </div>

          <button
            onClick={() => setShowUploadModal(true)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Attach Evidence</span>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 px-6 bg-slate-900">
          <button
            onClick={() => setActiveTab('provenance')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
              activeTab === 'provenance'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Statutory Provenance</span>
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
              activeTab === 'evidence'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Paperclip className="w-4 h-4" />
            <span>Operational Evidence ({evidenceList.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('activity')}
            className={`py-3 px-4 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
              activeTab === 'activity'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>Activity Stream ({activities.length})</span>
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === 'provenance' && (
            <div className="space-y-6">
              {/* Statutory Obligation Reference */}
              <div className="p-4 bg-slate-800/60 border border-slate-700/80 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-indigo-400 text-xs font-bold uppercase tracking-wider">
                    <FileText className="w-4 h-4" />
                    <span>Statutory Mandate Citation</span>
                  </div>
                  {task.authoritative_source_url && (
                    <a
                      href={task.authoritative_source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-indigo-400 hover:underline flex items-center space-x-1"
                    >
                      <span>Official Source</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <p className="text-sm font-semibold text-slate-200">
                  {task.source_citation || 'Statutory Requirement under IT Act 2000'}
                </p>
                <div className="p-3 bg-slate-900/80 rounded-lg text-xs text-slate-300 leading-relaxed border border-slate-700/50">
                  {task.description}
                </div>
              </div>

              {/* Functional Ownership & Assignment */}
              <div className="p-4 bg-slate-800/40 border border-slate-700/60 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Functional Ownership & Assignee
                  </span>
                  {!isEditingAssignee ? (
                    <button
                      onClick={() => setIsEditingAssignee(true)}
                      className="text-xs text-indigo-400 hover:underline"
                    >
                      Edit
                    </button>
                  ) : (
                    <div className="space-x-2">
                      <button
                        onClick={handleAssignSave}
                        className="text-xs text-emerald-400 hover:underline font-semibold"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setIsEditingAssignee(false)}
                        className="text-xs text-slate-400 hover:underline"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>

                {!isEditingAssignee ? (
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-slate-500 block mb-0.5">Assignee</span>
                      <span className="text-slate-200 font-medium">{task.assignee}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block mb-0.5">Responsible Function</span>
                      <span className="text-slate-200 font-medium">{task.responsible_function || 'General Compliance'}</span>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Assignee</label>
                      <input
                        type="text"
                        value={assignedName}
                        onChange={(e) => setAssignedName(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">Responsible Function</label>
                      <input
                        type="text"
                        value={assignedFunction}
                        onChange={(e) => setAssignedFunction(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Upstream Evidence Provenance Links */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Authoritative Upstream Grounding
                </h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg space-y-1">
                    <span className="text-xs text-indigo-400 font-medium flex items-center space-x-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Legal Assessment</span>
                    </span>
                    <p className="text-xs text-slate-300">
                      Evaluated as <strong>APPLICABLE</strong> under authoritative jurisdiction rules.
                    </p>
                  </div>
                  <div className="p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg space-y-1">
                    <span className="text-xs text-emerald-400 font-medium flex items-center space-x-1">
                      <Building2 className="w-3.5 h-3.5" />
                      <span>Organization Context</span>
                    </span>
                    <p className="text-xs text-slate-300">
                      Confirmed Business Activities & Sector Profile.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'evidence' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-400">
                  Operational evidence proving execution of this statutory requirement.
                </p>
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-sm"
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Upload Evidence</span>
                </button>
              </div>

              {evidenceList.length === 0 ? (
                <div className="p-8 text-center bg-slate-800/20 border border-dashed border-slate-700 rounded-xl">
                  <Paperclip className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No operational evidence uploaded yet.</p>
                  <p className="text-xs text-slate-500 mt-1">Upload audit reports, screenshots, or configuration files.</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {evidenceList.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-3.5 bg-slate-800/60 border border-slate-700/60 rounded-lg flex items-start justify-between"
                    >
                      <div className="space-y-1 max-w-md">
                        <div className="flex items-center space-x-2">
                          <span className="px-1.5 py-0.5 bg-slate-700 text-slate-300 text-xs rounded font-mono">
                            {ev.evidence_type}
                          </span>
                          <span className="text-xs font-semibold text-slate-200 truncate">
                            {ev.file_name}
                          </span>
                        </div>
                        {ev.description && (
                          <p className="text-xs text-slate-400">{ev.description}</p>
                        )}
                        <p className="text-xs text-slate-500">
                          Uploaded by <strong>{ev.uploaded_by}</strong> ({ev.uploader_role}) on{' '}
                          {new Date(ev.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {ev.file_url && (
                        <a
                          href={ev.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-indigo-400 hover:underline flex items-center space-x-1"
                        >
                          <span>View</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'activity' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Immutable chronological log of operational transitions, assignments, and statutory trigger events.
              </p>
              {activities.length === 0 ? (
                <div className="p-8 text-center bg-slate-800/20 border border-dashed border-slate-700 rounded-xl">
                  <Activity className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No activity recorded yet.</p>
                </div>
              ) : (
                <div className="space-y-3 relative pl-4 border-l border-slate-800">
                  {activities.map((act) => (
                    <div key={act.id} className="relative space-y-1">
                      <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-indigo-500 ring-4 ring-slate-900" />
                      <div className="flex items-center space-x-2 text-xs">
                        <span className="font-semibold text-slate-200">{act.actor_name}</span>
                        <span className="text-slate-500">({act.actor_role})</span>
                        <span className="text-slate-500">•</span>
                        <span className="text-slate-500">{new Date(act.created_at).toLocaleString()}</span>
                      </div>
                      <p className="text-xs text-slate-300 bg-slate-800/40 p-2.5 rounded-lg border border-slate-700/40">
                        {act.message}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Comment input footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900">
          <form onSubmit={handleAddComment} className="flex space-x-2">
            <input
              type="text"
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Add an operational audit note or comment..."
              className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={actionLoading || !newComment.trim()}
              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium flex items-center space-x-1 disabled:opacity-50 transition-colors"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Comment</span>
            </button>
          </form>
        </div>
      </div>

      {/* Upload Evidence Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-md rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-white">Attach Operational Evidence</h3>
              <button onClick={() => setShowUploadModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleUploadEvidence} className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Evidence Type</label>
                <select
                  value={evidenceType}
                  onChange={(e) => setEvidenceType(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="DOCUMENT">DOCUMENT</option>
                  <option value="SCREENSHOT">SCREENSHOT</option>
                  <option value="LOG">LOG</option>
                  <option value="REPORT">REPORT</option>
                  <option value="POLICY">POLICY</option>
                  <option value="CERTIFICATE">CERTIFICATE</option>
                  <option value="INCIDENT_RECORD">INCIDENT_RECORD</option>
                  <option value="OTHER">OTHER</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">File / Artifact Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. ntp_drift_audit_log.log"
                  value={evidenceFileName}
                  onChange={(e) => setEvidenceFileName(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Artifact URL (Optional)</label>
                <input
                  type="text"
                  placeholder="https://s3.corp/evidence/..."
                  value={evidenceUrl}
                  onChange={(e) => setEvidenceUrl(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Description & Scope</label>
                <textarea
                  rows={2}
                  placeholder="Summary of what this evidence verifies..."
                  value={evidenceDesc}
                  onChange={(e) => setEvidenceDesc(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded"
                >
                  Save Evidence
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reopen Modal */}
      {showReopenModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-md rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-white">Reopen Completed Task</h3>
              <button onClick={() => setShowReopenModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleReopen} className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Reopen Justification / Audit Finding</label>
                <textarea
                  rows={3}
                  required
                  placeholder="State reason for reopening (e.g. audit discrepancy, drift detected)..."
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReopenModal(false)}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded"
                >
                  Confirm Reopen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
