import React from 'react';
import { ShieldCheck, AlertTriangle, Building2, Globe, FileText, CheckCircle2, ArrowRight } from 'lucide-react';

interface ProvenanceNode {
  id: string;
  type: 'REGULATION' | 'APPLICABILITY' | 'OBLIGATION' | 'TASK' | 'EVIDENCE';
  title: string;
  status?: string;
  meta?: string;
  link?: string;
}

interface ProvenanceExplorerProps {
  startNode?: any;
}

export const ProvenanceExplorer: React.FC<ProvenanceExplorerProps> = ({ startNode }) => {
  // Mock logic to construct the chain based on startNode. In real app, fetch from API.
  const chain: ProvenanceNode[] = [
    {
      id: 'reg_1',
      type: 'REGULATION',
      title: 'CERT-In Directions',
      meta: 'India | Authoritative Mandate',
    },
    {
      id: 'app_1',
      type: 'APPLICABILITY',
      title: 'APPLICABLE',
      meta: 'Matched criteria: ICT Activity, Indian Jurisdiction',
    },
    {
      id: 'obl_1',
      type: 'OBLIGATION',
      title: 'CERT-In Incident Reporting',
      meta: 'Report within 6 hours',
    },
    {
      id: 'task_1',
      type: 'TASK',
      title: 'Operational Task',
      status: 'OPEN',
      meta: 'Assigned to CISO',
    },
    {
      id: 'ev_1',
      type: 'EVIDENCE',
      title: 'Operational Evidence',
      status: 'MISSING',
      meta: 'No files uploaded',
    }
  ];

  const getIcon = (type: string) => {
    switch (type) {
      case 'REGULATION': return <Globe className="w-5 h-5 text-indigo-400" />;
      case 'APPLICABILITY': return <ShieldCheck className="w-5 h-5 text-emerald-400" />;
      case 'OBLIGATION': return <FileText className="w-5 h-5 text-amber-400" />;
      case 'TASK': return <CheckCircle2 className="w-5 h-5 text-blue-400" />;
      case 'EVIDENCE': return <AlertTriangle className="w-5 h-5 text-rose-400" />;
      default: return <FileText className="w-5 h-5" />;
    }
  };

  return (
    <div className="space-y-6 relative">
      {chain.map((node, idx) => (
        <div key={node.id} className="relative flex items-start gap-4">
          <div className="relative z-10 w-12 h-12 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center shrink-0 shadow-lg">
            {getIcon(node.type)}
          </div>
          
          <div className="flex-1 p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 hover:border-brand-500/50 transition cursor-pointer group">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{node.type}</div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-brand-400 transition transform group-hover:translate-x-1" />
            </div>
            <div className="text-sm font-bold text-white">{node.title}</div>
            <div className="text-xs text-slate-400">{node.meta}</div>
            {node.status && (
              <div className="mt-2 inline-flex">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${node.status === 'MISSING' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                  {node.status}
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
