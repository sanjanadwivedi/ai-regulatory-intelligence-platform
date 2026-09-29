import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import { RegulatoryChangeFeedResponse, RegulatoryChangeFeedItem } from '../../types';
import { Loader2, AlertCircle, FileX, ChevronRight, Filter } from 'lucide-react';

interface Props {
  navigateTo: (section: any, regId?: string | null, replace?: boolean, changeId?: string | null) => void;
}

export function RegulatoryChangeFeedWidget({ navigateTo }: Props) {
  const [feed, setFeed] = useState<RegulatoryChangeFeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const size = 10;

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    const skip = (page - 1) * size;
    
    ServiceAPI.getRegulatoryChanges(skip, size)
      .then(data => {
        if (isMounted) {
          setFeed(data);
          setLoading(false);
        }
      })
      .catch(err => {
        if (isMounted) {
          setError('Failed to load regulatory changes feed.');
          setLoading(false);
        }
      });
    return () => { isMounted = false; };
  }, [page]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'REQUIRES_REVIEW': return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'ACKNOWLEDGED': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'RESOLVED': return 'bg-green-500/20 text-green-400 border-green-500/30';
      default: return 'bg-slate-700/50 text-slate-300 border-slate-700';
    }
  };

  const getChangeTypeColor = (type: string) => {
    switch (type) {
      case 'NEW_REGULATION': return 'text-green-400';
      case 'REVISION': return 'text-blue-400';
      case 'REPEAL': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Filter className="w-5 h-5 text-brand-400" />
          Regulatory Change Feed
        </h2>
      </div>

      {error ? (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
        </div>
      ) : !feed || feed.items.length === 0 ? (
        <div className="text-center py-12 bg-slate-900/30 border border-dashed border-slate-800 rounded-xl">
          <FileX className="w-10 h-10 mx-auto mb-3 text-slate-600" />
          <p className="text-slate-400 font-medium">No regulatory changes found.</p>
          <p className="text-slate-500 text-sm mt-1">You're all caught up!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {feed.items.map((item: RegulatoryChangeFeedItem) => (
            <button
              key={item.change_id}
              onClick={() => navigateTo('intelligence', null, false, item.change_id)}
              className="w-full text-left p-4 bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 rounded-xl transition-all flex flex-col md:flex-row gap-4 items-start md:items-center justify-between group"
            >
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold tracking-wider ${getStatusColor(item.review_status)}`}>
                    {item.review_status.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-xs font-bold ${getChangeTypeColor(item.change_type)}`}>
                    {item.change_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-slate-500">
                    Detected {new Date(item.detected_timestamp).toLocaleDateString()}
                  </span>
                </div>
                
                <h3 className="text-base font-bold text-white group-hover:text-brand-300 transition-colors">
                  {item.regulation_name}
                </h3>
                
                <p className="text-sm text-slate-400 mt-1 flex items-center gap-2">
                  {item.previous_version && <span className="line-through opacity-70">{item.previous_version}</span>}
                  {item.previous_version && <span>→</span>}
                  <span className="font-mono text-xs bg-slate-800 px-1.5 py-0.5 rounded text-slate-300">{item.new_version}</span>
                </p>
              </div>
              
              <div className="flex items-center gap-6">
                <div className="flex gap-4 text-center">
                  <div>
                    <p className="text-xs text-slate-500 uppercase">Assess</p>
                    <p className={`font-bold ${item.affected_assessment_count > 0 ? 'text-amber-400' : 'text-slate-600'}`}>{item.affected_assessment_count}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 uppercase">Oblig</p>
                    <p className={`font-bold ${item.affected_obligation_count > 0 ? 'text-amber-400' : 'text-slate-600'}`}>{item.affected_obligation_count}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 uppercase">Tasks</p>
                    <p className={`font-bold ${item.affected_task_count > 0 ? 'text-amber-400' : 'text-slate-600'}`}>{item.affected_task_count}</p>
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" />
              </div>
            </button>
          ))}

          {/* Pagination Controls */}
          <div className="flex items-center justify-between mt-6 pt-4 border-t border-slate-800">
            <p className="text-xs text-slate-500">
              Showing {(page - 1) * size + 1} to {Math.min(page * size, feed.total)} of {feed.total} changes
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={page * size >= feed.total}
                className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
