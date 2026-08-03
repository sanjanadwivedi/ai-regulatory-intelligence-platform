import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  Bell,
  Search,
  Sparkles,
  ChevronDown,
  UserCheck,
  HelpCircle,
  X,
  CheckCircle2,
  Loader2,
  Users,
} from 'lucide-react';
import { ComplianceTask } from '../../types';
import { ServiceAPI } from '../../services/api';

export interface UserPersona {
  id: string;
  name: string;
  role: string;
  avatar: string;
}

const DEFAULT_PERSONAS: UserPersona[] = [
  { id: 'default-1', name: 'Sarah Jenkins', role: 'Compliance Officer', avatar: 'SJ' },
  { id: 'default-2', name: 'David Vance', role: 'Chief Compliance Officer', avatar: 'DV' },
];

function getInitials(name: string): string {
  if (!name) return 'U';
  const parts = name.trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

interface NavbarProps {
  onSearchClick: () => void;
  onOpenTour: () => void;
  onOpenSetup?: () => void;
  /** Passed by App.tsx — kept for API compatibility but not used for the badge count.
   *  The badge is driven entirely by liveNotifications to avoid double-counting. */
  unreadNotifications: number;
  tasks?: ComplianceTask[];
  currentPersona: UserPersona;
  onSelectPersona: (persona: UserPersona) => void;
}

const NOTIFICATION_POLL_MS = 60_000; // re-fetch notifications every 60 seconds

export const Navbar: React.FC<NavbarProps> = ({
  onSearchClick,
  onOpenTour,
  onOpenSetup,
  tasks = [],
  currentPersona,
  onSelectPersona,
}) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showNotifDropdown, setShowNotifDropdown] = useState(false);

  const [dbUsers, setDbUsers] = useState<UserPersona[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [liveNotifications, setLiveNotifications] = useState<any[]>([]);

  // ---------------------------------------------------------------------------
  // Notifications — poll periodically after auth token is present
  // ---------------------------------------------------------------------------
  const loadNotifications = useCallback(async () => {
    const notifs = await ServiceAPI.getNotifications();
    setLiveNotifications(notifs ?? []);
  }, []);

  const markRead = async (id: string) => {
    await ServiceAPI.markNotificationRead(id).catch(() => null);
    setLiveNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, NOTIFICATION_POLL_MS);
    return () => clearInterval(interval);
  }, [loadNotifications]);

  // ---------------------------------------------------------------------------
  // Users — load once on mount and on user_list_updated events
  // ---------------------------------------------------------------------------
  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const users = await ServiceAPI.getUsers();
      if (users && users.length > 0) {
        setDbUsers(
          users.map((u: any) => ({
            id: u.id,
            name: u.full_name,
            role: u.role,
            avatar: getInitials(u.full_name),
          }))
        );
      } else {
        setDbUsers(DEFAULT_PERSONAS);
      }
    } catch {
      setDbUsers(DEFAULT_PERSONAS);
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
    window.addEventListener('user_list_updated', loadUsers);
    return () => window.removeEventListener('user_list_updated', loadUsers);
  }, [loadUsers]);

  // ---------------------------------------------------------------------------
  // Derived counts
  // ---------------------------------------------------------------------------
  const unreadCount = liveNotifications.filter((n) => !n.read).length;

  // Fallback: show urgent tasks only when backend returned no notifications at all
  const urgentTaskFallbacks = liveNotifications.length === 0
    ? (tasks || []).filter(
        (t) =>
          t &&
          (t.priority === 'HIGH' ||
            t.status === 'NEEDS_REVIEW' ||
            t.status === 'WAITING_APPROVAL')
      )
    : [];

  const badgeCount = liveNotifications.length > 0 ? unreadCount : urgentTaskFallbacks.length;

  const personas = dbUsers.length > 0 ? dbUsers : DEFAULT_PERSONAS;

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Brand */}
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 via-brand-500 to-indigo-500 p-0.5 shadow-lg shadow-brand-500/20 flex items-center justify-center">
          <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-brand-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-extrabold text-lg tracking-tight text-white font-sans">
              ReguGuard <span className="text-brand-400">AI</span>
            </span>
            <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest bg-brand-500/20 text-brand-300 rounded border border-brand-500/30 flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> Enterprise
            </span>
          </div>
          <p className="text-xs text-slate-400 hidden sm:block">
            AI-Powered Regulatory Intelligence Platform
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center space-x-3">
        {onOpenSetup && (
          <button
            onClick={onOpenSetup}
            className="flex items-center space-x-1.5 bg-brand-600 text-white hover:bg-brand-500 px-3 py-1.5 rounded-lg font-bold text-xs shadow-lg shadow-brand-600/30 transition-all hover:scale-105"
          >
            <span>Enterprise Setup</span>
          </button>
        )}

        <button
          onClick={onOpenTour}
          className="flex items-center space-x-1.5 bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 px-3 py-1.5 rounded-lg border border-brand-500/30 text-xs font-bold transition-all shadow"
        >
          <HelpCircle className="w-4 h-4 text-brand-400" />
          <span>Guided Tour</span>
        </button>

        <button
          onClick={onSearchClick}
          className="flex items-center space-x-2 bg-slate-900/90 hover:bg-slate-850 text-slate-400 hover:text-slate-200 px-3.5 py-1.5 rounded-lg border border-slate-800 text-xs transition-all w-40 sm:w-56"
        >
          <Search className="w-4 h-4 text-brand-400" />
          <span className="flex-1 text-left">Ask AI Copilot...</span>
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => {
              setShowNotifDropdown(!showNotifDropdown);
              setShowDropdown(false);
            }}
            className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition-colors relative"
          >
            <Bell className="w-4 h-4" />
            {badgeCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center animate-pulse">
                {badgeCount}
              </span>
            )}
          </button>

          {showNotifDropdown && (
            <div className="absolute right-0 mt-2 w-80 glass-panel rounded-2xl border border-slate-800 shadow-2xl p-3 z-50 space-y-2">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Bell className="w-3.5 h-3.5 text-brand-400" />
                  Notifications & Alerts ({liveNotifications.length || urgentTaskFallbacks.length})
                </span>
                <button
                  onClick={() => setShowNotifDropdown(false)}
                  className="text-slate-400 hover:text-white p-0.5"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {/* Live backend notifications */}
                {liveNotifications.map((n) => (
                  <div
                    key={n.id}
                    className={`p-2.5 rounded-xl border space-y-1 text-xs cursor-pointer transition-colors ${
                      n.read
                        ? 'bg-slate-900/50 border-slate-800/50 opacity-60'
                        : 'bg-slate-900 border-slate-800 hover:border-brand-500/30'
                    }`}
                    onClick={() => !n.read && markRead(n.id)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                        {n.type}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-slate-500">{n.channel}</span>
                        {!n.read && (
                          <span className="w-1.5 h-1.5 rounded-full bg-brand-400 block" />
                        )}
                      </div>
                    </div>
                    <p className="font-semibold text-slate-200">{n.title}</p>
                    <p className="text-[10px] text-slate-400">{n.message}</p>
                  </div>
                ))}

                {/* Fallback: urgent tasks when no backend notifications exist */}
                {urgentTaskFallbacks.map((t) => (
                  <div
                    key={t.id}
                    className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">
                        {t.priority} PRIORITY
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        Due: {t.due_date}
                      </span>
                    </div>
                    <p className="font-semibold text-slate-200">{t.title}</p>
                    <p className="text-[10px] text-slate-400">Assigned: {t.assignee}</p>
                  </div>
                ))}

                {liveNotifications.length === 0 && urgentTaskFallbacks.length === 0 && (
                  <div className="p-4 text-center text-xs text-slate-400 space-y-1">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 mx-auto" />
                    <p className="font-semibold">All compliance notifications cleared</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Real User Switcher */}
        <div className="relative pl-2 border-l border-slate-800">
          <button
            onClick={() => {
              setShowDropdown(!showDropdown);
              setShowNotifDropdown(false);
            }}
            className="flex items-center space-x-2.5 p-1.5 rounded-xl hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-all text-left"
          >
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-brand-500/30 flex items-center justify-center text-brand-400 font-bold text-xs shadow">
              {currentPersona.avatar}
            </div>
            <div className="hidden lg:block">
              <p className="text-xs font-bold text-slate-200 flex items-center gap-1">
                {currentPersona.name} <UserCheck className="w-3 h-3 text-emerald-400" />
              </p>
              <p className="text-[10px] text-slate-400">{currentPersona.role}</p>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {showDropdown && (
            <div
              className="absolute right-0 mt-2 glass-panel rounded-2xl border border-slate-800 shadow-2xl p-2 z-50 space-y-1"
              style={{ minWidth: '260px' }}
            >
              <div className="px-3 py-2 flex items-center justify-between border-b border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                  <Users className="w-3 h-3" /> Switch Active User
                </span>
                {loadingUsers && <Loader2 className="w-3 h-3 text-slate-500 animate-spin" />}
              </div>

              {personas.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">
                  No users added yet. Go to{' '}
                  <strong>Security & Audit</strong> to add team members.
                </div>
              ) : (
                personas.map((persona) => (
                  <button
                    key={persona.id}
                    onClick={() => {
                      onSelectPersona(persona);
                      setShowDropdown(false);
                    }}
                    className={`w-full flex items-center space-x-3 p-2 rounded-xl text-xs text-left transition-all ${
                      currentPersona.id === persona.id
                        ? 'bg-brand-600/20 text-white font-bold border border-brand-500/30'
                        : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                    }`}
                  >
                    <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center text-brand-300 font-bold text-[10px] shrink-0">
                      {persona.avatar}
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-200 truncate">{persona.name}</p>
                      <p className="text-[10px] text-slate-400 truncate">{persona.role}</p>
                    </div>
                  </button>
                ))
              )}

              <div className="pt-1 border-t border-slate-800">
                <p className="text-[10px] text-slate-500 px-3 py-1">
                  Manage team members in{' '}
                  <strong className="text-slate-400">Security & Audit</strong>
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
