import React, { useState, useEffect } from 'react';
import { 
  Check, X, Edit2, ExternalLink, ShieldAlert, Sparkles, 
  CheckSquare, CheckCircle2, ChevronRight, Activity, Building2, Briefcase, Globe, Users, Shield
} from 'lucide-react';
import { ServiceAPI } from '../../services/api';

export interface FactReviewConsoleProps {
  onFinalize: () => void;
}

const CATEGORY_MAP: Record<string, { label: string, icon: React.ReactNode }> = {
  COMPANY: { label: 'About your company', icon: <Building2 className="w-5 h-5 text-blue-400" /> },
  BUSINESS_ACTIVITY: { label: 'Business activities', icon: <Activity className="w-5 h-5 text-purple-400" /> },
  PRODUCT_SERVICE: { label: 'Products and services', icon: <Briefcase className="w-5 h-5 text-emerald-400" /> },
  LOCATION: { label: 'Locations', icon: <Globe className="w-5 h-5 text-amber-400" /> },
  DEPARTMENT: { label: 'Teams and functions', icon: <Users className="w-5 h-5 text-rose-400" /> },
  LICENSE: { label: 'Official licenses and authorizations', icon: <Shield className="w-5 h-5 text-brand-400" /> },
  REGULATORY_SIGNAL: { label: 'Potential Regulatory Signals', icon: <Shield className="w-5 h-5 text-cyan-400" /> },
};

export const FactReviewConsole: React.FC<FactReviewConsoleProps> = ({ onFinalize }) => {
  const [facts, setFacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [confirmingBulk, setConfirmingBulk] = useState(false);
  const [bulkMessage, setBulkMessage] = useState<string | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadFacts();
  }, []);

  const loadFacts = async () => {
    try {
      setLoading(true);
      const data = await ServiceAPI.getDiscoveryFacts('ALL');
      setFacts(data);
    } catch (err) {
      console.error('Failed to load facts', err);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (id: string) => {
    try {
      await ServiceAPI.confirmFact(id);
      setFacts(facts.map(f => f.id === id ? { ...f, status: 'CONFIRMED' } : f));
    } catch (err) {
      console.error('Failed to confirm fact', err);
    }
  };

  const handleReject = async (id: string) => {
    try {
      await ServiceAPI.rejectFact(id);
      setFacts(facts.map(f => f.id === id ? { ...f, status: 'REJECTED' } : f));
    } catch (err) {
      console.error('Failed to reject fact', err);
    }
  };

  const handleSaveEdit = async (id: string) => {
    if (!editValue.trim()) return;
    try {
      await ServiceAPI.editFact(id, editValue);
      setFacts(facts.map(f => f.id === id ? { ...f, status: 'CONFIRMED', fact_value: editValue, extraction_method: 'USER_EDITED' } : f));
      setEditingId(null);
    } catch (err) {
      console.error('Failed to edit fact', err);
    }
  };

  const handleBulkConfirm = async () => {
    try {
      setConfirmingBulk(true);
      const res = await ServiceAPI.bulkConfirmFacts(0.85);
      setBulkMessage(`${res.confirmed_count} high-confidence findings confirmed.`);
      await loadFacts();
      setTimeout(() => setBulkMessage(null), 3000);
    } catch (err) {
      console.error('Failed bulk confirm', err);
    } finally {
      setConfirmingBulk(false);
    }
  };

  const handleFinalize = async () => {
    try {
      setError(null);
      setIsFinalizing(true);
      await ServiceAPI.finalizeDiscovery();
      await onFinalize();
    } catch (err: any) {
      console.error('Failed to finalize discovery', err);
      const msg = err.response?.data?.detail || 'Failed to finalize profile. Please try again.';
      setError(msg);
    } finally {
      setIsFinalizing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-slate-800 border-t-brand-500 rounded-full animate-spin" />
          <p className="text-slate-400">Loading discovery findings...</p>
        </div>
      </div>
    );
  }

  // Filter out rejected from main view unless we want to show a history
  const activeFacts = facts.filter(f => f.status !== 'REJECTED');
  
  const pendingCount = activeFacts.filter(f => f.status === 'PENDING').length;
  const highConfPendingCount = activeFacts.filter(f => f.status === 'PENDING' && f.confidence >= 0.85).length;

  const getConfidenceLabel = (conf: number) => {
    if (conf >= 0.85) return { label: 'High confidence', color: 'text-emerald-400' };
    if (conf >= 0.70) return { label: 'Moderate confidence', color: 'text-amber-400' };
    return { label: 'Needs review', color: 'text-rose-400' };
  };

  // Deduplicate facts by type and value so each unique candidate appears strictly once
  const uniqueFactsMap = new Map<string, any>();
  activeFacts.forEach(fact => {
    const key = `${fact.fact_type}::${fact.fact_value.trim().toLowerCase()}`;
    if (!uniqueFactsMap.has(key) || (fact.status === 'CONFIRMED' && uniqueFactsMap.get(key).status !== 'CONFIRMED')) {
      uniqueFactsMap.set(key, fact);
    }
  });
  const uniqueFacts = Array.from(uniqueFactsMap.values());

  // Group unique facts
  const groupedFacts = uniqueFacts.reduce((acc, fact) => {
    const cat = CATEGORY_MAP[fact.fact_type]?.label || 'Other findings';
    if (!acc[cat]) acc[cat] = { icon: CATEGORY_MAP[fact.fact_type]?.icon, items: [] };
    acc[cat].items.push(fact);
    return acc;
  }, {} as Record<string, { icon: React.ReactNode, items: any[] }>);

  return (
    <div className="w-full max-w-5xl mx-auto py-8 px-4 flex flex-col gap-8 h-full">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Sparkles className="w-6 h-6 text-brand-400" />
          We found this information about your organization
        </h1>
        <p className="text-slate-400">
          Review the items we're less certain about. Confirm anything that's correct and edit anything that needs changing.
        </p>
      </div>

      <div className="flex items-center justify-between bg-slate-900/50 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-brand-500/10 flex items-center justify-center text-brand-400 font-bold">
            {pendingCount}
          </div>
          <div>
            <div className="text-sm font-medium text-white">items need your attention</div>
            <div className="text-xs text-slate-400">Review remaining pending findings</div>
          </div>
        </div>

        {highConfPendingCount > 0 && (
          <div className="flex items-center gap-4">
            {bulkMessage && <span className="text-emerald-400 text-sm font-medium animate-pulse">{bulkMessage}</span>}
            <button
              onClick={handleBulkConfirm}
              disabled={confirmingBulk}
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <CheckSquare className="w-4 h-4" />
              Confirm all high-confidence findings ({highConfPendingCount})
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto space-y-8 pr-2">
        {Object.entries(groupedFacts).map(([category, data]: [string, any]) => { const { icon, items } = data; return (
          <div key={category} className="space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2 pb-2 border-b border-slate-800/50">
              {icon}
              {category}
            </h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {items.map((fact: any) => {
                const conf = getConfidenceLabel(fact.confidence);
                const isPending = fact.status === 'PENDING';
                const isEditing = editingId === fact.id;
                
                return (
                  <div 
                    key={fact.id} 
                    className={`bg-slate-900/40 border rounded-xl p-5 flex flex-col gap-4 transition-all ${isPending ? 'border-brand-500/30 shadow-[0_0_15px_rgba(56,189,248,0.05)]' : 'border-slate-800 opacity-70'}`}
                  >
                    <div className="flex justify-between items-start gap-4">
                      <div className="flex-1 space-y-1">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input 
                              type="text" 
                              className="form-input text-sm flex-1" 
                              value={editValue} 
                              onChange={e => setEditValue(e.target.value)} 
                              autoFocus
                            />
                            <button onClick={() => handleSaveEdit(fact.id)} className="p-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-white">
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={() => setEditingId(null)} className="p-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300">
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="font-semibold text-white text-base">
                            {fact.fact_value}
                            {fact.extraction_method === 'USER_EDITED' && (
                              <span className="ml-2 text-[10px] uppercase tracking-wider bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">Edited</span>
                            )}
                            {fact.fact_type === 'REGULATORY_SIGNAL' && (
                              <span className="ml-2 text-[10px] font-normal uppercase tracking-wider bg-cyan-950/60 text-cyan-300 border border-cyan-500/30 px-1.5 py-0.5 rounded">Potential Signal</span>
                            )}
                          </div>
                        )}
                        <div className="flex items-center gap-2 text-xs">
                          <span className={conf.color}>{conf.label} &middot; {Math.round(fact.confidence * 100)}%</span>
                        </div>
                        {fact.fact_type === 'REGULATORY_SIGNAL' && (
                          <p className="text-[11px] text-cyan-300/70 pt-0.5 leading-snug">
                            Potential regulatory relevance identified from public evidence. Legal applicability will be determined separately by the Regulatory Applicability Engine.
                          </p>
                        )}
                      </div>
                      
                      {isPending ? (
                        <div className="flex items-center gap-1 shrink-0">
                          <button onClick={() => handleConfirm(fact.id)} className="p-2 hover:bg-emerald-500/10 text-slate-400 hover:text-emerald-400 rounded-lg transition-colors" title={fact.fact_type === 'REGULATORY_SIGNAL' ? 'Confirm Signal' : 'Confirm Finding'}>
                            <Check className="w-4 h-4" />
                          </button>
                          <button onClick={() => { setEditingId(fact.id); setEditValue(fact.fact_value); }} className="p-2 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg transition-colors" title="Edit">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button onClick={() => handleReject(fact.id)} className="p-2 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 rounded-lg transition-colors" title="Reject">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="shrink-0 flex items-center gap-2 text-emerald-500 text-sm font-medium">
                          <CheckCircle2 className="w-4 h-4" />
                          {fact.fact_type === 'REGULATORY_SIGNAL' ? 'Signal Confirmed' : 'Confirmed'}
                        </div>
                      )}
                    </div>
                    
                    <div className="bg-slate-950/50 rounded-lg p-3 text-sm space-y-2 border border-slate-800/50">
                      <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">Evidence</div>
                      {fact.snippet ? (
                        <p className="text-slate-300 italic text-[13px] leading-relaxed">"{fact.snippet}"</p>
                      ) : (
                        <div className="flex items-center gap-2 text-amber-500/70 text-[13px]">
                          <ShieldAlert className="w-4 h-4" />
                          Evidence unavailable
                        </div>
                      )}
                      
                      {fact.source_url && (
                        <div className="pt-2 flex items-center justify-between border-t border-slate-800/50 mt-2">
                          <span className="text-xs text-slate-500">Source: {fact.source_title || 'Company Website'}</span>
                          <a href={fact.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-brand-400 hover:text-brand-300">
                            View source <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );})}
      </div>

      <div className="pt-6 border-t border-slate-800 flex items-center justify-between">
        <div className="flex-1">
          {error && (
            <div className="flex items-center gap-2 text-rose-400 text-sm bg-rose-500/10 px-3 py-2 rounded-lg border border-rose-500/20 w-fit">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
        <button
          onClick={handleFinalize}
          disabled={isFinalizing}
          className="btn-primary flex items-center gap-2 shrink-0"
        >
          {isFinalizing ? 'Finalizing...' : 'Confirm Organization Profile'}
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

