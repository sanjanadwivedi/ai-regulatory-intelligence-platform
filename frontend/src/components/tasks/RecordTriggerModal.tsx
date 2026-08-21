import React, { useState } from 'react';
import { X, AlertTriangle, Zap, Calendar, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { apiService } from '../../services/api';

interface RecordTriggerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onEventRecorded: () => void;
}

export const RecordTriggerModal: React.FC<RecordTriggerModalProps> = ({
  isOpen,
  onClose,
  onEventRecorded,
}) => {
  const [eventType, setEventType] = useState<'INCIDENT_DETECTED' | 'REGULATORY_NOTIFICATION_RECEIVED' | 'DATA_BREACH_IDENTIFIED' | 'OTHER'>('INCIDENT_DETECTED');
  const [eventTimestamp, setEventTimestamp] = useState<string>(new Date().toISOString().slice(0, 16));
  const [source, setSource] = useState<string>('SOC Monitoring / SIEM Alert');
  const [description, setDescription] = useState<string>('Ransomware command & control communication detected on production DMZ host.');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setResultMsg(null);
    try {
      const res = await apiService.recordTriggerEvent({
        event_type: eventType,
        event_timestamp: new Date(eventTimestamp).toISOString(),
        source,
        description,
      });
      setResultMsg(`Recorded successfully. ${res.affected_tasks_count || 0} tasks evaluated & updated.`);
      setTimeout(() => {
        onEventRecorded();
        onClose();
      }, 1200);
    } catch (err: any) {
      alert(`Error recording trigger event: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Record Statutory Trigger Event</h3>
              <p className="text-xs text-slate-400">Trigger real-time statutory windows (e.g. CERT-In 6-Hour Rule)</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Trigger Event Type
            </label>
            <select
              value={eventType}
              onChange={(e: any) => setEventType(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
            >
              <option value="INCIDENT_DETECTED">INCIDENT_DETECTED (CERT-In 6h Reporting Window)</option>
              <option value="REGULATORY_NOTIFICATION_RECEIVED">REGULATORY_NOTIFICATION_RECEIVED</option>
              <option value="DATA_BREACH_IDENTIFIED">DATA_BREACH_IDENTIFIED</option>
              <option value="OTHER">OTHER</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Event Timestamp
            </label>
            <div className="relative">
              <input
                type="datetime-local"
                value={eventTimestamp}
                onChange={(e) => setEventTimestamp(e.target.value)}
                required
                className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500 pl-9"
              />
              <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Event Source / Origin
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              required
              placeholder="e.g. SOC SIEM Alert #98234, CISO Hotline"
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
              Incident Description & Scope
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              placeholder="Provide technical specifics and preliminary indicators of compromise..."
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start space-x-2 text-amber-300 text-xs">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              Applying this event will deterministically calculate and set operational deadlines on matching active tasks (e.g. CERT-In 6-Hour reporting) without mutating upstream legal applicability assessments.
            </p>
          </div>

          {resultMsg && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center space-x-2 text-emerald-300 text-xs">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>{resultMsg}</span>
            </div>
          )}

          <div className="pt-3 border-t border-slate-800 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center space-x-2 disabled:opacity-50 shadow-lg shadow-amber-600/20"
            >
              {isSubmitting ? (
                <span>Recording Event...</span>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Record & Trigger Deadlines</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
