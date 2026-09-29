import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import { RegulatoryChangeDetail, DiffHunk } from '../../types';
import { Loader2, AlertCircle, ArrowLeft, GitCommit, Calendar, Link2, CheckCircle, Clock } from 'lucide-react';

interface Props {
  changeId: string;
  onBack: () => void;
  navigateTo: (section: any, regId?: string | null, replace?: boolean, changeId?: string | null) => void;
}

export function RegulatoryChangeDetailWorkspace({ changeId, onBack, navigateTo }: Props) {
  const [detail, setDetail] = useState<RegulatoryChangeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [propagating, setPropagating] = useState(false);
  const [impactData, setImpactData] = useState<any | null>(null);

  const fetchDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ServiceAPI.getRegulatoryChange(changeId);
      setDetail(data);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('Regulatory change not found.');
      } else {
        setError('Failed to load regulatory change detail.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [changeId]);

  const handleReview = async (decision: string) => {
    if (!detail) return;
    setReviewing(true);
    setReviewError(null);
    try {
      await ServiceAPI.reviewRegulatoryChange(changeId, { decision, review_notes: 'Reviewed via UI' });
      await fetchDetail(); // Refresh after success
    } catch (err: any) {
      if (err.response?.status === 409) {
        setReviewError(err.response.data?.detail || 'Conflict: Invalid transition state.');
      } else if (err.response?.status === 400) {
        setReviewError(err.response.data?.detail || 'Bad Request: Invalid decision.');
      } else {
        setReviewError('An error occurred while submitting the review.');
      }
    } finally {
      setReviewing(false);
    }
  };

  const handlePropagate = async () => {
    if (!detail) return;
    setPropagating(true);
    setReviewError(null);
    try {
      const data = await ServiceAPI.propagateChangeImpact(changeId);
      setImpactData(data);
    } catch (err: any) {
      setReviewError(err.response?.data?.detail || 'Failed to propagate impact.');
    } finally {
      setPropagating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
        <p className="text-slate-400">Loading Regulatory Change {changeId}...</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="space-y-6">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Intelligence
        </button>
        <div className="glass-panel p-12 rounded-2xl border border-red-900/30 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">{error || 'Change Not Found'}</h2>
          <p className="text-slate-400">The requested regulatory change record could not be located.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header & Back Button */}
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Change Feed
        </button>
        
        <div className="flex items-center gap-3">
          {detail.review_status === 'REQUIRES_REVIEW' && (
             <>
               <button 
                  onClick={() => handleReview('ACKNOWLEDGE')} 
                  disabled={reviewing}
                  className="px-4 py-2 bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg font-medium hover:bg-blue-500/30 disabled:opacity-50 transition-colors"
               >
                 Acknowledge
               </button>
               <button 
                  onClick={() => handleReview('RESOLVE')} 
                  disabled={reviewing}
                  className="px-4 py-2 bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg font-medium hover:bg-green-500/30 disabled:opacity-50 transition-colors"
               >
                 Resolve
               </button>
             </>
          )}
          {detail.review_status !== 'REQUIRES_REVIEW' && (
              <button 
                 onClick={handlePropagate} 
                 disabled={propagating || impactData !== null}
                 className="px-4 py-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg font-medium hover:bg-purple-500/30 disabled:opacity-50 transition-colors"
              >
                {propagating ? 'Propagating...' : impactData ? 'Impact Propagated' : 'Propagate Impact'}
              </button>
          )}
          {detail.review_status === 'ACKNOWLEDGED' && (
             <button 
                onClick={() => handleReview('RESOLVE')} 
                disabled={reviewing}
                className="px-4 py-2 bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg font-medium hover:bg-green-500/30 disabled:opacity-50 transition-colors"
             >
               Resolve
             </button>
          )}
          {detail.review_status === 'RESOLVED' && (
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 text-green-400 rounded-lg border border-green-500/20">
              <CheckCircle className="w-4 h-4" />
              <span className="font-medium text-sm">Resolved</span>
            </div>
          )}
          {reviewing && <Loader2 className="w-5 h-5 text-brand-500 animate-spin" />}
        </div>
      </div>

      {reviewError && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p>{reviewError}</p>
        </div>
      )}

      {/* Change Overview */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800">
        <h1 className="text-2xl font-bold text-white mb-2">{detail.regulation_name}</h1>
        <div className="flex items-center gap-4 text-sm text-slate-400 mb-6 pb-6 border-b border-slate-800">
           <span className="flex items-center gap-1.5"><GitCommit className="w-4 h-4"/> {detail.change_type.replace(/_/g, ' ')}</span>
           <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4"/> Detected {new Date(detail.detected_timestamp).toLocaleDateString()}</span>
           {detail.effective_date && (
             <span className="flex items-center gap-1.5"><Clock className="w-4 h-4"/> Effective {new Date(detail.effective_date).toLocaleDateString()}</span>
           )}
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <p className="text-xs text-slate-500 uppercase mb-1">Previous Version</p>
            <p className="font-mono text-sm text-slate-300">{detail.previous_version || 'N/A'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase mb-1">New Version</p>
            <p className="font-mono text-sm text-white bg-slate-800/50 inline-block px-2 py-1 rounded">{detail.new_version}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase mb-1">Review Status</p>
            <p className="text-sm font-bold text-white">{detail.review_status.replace(/_/g, ' ')}</p>
          </div>
          <div>
             <p className="text-xs text-slate-500 uppercase mb-1">Reviewed By</p>
             <p className="text-sm text-slate-300">{detail.reviewed_by || 'Pending'}</p>
          </div>
        </div>
      </div>

      {/* Diff View */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800">
        <h2 className="text-lg font-bold text-white mb-4">Regulatory Delta</h2>
        {!detail.diff_hunks || detail.diff_hunks.length === 0 ? (
          <div className="p-4 bg-slate-900/50 rounded-lg text-slate-400 text-sm">
            No specific textual diff available for this change. (Type: {detail.change_type})
          </div>
        ) : (
          <div className="space-y-4">
             {detail.diff_hunks.map((hunk, idx) => (
                <div key={idx} className="border border-slate-800 rounded-lg overflow-hidden bg-slate-900/30">
                  <div className="bg-slate-800 px-4 py-2 text-xs font-mono text-slate-400 flex justify-between">
                     <span>Section {hunk.section_id || 'Unknown'}</span>
                     <span className={`px-2 rounded text-[10px] uppercase font-bold
                       ${hunk.type === 'ADDED' ? 'bg-green-500/20 text-green-400' : 
                         hunk.type === 'REMOVED' ? 'bg-red-500/20 text-red-400' : 
                         'bg-blue-500/20 text-blue-400'}`}
                     >{hunk.type || 'MODIFIED'}</span>
                  </div>
                  <div className="p-4 text-sm font-mono space-y-2">
                     {hunk.old_text && (
                        <div className="flex gap-4">
                           <span className="text-red-500 select-none">-</span>
                           <span className="text-red-400/80 bg-red-500/10 px-2 py-0.5 rounded break-words whitespace-pre-wrap flex-1">{hunk.old_text}</span>
                        </div>
                     )}
                     {hunk.new_text && (
                        <div className="flex gap-4">
                           <span className="text-green-500 select-none">+</span>
                           <span className="text-green-400/80 bg-green-500/10 px-2 py-0.5 rounded break-words whitespace-pre-wrap flex-1">{hunk.new_text}</span>
                        </div>
                     )}
                  </div>
                </div>
             ))}
          </div>
        )}
      </div>

      {/* Downstream Impact */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800">
        <h2 className="text-lg font-bold text-white mb-4">Downstream Impact</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
           <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50">
             <h3 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2"><Link2 className="w-4 h-4"/> Affected Assessments</h3>
             {detail.affected_assessments.length === 0 ? (
               <p className="text-xs text-slate-500">None</p>
             ) : (
               <ul className="space-y-2">
                 {detail.affected_assessments.map(id => (
                    <li key={id}>
                       <button onClick={() => navigateTo('repository', id)} className="text-brand-400 hover:text-brand-300 text-xs font-mono">{id}</button>
                    </li>
                 ))}
               </ul>
             )}
           </div>

           <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50">
             <h3 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2"><Link2 className="w-4 h-4"/> Affected Obligations</h3>
             {detail.affected_obligations.length === 0 ? (
               <p className="text-xs text-slate-500">None</p>
             ) : (
               <ul className="space-y-2">
                 {detail.affected_obligations.map(id => (
                    <li key={id}>
                       <span className="text-slate-400 text-xs font-mono">{id}</span>
                    </li>
                 ))}
               </ul>
             )}
           </div>

           <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800/50">
             <h3 className="text-sm font-bold text-slate-300 mb-3 flex items-center gap-2"><Link2 className="w-4 h-4"/> Affected Tasks</h3>
             {detail.affected_tasks.length === 0 ? (
               <p className="text-xs text-slate-500">None</p>
             ) : (
               <ul className="space-y-2">
                 {detail.affected_tasks.map(id => (
                    <li key={id}>
                       <button onClick={() => navigateTo('actions')} className="text-brand-400 hover:text-brand-300 text-xs font-mono">{id}</button>
                    </li>
                 ))}
               </ul>
             )}
           </div>
        </div>
      </div>

      {/* Impact Propagation Results */}
      {impactData && (
        <div className="glass-panel p-6 rounded-2xl border border-purple-500/30 bg-purple-900/10">
          <h2 className="text-lg font-bold text-white mb-4">Impact Propagation Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-4">
             <div>
                <p className="text-xs text-slate-500 uppercase mb-1">Status</p>
                <p className="font-bold text-purple-400">{impactData.impact_status}</p>
             </div>
             <div>
                <p className="text-xs text-slate-500 uppercase mb-1">Obligations Affected</p>
                <p className="font-mono text-white">{impactData.summary?.obligations_affected}</p>
             </div>
             <div>
                <p className="text-xs text-slate-500 uppercase mb-1">Controls Affected</p>
                <p className="font-mono text-white">{impactData.summary?.controls_affected}</p>
             </div>
             <div>
                <p className="text-xs text-slate-500 uppercase mb-1">Tasks Affected</p>
                <p className="font-mono text-white">{impactData.summary?.tasks_affected}</p>
             </div>
          </div>
          {impactData.mapping_gap && (
             <div className="p-4 bg-orange-500/20 text-orange-400 border border-orange-500/30 rounded-lg text-sm mb-4">
                <AlertCircle className="w-5 h-5 inline mr-2" />
                <strong>Mapping Gap Detected:</strong> {impactData.reason}
             </div>
          )}
          {!impactData.mapping_gap && impactData.reason && (
             <p className="text-sm text-slate-400">{impactData.reason}</p>
          )}
        </div>
      )}
    </div>
  );
}
