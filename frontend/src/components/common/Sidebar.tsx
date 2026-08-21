import React from 'react';
import {
  LayoutDashboard,
  BookOpen,
  ClipboardCheck,
  ShieldCheck,
  Settings,
  ChevronRight,
  Circle,
} from 'lucide-react';
import { NavSection } from '../../types';

interface SidebarProps {
  activeSection: NavSection;
  onSelectSection: (sec: NavSection) => void;
  pendingReviewCount: number;
  // Legacy props kept for backward-compat with App.tsx — not rendered in sidebar UI
  ocrQueueCount?: number;
  lastCrawlTime?: string | null;
  backendOnline?: boolean;
}

// ---------------------------------------------------------------------------
// IA v3.0 — Four primary navigation pillars + Settings
// Copilot is AMBIENT: accessible via FloatingCopilotWidget, not a sidebar item.
// Knowledge Graph, Delta, Timeline, AI Review are CONTEXTUAL inside Repository.
// Sources, Feeds, Batch Re-extract are in Settings (admin concern).
// ---------------------------------------------------------------------------

interface NavItem {
  id: NavSection;
  label: string;
  description: string;
  icon: React.FC<{ className?: string }>;
}

const PRIMARY_NAV: NavItem[] = [
  {
    id: 'workspace',
    label: 'Compliance Overview',
    description: 'Daily monitoring & triage',
    icon: LayoutDashboard,
  },
  {
    id: 'repository',
    label: 'Regulatory Repository',
    description: 'Search & investigate directives',
    icon: BookOpen,
  },
  {
    id: 'actions',
    label: 'Compliance Actions',
    description: 'Tasks, approvals & evidence',
    icon: ClipboardCheck,
  },
  {
    id: 'intelligence',
    label: 'Intelligence & Evidence',
    description: 'Snapshots & audit packages',
    icon: ShieldCheck,
  },
  {
    id: 'audit',
    label: 'Audit Log & Analytics',
    description: 'Immutable trail & metrics',
    icon: ShieldCheck,
  },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeSection,
  onSelectSection,
  pendingReviewCount,
  backendOnline = true,
}) => {
  return (
    <aside
      className="w-64 border-r border-slate-800/80 bg-slate-950/95 flex flex-col justify-between py-5 px-3 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto"
      role="navigation"
      aria-label="Primary navigation"
    >
      {/* PRIMARY PILLARS */}
      <div className="flex flex-col gap-1">
        <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
          Navigation
        </p>

        {PRIMARY_NAV.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          const hasBadge = item.id === 'actions' && pendingReviewCount > 0;

          return (
            <button
              key={item.id}
              onClick={() => onSelectSection(item.id)}
              className={`group w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all duration-200 ${
                isActive
                  ? 'bg-brand-600/20 border border-brand-500/30 shadow-sm shadow-brand-500/10'
                  : 'border border-transparent hover:bg-slate-900/60 hover:border-slate-800/60'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                    isActive
                      ? 'bg-brand-600/30'
                      : 'bg-slate-800/60 group-hover:bg-slate-800'
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? 'text-brand-300' : 'text-slate-400 group-hover:text-slate-300'
                    }`}
                  />
                </div>
                <div className="min-w-0">
                  <p
                    className={`text-xs font-semibold truncate ${
                      isActive ? 'text-brand-200' : 'text-slate-300 group-hover:text-white'
                    }`}
                  >
                    {item.label}
                  </p>
                  <p className="text-[10px] text-slate-500 truncate group-hover:text-slate-400 transition-colors">
                    {item.description}
                  </p>
                </div>
              </div>

              <div className="flex-shrink-0 flex items-center gap-1.5">
                {hasBadge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-500/20 text-amber-300 rounded-full border border-amber-500/30 animate-pulse">
                    {pendingReviewCount}
                  </span>
                )}
                <ChevronRight
                  className={`w-3.5 h-3.5 transition-all ${
                    isActive
                      ? 'text-brand-400 opacity-100'
                      : 'text-slate-600 opacity-0 group-hover:opacity-100 group-hover:text-slate-400'
                  }`}
                />
              </div>
            </button>
          );
        })}

        {/* SETTINGS — secondary, below divider */}
        <div className="my-3 border-t border-slate-800/60" />

        <button
          onClick={() => onSelectSection('settings')}
          className={`group w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all duration-200 ${
            activeSection === 'settings'
              ? 'bg-slate-800/60 border border-slate-700/40'
              : 'border border-transparent hover:bg-slate-900/60 hover:border-slate-800/60'
          }`}
          aria-current={activeSection === 'settings' ? 'page' : undefined}
        >
          <div className="flex items-center gap-3 min-w-0">
            <div
              className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                activeSection === 'settings'
                  ? 'bg-slate-700/60'
                  : 'bg-slate-800/60 group-hover:bg-slate-800'
              }`}
            >
              <Settings
                className={`w-4 h-4 ${
                  activeSection === 'settings'
                    ? 'text-slate-300'
                    : 'text-slate-500 group-hover:text-slate-400'
                }`}
              />
            </div>
            <div className="min-w-0">
              <p
                className={`text-xs font-semibold truncate ${
                  activeSection === 'settings' ? 'text-slate-200' : 'text-slate-400 group-hover:text-slate-300'
                }`}
              >
                Settings
              </p>
              <p className="text-[10px] text-slate-600 truncate group-hover:text-slate-500 transition-colors">
                Sources, feeds & admin
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* SYSTEM STATUS FOOTER */}
      <div className="px-3 py-2.5 rounded-xl bg-slate-900/50 border border-slate-800/60 text-xs space-y-1">
        <div className="flex items-center gap-2">
          <Circle
            className={`w-2 h-2 fill-current flex-shrink-0 ${
              backendOnline ? 'text-emerald-400' : 'text-slate-500'
            }`}
          />
          <span className="text-[10px] font-semibold text-slate-400">
            {backendOnline ? 'System Online' : 'System Offline'}
          </span>
        </div>
        <p className="text-[10px] text-slate-600 leading-tight">
          Aegis AI available via floating assistant
        </p>
      </div>
    </aside>
  );
};

