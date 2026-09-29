import React from 'react';
import { XCircle, CheckCircle2, AlertTriangle, ShieldCheck, FileText, ArrowDown } from 'lucide-react';
import { ProvenanceExplorer } from './ProvenanceExplorer';

interface ReasoningDrawerProps {
  data: any;
  onClose: () => void;
}

export const ReasoningDrawer: React.FC<ReasoningDrawerProps> = ({ data, onClose }) => {
  if (!data) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[600px] bg-slate-950 border-l border-slate-800 shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
      <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/50">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-400" />
          Deterministic Reasoning
        </h2>
        <button onClick={onClose} className="text-slate-400 hover:text-white transition">
          <XCircle className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              {data.type === 'ALERT' && data.data?.alert_type === 'EVIDENCE_GAP' ? 'EVIDENCE IS MISSING FOR THIS OBLIGATION' : 'CONCLUSION'}
            </h3>
            <div className="text-sm font-semibold text-white mb-2">WHY THIS APPEARS</div>
            <div className="text-sm text-slate-200">
              {data.data?.description || data.data?.rationale || "Operational evidence is missing for this active obligation."}
            </div>
            {data.type === 'ALERT' && (data.data?.alert_type === 'EVIDENCE_GAP' || data.data?.alert_type === 'COMPLETED_WITHOUT_EVIDENCE') && (
              <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-400 font-medium">
                Notice: Missing operational evidence indicates an evidence gap; it does not by itself establish legal non-compliance.
              </div>
            )}
          </div>

          <div className="relative">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 px-2">Provenance Chain</h3>
            <div className="absolute left-6 top-10 bottom-0 w-px bg-slate-800" />
            
            <div className="space-y-4 relative z-10">
              <ProvenanceExplorer entityType={data.type} entityId={data.data?.id} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
