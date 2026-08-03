import React from 'react';
import {
  Home,
  BookOpen,
  GitBranch,
  CheckCircle2,
  Briefcase,
  Bot,
  Radio,
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import { NavSection } from '../../types';
import { formatRelativeTime } from '../../utils/formatTime';

interface SidebarProps {
  activeSection: NavSection;
  onSelectSection: (sec: NavSection) => void;
  pendingReviewCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSelectSection,
  pendingReviewCount,
}) => {
  const menuItems = [
    { id: 'workspace' as NavSection, label: 'Workspace', icon: Home },
    { id: 'repository' as NavSection, label: 'Regulations', icon: BookOpen },
    { id: 'graph' as NavSection, label: 'Knowledge Graph', icon: GitBranch, isNew: true },
    { id: 'reviews' as NavSection, label: 'Reviews & Sign-offs', icon: CheckCircle2, badge: pendingReviewCount },
    { id: 'cases' as NavSection, label: 'Compliance Cases', icon: Briefcase },
    { id: 'copilot' as NavSection, label: 'AI Copilot', icon: Bot },
    { id: 'sources' as NavSection, label: 'Feed Sources & OCR Queue', icon: Radio, isReviewQueue: true },
    { id: 'batch_re_extract' as NavSection, label: 'Batch Re-Extract', icon: RefreshCw },
    { id: 'security' as NavSection, label: 'Security & Audit', icon: ShieldCheck },
  ];


  return (
    <aside className="w-64 border-r border-slate-800/80 bg-slate-950/90 flex flex-col justify-between py-4 px-3 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          Compliance OS
        </div>
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectSection(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-xs font-semibold transition-all duration-200 ${
                isActive
                  ? 'bg-gradient-to-r from-brand-600/30 to-brand-500/10 text-brand-300 border border-brand-500/30 shadow-lg shadow-brand-500/10 scale-[1.02]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 hover:translate-x-0.5'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-brand-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold bg-amber-500/20 text-amber-300 rounded-full border border-amber-500/30 animate-pulse">
                  {item.badge}
                </span>
              )}
              {item.isNew && (
                <span className="px-1.5 py-0.5 text-[9px] font-bold bg-brand-500/20 text-brand-300 rounded border border-brand-500/30 uppercase">
                  Graph
                </span>
              )}
              {item.isReviewQueue && (
                <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/20 text-amber-300 rounded border border-amber-500/30 uppercase animate-pulse">
                  1 OCR Queue
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Real-Time Engine Status Footprint */}
      <div className="px-3.5 py-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold text-slate-400 uppercase">AI Crawler Engine</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
        </div>
        <p className="text-[11px] text-slate-300 font-semibold">Real-time Stream Active</p>
        <p className="text-[10px] text-slate-400">Last crawl: {formatRelativeTime(new Date(Date.now() - 15 * 60 * 1000))}</p>
      </div>
    </aside>
  );
};
