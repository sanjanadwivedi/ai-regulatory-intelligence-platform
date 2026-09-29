import React, { useEffect, useState } from 'react';
import { ShieldCheck, AlertTriangle, Building2, Globe, FileText, CheckCircle2, ArrowRight, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

interface ProvenanceNode {
  id: string;
  type: 'REGULATION' | 'APPLICABILITY' | 'OBLIGATION' | 'TASK' | 'EVIDENCE' | 'CONTROL';
  title: string;
  status?: string;
  meta?: string;
  link?: string;
}

interface ProvenanceExplorerProps {
  entityType?: string;
  entityId?: string;
}

export const ProvenanceExplorer: React.FC<ProvenanceExplorerProps> = ({ entityType, entityId }) => {
  const [nodes, setNodes] = useState<ProvenanceNode[]>([]);
  const [status, setStatus] = useState<'AVAILABLE' | 'UNAVAILABLE'>('UNAVAILABLE');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    if (!entityType || !entityId) {
      if (isMounted) {
        setLoading(false);
        setStatus('UNAVAILABLE');
      }
      return;
    }

    const fetchProvenance = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.get(`/api/v1/provenance/${entityType}/${entityId}`);
        if (isMounted) {
          setStatus(response.data.status);
          setNodes(response.data.nodes || []);
        }
      } catch (err: any) {
        if (isMounted) {
          console.error('Failed to fetch provenance:', err);
          setError(err.response?.data?.detail || 'Failed to load provenance data');
          setStatus('UNAVAILABLE');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchProvenance();

    return () => {
      isMounted = false;
    };
  }, [entityType, entityId]);

  const getIcon = (type: string) => {
    switch (type) {
      case 'REGULATION': return <Globe className="w-5 h-5 text-indigo-400" />;
      case 'APPLICABILITY': return <ShieldCheck className="w-5 h-5 text-emerald-400" />;
      case 'OBLIGATION': return <FileText className="w-5 h-5 text-amber-400" />;
      case 'CONTROL': return <Building2 className="w-5 h-5 text-purple-400" />;
      case 'TASK': return <CheckCircle2 className="w-5 h-5 text-blue-400" />;
      case 'EVIDENCE': return <AlertTriangle className="w-5 h-5 text-rose-400" />;
      default: return <FileText className="w-5 h-5" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        <span className="text-sm font-medium">Tracing provenance chain...</span>
      </div>
    );
  }

  if (error || status === 'UNAVAILABLE' || nodes.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-slate-500 bg-slate-900/50 rounded-xl border border-slate-800">
        <AlertTriangle className="w-5 h-5 mr-2 text-slate-600" />
        <span className="text-sm font-medium text-slate-400">
          No verified provenance is available for this entity.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">
      {nodes.map((node, idx) => (
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
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${node.status === 'MISSING' || node.status === 'UNAVAILABLE' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
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
