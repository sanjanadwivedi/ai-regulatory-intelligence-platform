import React, { useEffect, useState, useCallback } from 'react';
import { Navbar, UserPersona } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { CODashboard } from './components/dashboard/CODashboard';
import { RegulationList } from './components/regulations/RegulationList';
import { RegulationDetail } from './components/regulations/RegulationDetail';
import { RAGCopilot } from './components/copilot/RAGCopilot';
import { ComplianceActionsHub } from './components/actions/ComplianceActionsHub';
import { AuditDefenseHub } from './components/audit/AuditDefenseHub';
import { SettingsHub } from './components/settings/SettingsHub';
import { GuidedTourModal } from './components/common/GuidedTourModal';
import { EnterpriseSetupModal } from './components/common/EnterpriseSetupModal';
import { OrganizationDiscoveryPage } from './components/discovery/OrganizationDiscoveryPage';
import { LoginModal } from './components/common/LoginModal';
import { LandingPage } from './components/landing/LandingPage';
import { FloatingCopilotWidget } from './components/copilot/FloatingCopilotWidget';
import { ComplianceIntelligenceDashboard } from './components/intelligence/ComplianceIntelligenceDashboard';

import {
  NavSection,
  Regulation,
  ComplianceTask,
  RegulatorySource,
  AnalyticsOverview,
  AuditLog,
  TaskStatus,
} from './types';
import { ServiceAPI } from './services/api';
import { X, CheckSquare, Loader2, AlertCircle } from 'lucide-react';

// ---------------------------------------------------------------------------
// OrgSetupStatus — single source of truth for the organization's readiness.
// NEVER derived from HTTP status alone — always from the persisted domain state.
//
// Backend discovery_status lifecycle (domain.py):
//   UNINITIALIZED  → no setup started
//   DISCOVERING    → crawler is running (do NOT restart, do NOT ask for URL again)
//   REVIEW_PENDING → facts extracted, user must review before confirming
//   CONFIRMED      → human-reviewed and confirmed — setup is complete
// ---------------------------------------------------------------------------
export type OrgSetupStatus =
  | 'LOADING'           // Initial state: data not yet fetched
  | 'SETUP_REQUIRED'    // 404 OR discovery_status = UNINITIALIZED — show Discovery form
  | 'DISCOVERING'       // discovery_status = DISCOVERING — show progress, no re-crawl
  | 'REVIEW_PENDING'    // discovery_status = REVIEW_PENDING — show FactReviewConsole
  | 'SETUP_COMPLETE'    // discovery_status = CONFIRMED — show Compliance Overview
  | 'PROFILE_LOAD_ERROR'; // Network / 5xx — never silently treat as SETUP_REQUIRED

type CoreData = {
  regulations: Regulation[];
  tasks: ComplianceTask[];
  sources: RegulatorySource[];
  analytics: AnalyticsOverview | null;
  auditLogs: AuditLog[];
  enterpriseProfile: any;
  orgStatus: Exclude<OrgSetupStatus, 'LOADING'>;
};

/** Map backend discovery_status string → frontend OrgSetupStatus */
function resolveOrgStatus(discoveryStatus: string | null | undefined): Exclude<OrgSetupStatus, 'LOADING' | 'PROFILE_LOAD_ERROR'> {
  switch (discoveryStatus) {
    case 'CONFIRMED':      return 'SETUP_COMPLETE';
    case 'REVIEW_PENDING': return 'REVIEW_PENDING';
    case 'DISCOVERING':    return 'DISCOVERING';
    case 'UNINITIALIZED':
    default:               return 'SETUP_REQUIRED';
  }
}

async function fetchCoreData(): Promise<CoreData> {
  const [regulations, tasks, sources, analytics, auditLogs, enterpriseProfile] =
    await Promise.allSettled([
      ServiceAPI.getRegulations(),
      ServiceAPI.getTasks(),
      ServiceAPI.getSources(),
      ServiceAPI.getAnalyticsOverview(),
      ServiceAPI.getAuditLogs(),
      ServiceAPI.getEnterpriseProfile(),
    ]);

  let orgStatus: Exclude<OrgSetupStatus, 'LOADING'>;
  let profileValue = null;

  if (enterpriseProfile.status === 'fulfilled') {
    profileValue = enterpriseProfile.value;
    // Authority: domain field beats HTTP 200. A profile row with UNINITIALIZED
    // means setup is not complete — route to onboarding, not workspace.
    orgStatus = resolveOrgStatus(profileValue?.discovery_status);
  } else {
    const httpStatus = (enterpriseProfile.reason as any)?.response?.status;
    if (httpStatus === 404 || httpStatus === 401) {
      // No profile row (404) or unauthenticated (401) — default to SETUP_REQUIRED
      orgStatus = 'SETUP_REQUIRED';
    } else {
      // Network error, 500, etc. — never silently treat as new org
      orgStatus = 'PROFILE_LOAD_ERROR';
    }
  }

  return {
    regulations:
      regulations.status === 'fulfilled' ? regulations.value ?? [] : [],
    tasks:
      tasks.status === 'fulfilled' ? tasks.value ?? [] : [],
    sources:
      sources.status === 'fulfilled' ? sources.value ?? [] : [],
    analytics:
      analytics.status === 'fulfilled' ? analytics.value : null,
    auditLogs:
      auditLogs.status === 'fulfilled' ? auditLogs.value ?? [] : [],
    enterpriseProfile: profileValue,
    orgStatus,
  };
}

// ---------------------------------------------------------------------------
// Default persona shown before DB users load
// ---------------------------------------------------------------------------
const DEFAULT_PERSONA: UserPersona = {
  id: 'default-1',
  name: 'Sarah Jenkins',
  role: 'Compliance Officer',
  avatar: 'SJ',
};

// ---------------------------------------------------------------------------
// URL Synchronization & Routing (VAL-01)
// Synchronizes activeSection and selectedRegId with the browser URL
// ---------------------------------------------------------------------------
const VALID_NAV_SECTIONS: NavSection[] = [
  'landing',
  'organization-discovery',
  'workspace',
  'repository',
  'actions',
  'intelligence',
  'audit',
  'settings',
  'copilot',
];

function parseUrlRoute(): { section: NavSection; regId: string | null } {
  let pathname = window.location.pathname.replace(/^\/+|\/+$/g, '').trim();
  const hash = window.location.hash.replace(/^#\/?/, '').trim();

  if (!pathname && hash) {
    pathname = hash.split('?')[0];
  }

  const searchStr = window.location.search || (hash.includes('?') ? '?' + hash.split('?')[1] : '');
  const searchParams = new URLSearchParams(searchStr);
  let regId = searchParams.get('id') || searchParams.get('regId') || null;

  const segments = pathname.split('/').filter(Boolean);
  const sectionCandidate = (segments[0] || '').toLowerCase() as NavSection;

  if (VALID_NAV_SECTIONS.includes(sectionCandidate)) {
    if (sectionCandidate === 'repository' && segments[1] && !regId) {
      regId = decodeURIComponent(segments[1]);
    }
    return { section: sectionCandidate, regId };
  }

  return { section: 'landing', regId: null };
}

function computeUrlPath(section: NavSection, regId: string | null): string {
  if (section === 'landing') return '/';
  if (section === 'organization-discovery') return '/organization-discovery';
  if (section === 'repository' && regId) {
    return `/repository?id=${encodeURIComponent(regId)}`;
  }
  return `/${section}`;
}

export function App() {
  const initialRoute = parseUrlRoute();
  const [activeSection, setActiveSection] = useState<NavSection>(initialRoute.section);
  const [selectedRegId, setSelectedRegId] = useState<string | null>(initialRoute.regId);

  // Central navigation dispatcher that updates state and browser history
  const navigateTo = useCallback(
    (section: NavSection, regId: string | null = null, replace: boolean = false) => {
      setActiveSection(section);
      setSelectedRegId(regId);

      const targetPath = computeUrlPath(section, regId);
      const currentPath = window.location.pathname + window.location.search;

      if (currentPath !== targetPath) {
        if (replace) {
          window.history.replaceState({ section, regId }, '', targetPath);
        } else {
          window.history.pushState({ section, regId }, '', targetPath);
        }
      }
    },
    []
  );

  // Synchronize on browser Back / Forward (popstate)
  useEffect(() => {
    const handlePopState = () => {
      const { section, regId } = parseUrlRoute();
      setActiveSection(section);
      setSelectedRegId(regId);
    };

    window.addEventListener('popstate', handlePopState);

    const current = parseUrlRoute();
    const expected = computeUrlPath(current.section, current.regId);
    const actual = window.location.pathname + window.location.search;
    if (actual !== expected && actual !== '/' && actual !== '') {
      window.history.replaceState({ section: current.section, regId: current.regId }, '', expected);
    }

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Auth & Modal States (Single state machine — no redundant discovery booleans)
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [showManualSetupModal, setShowManualSetupModal] = useState(false);

  // Active user
  const [currentPersona, setCurrentPersona] = useState<UserPersona>(DEFAULT_PERSONA);

  // Core Datasets
  const [regulations, setRegulations] = useState<Regulation[]>([]);
  const [tasks, setTasks] = useState<ComplianceTask[]>([]);
  const [sources, setSources] = useState<RegulatorySource[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [enterpriseProfile, setEnterpriseProfile] = useState<any>(null);
  const [isDataLoaded, setIsDataLoaded] = useState(false);
  const [orgStatus, setOrgStatus] = useState<OrgSetupStatus>('LOADING');
  const [copilotInitialQuery, setCopilotInitialQuery] = useState<string>('');

  // Task creation modal
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDesc, setNewTaskDesc] = useState('');
  const [newTaskAssignee, setNewTaskAssignee] = useState(DEFAULT_PERSONA.name);
  const [newTaskPriority, setNewTaskPriority] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('HIGH');
  const [newTaskDueDate, setNewTaskDueDate] = useState('2026-09-15');
  const [taskSaving, setTaskSaving] = useState(false);

  // ---------------------------------------------------------------------------
  // loadData — single source of truth for all state hydration.
  // ---------------------------------------------------------------------------
  const loadData = useCallback(async () => {
    const data = await fetchCoreData();

    setRegulations(data.regulations);
    setTasks(data.tasks);
    setSources(data.sources);
    setAnalytics(data.analytics);
    setAuditLogs(data.auditLogs);

    setEnterpriseProfile(data.enterpriseProfile);
    setOrgStatus(data.orgStatus);
    setIsDataLoaded(true);
  }, []);

  // Load DB users and set persona from the first user returned
  const loadPersona = useCallback(async () => {
    try {
      const users = await ServiceAPI.getUsers();
      if (users && users.length > 0) {
        const u = users[0];
        const initials = u.full_name
          .split(' ')
          .map((n: string) => n[0])
          .join('')
          .toUpperCase()
          .slice(0, 2);
        setCurrentPersona({ id: u.id, name: u.full_name, role: u.role, avatar: initials });
        setNewTaskAssignee(u.full_name);
      }
    } catch {
      // Non-fatal
    }
  }, []);

  useEffect(() => {
    loadData();
    loadPersona();

    const handleAuthRequired = () => setShowLoginModal(true);
    window.addEventListener('auth_required', handleAuthRequired);
    return () => window.removeEventListener('auth_required', handleAuthRequired);
  }, [loadData, loadPersona]);

  // ---------------------------------------------------------------------------
  // Auth Handler
  // ---------------------------------------------------------------------------
  const handleLoginSuccess = (userData: any) => {
    setShowLoginModal(false);
    if (userData?.full_name) {
      const initials = userData.full_name
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
      setCurrentPersona({
        id: userData.user_id || 'user-1',
        name: userData.full_name,
        role: userData.role || 'Compliance Officer',
        avatar: initials,
      });
      setNewTaskAssignee(userData.full_name);
    }
    loadData();
    if (activeSection === 'landing') {
      navigateTo('workspace', null);
    }
  };

  // ---------------------------------------------------------------------------
  // Manual Profile Save Handler (Fallback)
  // ---------------------------------------------------------------------------
  const handleManualSaveProfile = async (profileData: any) => {
    const res = await ServiceAPI.saveEnterpriseProfile({
      ...profileData,
      discovery_status: 'CONFIRMED',
    });
    setEnterpriseProfile(res);
    setShowManualSetupModal(false);
    await loadData();
    navigateTo('workspace', null);
    return res;
  };

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------
  const handleSelectRegulation = (id: string) => {
    navigateTo('repository', id);
  };

  const openCopilotWithQuery = (query: string) => {
    setCopilotInitialQuery(query);
    navigateTo('copilot', null);
  };

  // ---------------------------------------------------------------------------
  // Task mutations
  // ---------------------------------------------------------------------------
  const handleUpdateTaskStatus = async (taskId: string, newStatus: TaskStatus) => {
    try {
      await ServiceAPI.updateTaskStatus(taskId, newStatus);
    } catch {
      // Non-fatal
    }
    const [updatedTasks, updatedAnalytics, updatedAudit] = await Promise.allSettled([
      ServiceAPI.getTasks(),
      ServiceAPI.getAnalyticsOverview(),
      ServiceAPI.getAuditLogs(),
    ]);
    if (updatedTasks.status === 'fulfilled') setTasks(updatedTasks.value ?? []);
    if (updatedAnalytics.status === 'fulfilled') setAnalytics(updatedAnalytics.value);
    if (updatedAudit.status === 'fulfilled') setAuditLogs(updatedAudit.value ?? []);
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    const regId =
      selectedRegId ||
      (regulations.length > 0 ? regulations[0].id : '');

    if (!regId) {
      console.warn('Cannot create task: no regulation available yet');
      return;
    }

    setTaskSaving(true);
    try {
      await ServiceAPI.createTask({
        regulation_id: regId,
        title: newTaskTitle,
        description: newTaskDesc,
        assignee: newTaskAssignee || currentPersona.name,
        reviewer: 'Chief Compliance Officer',
        priority: newTaskPriority,
        status: 'NEEDS_REVIEW',
        due_date: newTaskDueDate,
      });

      setShowTaskModal(false);
      setNewTaskTitle('');
      setNewTaskDesc('');

      const [updatedTasks, updatedAnalytics, updatedAudit] = await Promise.allSettled([
        ServiceAPI.getTasks(),
        ServiceAPI.getAnalyticsOverview(),
        ServiceAPI.getAuditLogs(),
      ]);
      if (updatedTasks.status === 'fulfilled') setTasks(updatedTasks.value ?? []);
      if (updatedAnalytics.status === 'fulfilled') setAnalytics(updatedAnalytics.value);
      if (updatedAudit.status === 'fulfilled') setAuditLogs(updatedAudit.value ?? []);
    } catch (err) {
      console.error('Task creation failed:', err);
    } finally {
      setTaskSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Derived state for badge counts
  // ---------------------------------------------------------------------------
  const selectedRegulation = regulations.find((r) => r.id === selectedRegId);

  const pendingReviewCount = tasks.filter(
    (t) => t && (t.status === 'WAITING_APPROVAL' || t.status === 'NEEDS_REVIEW')
  ).length;

  const navbarUnreadCount = 0;

  // ---------------------------------------------------------------------------
  // ROUTING & RENDERING — Driven strictly by activeSection and orgStatus
  // ---------------------------------------------------------------------------

  // 1. Landing Page Route
  if (activeSection === 'landing') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <LandingPage
          onNavigate={(sec) => {
            const isLoggedIn = !!localStorage.getItem('access_token');
            if (!isLoggedIn) {
              setShowLoginModal(true);
              return;
            }
            navigateTo(sec, null);
          }}
          onOpenLogin={() => setShowLoginModal(true)}
          orgStatus={orgStatus}
          onStartSetup={() => {
            const isLoggedIn = !!localStorage.getItem('access_token');
            if (!isLoggedIn) {
              setShowLoginModal(true);
              return;
            }
            navigateTo('workspace', null);
          }}
        />

        <LoginModal
          isOpen={showLoginModal}
          onSuccess={handleLoginSuccess}
          onClose={() => setShowLoginModal(false)}
        />
      </div>
    );
  }

  // 2. Loading State
  if (!isDataLoaded) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-100">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
          <p className="text-slate-400 font-medium">Loading your workspace...</p>
        </div>
      </div>
    );
  }

  // 3. Profile Load Error (Network / 5xx)
  if (orgStatus === 'PROFILE_LOAD_ERROR') {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-100 p-6">
        <div className="glass-panel p-8 rounded-2xl max-w-md w-full text-center space-y-4">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
          <h2 className="text-xl font-bold text-white">Initialization Error</h2>
          <p className="text-slate-400 text-sm">
            We couldn't connect to the server to load your organization profile. Please check your connection and try again.
          </p>
          <button onClick={() => { setIsDataLoaded(false); loadData(); }} className="btn-primary w-full mt-4">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // 4. Canonical Organization Discovery Route (/organization-discovery) or Unfinished Onboarding
  const isDedicatedDiscoveryRoute = activeSection === 'organization-discovery';
  const isUnfinishedOnboarding = orgStatus === 'SETUP_REQUIRED' || orgStatus === 'DISCOVERING' || orgStatus === 'REVIEW_PENDING';

  if (isDedicatedDiscoveryRoute || isUnfinishedOnboarding) {
    const isRediscoveryMode = isDedicatedDiscoveryRoute && orgStatus === 'SETUP_COMPLETE';
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <OrganizationDiscoveryPage
          mode={isRediscoveryMode ? 'rediscovery' : 'initial'}
          initialWebsite={isRediscoveryMode ? (enterpriseProfile?.website_url || '') : ''}
          orgStatus={isRediscoveryMode || orgStatus === 'SETUP_COMPLETE' ? 'SETUP_REQUIRED' : (orgStatus === 'LOADING' ? 'SETUP_REQUIRED' : orgStatus)}
          onComplete={async () => {
            await loadData();
            navigateTo('workspace', null);
          }}
          onSetupManually={isRediscoveryMode ? undefined : () => setShowManualSetupModal(true)}
          onCancel={() => navigateTo('settings', null)}
        />

        <EnterpriseSetupModal
          isOpen={showManualSetupModal}
          onClose={() => setShowManualSetupModal(false)}
          currentProfile={enterpriseProfile}
          onSaveProfile={handleManualSaveProfile}
        />

        <LoginModal
          isOpen={showLoginModal}
          onSuccess={handleLoginSuccess}
          onClose={() => setShowLoginModal(false)}
        />
      </div>
    );
  }

  // 5. Full Workspace (SETUP_COMPLETE / CONFIRMED)
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        onSearchClick={() => openCopilotWithQuery('')}
        onOpenTour={() => setShowTour(true)}
        onOpenSetup={() => navigateTo('settings', null)}
        onNavigateLanding={() => navigateTo('landing', null)}
        unreadNotifications={navbarUnreadCount}
        tasks={tasks}
        currentPersona={currentPersona}
        onSelectPersona={(persona) => {
          setCurrentPersona(persona);
          setNewTaskAssignee(persona.name);
        }}
      />

      <GuidedTourModal
        isOpen={showTour}
        onClose={() => setShowTour(false)}
        onNavigateSection={(sec) => {
          navigateTo(sec, null);
        }}
      />

      <EnterpriseSetupModal
        isOpen={showManualSetupModal}
        onClose={() => setShowManualSetupModal(false)}
        currentProfile={enterpriseProfile}
        onSaveProfile={handleManualSaveProfile}
      />

      <div className="flex-1 flex">
        <Sidebar
          activeSection={activeSection}
          onSelectSection={(sec) => {
            navigateTo(sec, sec === 'repository' ? selectedRegId : null);
          }}
          pendingReviewCount={pendingReviewCount}
        />

        <main className="flex-1 p-6 md:p-8 overflow-y-auto max-w-7xl mx-auto w-full">
          <ErrorBoundary>
            {activeSection === 'workspace' && (
              <CODashboard
                regulations={regulations}
                tasks={tasks}
                onSelectRegulation={handleSelectRegulation}
                onUpdateTaskStatus={handleUpdateTaskStatus}
                currentPersona={currentPersona}
                enterpriseProfile={enterpriseProfile}
                onNavigate={(section: string, regId?: string | null) => navigateTo(section as NavSection, regId || null)}
                onTriggerCrawl={async (sourceId) => {
                  const res = await ServiceAPI.triggerSourceCrawl(sourceId).catch(() => null);
                  const updatedRegs = await ServiceAPI.getRegulations().catch(() => regulations);
                  setRegulations(updatedRegs ?? []);
                  return res;
                }}
              />
            )}

            {activeSection === 'repository' && (
              <>
                {selectedRegulation ? (
                  <RegulationDetail
                    regulation={selectedRegulation}
                    onBack={() => navigateTo('repository', null)}
                    onCreateTask={(title, desc) => {
                      setNewTaskTitle(title);
                      setNewTaskDesc(desc);
                      setShowTaskModal(true);
                    }}
                    onOpenCopilot={openCopilotWithQuery}
                  />
                ) : (
                  <RegulationList
                    regulations={regulations}
                    onSelectRegulation={handleSelectRegulation}
                  />
                )}
              </>
            )}

            {/* Compliance Actions */}
            {activeSection === 'actions' && (
              <ComplianceActionsHub
                tasks={tasks}
                onUpdateStatus={handleUpdateTaskStatus}
                onCreateTaskClick={() => setShowTaskModal(true)}
              />
            )}

            {/* Compliance Intelligence */}
            {activeSection === 'intelligence' && (
              <ComplianceIntelligenceDashboard />
            )}

            {/* Audit & Defense */}
            {activeSection === 'audit' && (
              <AuditDefenseHub
                auditLogs={auditLogs}
                analytics={analytics}
              />
            )}

            {/* Settings */}
            {activeSection === 'settings' && (
              <SettingsHub
                sources={sources}
                onTriggerCrawl={async (id) =>
                  ServiceAPI.triggerSourceCrawl(id).catch(() => null)
                }
                onAddSource={async (sourceData) => {
                  const newSource = await ServiceAPI.createSource(sourceData);
                  const updatedSources = await ServiceAPI.getSources().catch(() => sources);
                  setSources(updatedSources ?? []);
                  return newSource;
                }}
                onDeleteSource={async (id) => {
                  await ServiceAPI.deleteSource(id).catch(() => null);
                  const updatedSources = await ServiceAPI.getSources().catch(
                    () => sources.filter((s) => s.id !== id)
                  );
                  setSources(updatedSources ?? []);
                }}
                onDiscoverAgain={() => navigateTo('organization-discovery', null)}
              />
            )}

            {/* Ambient Copilot full page */}
            {activeSection === 'copilot' && (
              <RAGCopilot initialQuery={copilotInitialQuery} />
            )}
          </ErrorBoundary>
        </main>
      </div>

      {/* Task Creation Modal */}
      {showTaskModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 w-full max-w-lg space-y-4 relative">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <CheckSquare className="w-5 h-5 text-brand-400" />
                Create New Compliance Task
              </h2>
              <button
                onClick={() => setShowTaskModal(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4 text-xs">
              <div className="form-group-region">
                <div>
                  <label className="form-label">Task Title</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Update Retail KYC SOP 3.2 for V-CIP re-verification"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div>
                  <label className="form-label">Action Description</label>
                  <textarea
                    rows={3}
                    placeholder="Enter detailed action plan..."
                    value={newTaskDesc}
                    onChange={(e) => setNewTaskDesc(e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              {/* Regulation context indicator */}
              {(selectedRegId || regulations.length > 0) && (
                <div className="p-2.5 rounded-xl bg-brand-600/10 border border-brand-500/20 text-[10px] text-brand-300">
                  <span className="font-bold">Linked Regulation: </span>
                  {regulations.find((r) => r.id === (selectedRegId || regulations[0]?.id))
                    ?.title ?? 'First available regulation'}
                </div>
              )}

              <div className="form-group-region">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="form-label">Assignee</label>
                    <input
                      type="text"
                      value={newTaskAssignee}
                      onChange={(e) => setNewTaskAssignee(e.target.value)}
                      className="form-input"
                    />
                  </div>
                  <div>
                    <label className="form-label">Priority</label>
                    <select
                      value={newTaskPriority}
                      onChange={(e) => setNewTaskPriority(e.target.value as any)}
                      className="form-input"
                    >
                      <option value="HIGH">HIGH PRIORITY</option>
                      <option value="MEDIUM">MEDIUM PRIORITY</option>
                      <option value="LOW">LOW PRIORITY</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="form-label">Enforcement Due Date</label>
                  <input
                    type="date"
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800 flex items-center justify-end space-x-3 mt-4">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={taskSaving || !newTaskTitle.trim()}
                  className="btn-primary"
                >
                  {taskSaving ? 'Creating...' : 'Create & Route Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <LoginModal
        isOpen={showLoginModal}
        onSuccess={handleLoginSuccess}
        onClose={() => setShowLoginModal(false)}
      />

      <FloatingCopilotWidget
        onOpenFullCopilot={(q) => openCopilotWithQuery(q || '')}
      />
    </div>
  );
}
