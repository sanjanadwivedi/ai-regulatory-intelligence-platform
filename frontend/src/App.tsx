import React, { useEffect, useState, useCallback } from 'react';
import { Navbar, UserPersona } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { CODashboard } from './components/dashboard/CODashboard';
import { RegulationList } from './components/regulations/RegulationList';
import { RegulationDetail } from './components/regulations/RegulationDetail';
import { KnowledgeGraphCanvas } from './components/graph/KnowledgeGraphCanvas';
import { TaskKanbanBoard } from './components/tasks/TaskKanbanBoard';
import { ReviewsConsole } from './components/reviews/ReviewsConsole';
import { RAGCopilot } from './components/copilot/RAGCopilot';
import { SourceManager } from './components/sources/SourceManager';
import { AnalyticsConsole } from './components/analytics/AnalyticsConsole';
import { AuditConsole } from './components/analytics/AuditConsole';
import { BatchReExtractionDashboard } from './components/admin/BatchReExtractionDashboard';
import { GuidedTourModal } from './components/common/GuidedTourModal';

import { EnterpriseSetupModal } from './components/common/EnterpriseSetupModal';
import { LoginModal } from './components/common/LoginModal';
import { LandingPage } from './components/landing/LandingPage';

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
import { X, CheckSquare } from 'lucide-react';

// ---------------------------------------------------------------------------
// Helper — reload all core datasets after any mutation.
// Centralised here so every handler calls one function, not ad-hoc subsets.
// Analytics must always refresh alongside tasks so metric counts stay correct.
// ---------------------------------------------------------------------------
type CoreData = {
  regulations: Regulation[];
  tasks: ComplianceTask[];
  sources: RegulatorySource[];
  analytics: AnalyticsOverview | null;
  auditLogs: AuditLog[];
  enterpriseProfile: any;
};

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
    enterpriseProfile:
      enterpriseProfile.status === 'fulfilled' ? enterpriseProfile.value : null,
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

export function App() {
  const [activeSection, setActiveSection] = useState<NavSection>('landing');
  const [selectedRegId, setSelectedRegId] = useState<string | null>(null);

  // Auth & Modal States
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [showSetupModal, setShowSetupModal] = useState(false);

  // Active user
  const [currentPersona, setCurrentPersona] =
    useState<UserPersona>(DEFAULT_PERSONA);

  // Core Datasets
  const [regulations, setRegulations] = useState<Regulation[]>([]);
  const [tasks, setTasks] = useState<ComplianceTask[]>([]);
  const [sources, setSources] = useState<RegulatorySource[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [enterpriseProfile, setEnterpriseProfile] = useState<any>(null);
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
  // Always called after login, and after any mutation that changes counts.
  // ---------------------------------------------------------------------------
  const loadData = useCallback(async () => {
    const data = await fetchCoreData();

    setRegulations(data.regulations);
    setTasks(data.tasks);
    setSources(data.sources);
    setAnalytics(data.analytics);
    setAuditLogs(data.auditLogs);

    if (data.enterpriseProfile) {
      setEnterpriseProfile(data.enterpriseProfile);
    }
  }, []);

  // Load DB users and set persona from the first user returned.
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
      // Non-fatal: keep default persona
    }
  }, []);

  useEffect(() => {
    const isLoggedIn = !!localStorage.getItem('access_token');
    if (isLoggedIn) {
      loadData();
      loadPersona();
    }

    const handleAuthRequired = () => setShowLoginModal(true);
    window.addEventListener('auth_required', handleAuthRequired);
    return () => window.removeEventListener('auth_required', handleAuthRequired);
  }, [loadData, loadPersona]);

  // ---------------------------------------------------------------------------
  // Auth
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
  };

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------
  const handleSelectRegulation = (id: string) => {
    setSelectedRegId(id);
    setActiveSection('repository');
  };

  const openCopilotWithQuery = (query: string) => {
    setCopilotInitialQuery(query);
    setActiveSection('copilot');
  };

  // ---------------------------------------------------------------------------
  // Task mutations — always re-fetch analytics so metric counts stay current
  // ---------------------------------------------------------------------------
  const handleUpdateTaskStatus = async (taskId: string, newStatus: TaskStatus) => {
    try {
      await ServiceAPI.updateTaskStatus(taskId, newStatus);
    } catch {
      // status update failed — still refresh so UI stays consistent with backend
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

    // Prefer the currently-selected regulation; fall back to the first real
    // regulation in state rather than a hardcoded demo ID.
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

      // Refresh tasks + analytics + audit in parallel
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

  // Unread notification count comes from live notifications fetched by Navbar.
  // We pass 0 here to avoid double-counting — Navbar manages its own count.
  const navbarUnreadCount = 0;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {activeSection !== 'landing' && (
        <Navbar
          onSearchClick={() => openCopilotWithQuery('')}
          onOpenTour={() => setShowTour(true)}
          onOpenSetup={() => setShowSetupModal(true)}
          onNavigateLanding={() => setActiveSection('landing')}
          unreadNotifications={navbarUnreadCount}
          tasks={tasks}
          currentPersona={currentPersona}
          onSelectPersona={(persona) => {
            setCurrentPersona(persona);
            setNewTaskAssignee(persona.name);
          }}
        />
      )}

      <GuidedTourModal
        isOpen={showTour}
        onClose={() => setShowTour(false)}
        onNavigateSection={(sec) => {
          setSelectedRegId(null);
          setActiveSection(sec);
        }}
      />

      <EnterpriseSetupModal
        isOpen={showSetupModal}
        onClose={() => setShowSetupModal(false)}
        currentProfile={enterpriseProfile}
        onSaveProfile={async (profileData) => {
          const res = await ServiceAPI.saveEnterpriseProfile(profileData);
          setEnterpriseProfile(res);
          await loadData();
          return res;
        }}
      />

      {activeSection === 'landing' ? (
        <LandingPage
          onNavigate={(sec) => {
            const isLoggedIn = !!localStorage.getItem('access_token');
            if (!isLoggedIn) {
              setShowLoginModal(true);
              return;
            }
            setSelectedRegId(null);
            setActiveSection(sec);
          }}
          onOpenLogin={() => setShowLoginModal(true)}
        />
      ) : (
        <div className="flex-1 flex">
          <Sidebar
            activeSection={activeSection}
            onSelectSection={(sec) => {
              if (sec !== 'repository') setSelectedRegId(null);
              setActiveSection(sec);
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
                onTriggerCrawl={async (sourceId) => {
                  const res = await ServiceAPI.triggerSourceCrawl(sourceId).catch(
                    () => null
                  );
                  const updatedRegs = await ServiceAPI.getRegulations().catch(
                    () => regulations
                  );
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
                    onBack={() => setSelectedRegId(null)}
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

            {activeSection === 'graph' && (
              <KnowledgeGraphCanvas
                regulationId={selectedRegId || regulations[0]?.id}
              />
            )}

            {activeSection === 'reviews' && (
              <ReviewsConsole
                tasks={tasks}
                onUpdateStatus={handleUpdateTaskStatus}
              />
            )}

            {activeSection === 'cases' && (
              <TaskKanbanBoard
                tasks={tasks}
                onUpdateStatus={handleUpdateTaskStatus}
                onCreateTaskClick={() => setShowTaskModal(true)}
              />
            )}

            {activeSection === 'copilot' && (
              <RAGCopilot initialQuery={copilotInitialQuery} />
            )}

            {activeSection === 'sources' && (
              <SourceManager
                sources={sources}
                onTriggerCrawl={async (id) =>
                  ServiceAPI.triggerSourceCrawl(id).catch(() => null)
                }
                onAddSource={async (sourceData) => {
                  const newSource = await ServiceAPI.createSource(sourceData);
                  const updatedSources = await ServiceAPI.getSources().catch(
                    () => sources
                  );
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
              />
            )}

            {activeSection === 'insights' && (
              <AnalyticsConsole analytics={analytics} auditLogs={auditLogs} />
            )}

            {activeSection === 'security' && (
              <AuditConsole auditLogs={auditLogs} />
            )}

            {activeSection === 'batch_re_extract' && (
              <BatchReExtractionDashboard />
            )}

          </ErrorBoundary>
        </main>
      </div>
      )}


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
              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block">Task Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Update Retail KYC SOP 3.2 for V-CIP re-verification"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block">Action Description</label>
                <textarea
                  rows={3}
                  placeholder="Enter detailed action plan..."
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              {/* Regulation context indicator */}
              {(selectedRegId || regulations.length > 0) && (
                <div className="p-2.5 rounded-xl bg-brand-600/10 border border-brand-500/20 text-[10px] text-brand-300">
                  <span className="font-bold">Linked Regulation: </span>
                  {regulations.find((r) => r.id === (selectedRegId || regulations[0]?.id))
                    ?.title ?? 'First available regulation'}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold block">Assignee</label>
                  <input
                    type="text"
                    value={newTaskAssignee}
                    onChange={(e) => setNewTaskAssignee(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold block">Priority</label>
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as any)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
                  >
                    <option value="HIGH">HIGH PRIORITY</option>
                    <option value="MEDIUM">MEDIUM PRIORITY</option>
                    <option value="LOW">LOW PRIORITY</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block">Enforcement Due Date</label>
                <input
                  type="date"
                  value={newTaskDueDate}
                  onChange={(e) => setNewTaskDueDate(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-900 text-slate-300 hover:text-white border border-slate-800 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={taskSaving || !newTaskTitle.trim()}
                  className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold shadow-lg shadow-brand-600/30 disabled:opacity-50 disabled:cursor-not-allowed"
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
    </div>
  );
}
