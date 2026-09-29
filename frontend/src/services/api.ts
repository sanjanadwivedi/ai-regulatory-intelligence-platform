/// <reference types="vite/client" />
import axios from 'axios';
import {
  Regulation,
  ComplianceTask,
  RegulatorySource,
  CopilotResponse,
  AuditLog,
  AnalyticsOverview,
  TaskStatus,
  CompliancePostureResponse,
  ComplianceAlert,
  ComplianceIntelligenceSnapshot,
  ComplianceDefensePack,
  ComplianceEvidenceManifest,
  OrganizationPostureResponse,
  RegulationPostureResponse,
  ObligationPostureResponse,
  InternalControl,
  ObligationControlMapping,
  RegulatoryIntelligenceSummary,
  RegulatoryChangeFeedResponse,
  RegulatoryChangeDetail,
  RegulatoryChangeReviewRequest,
  RegulatoryChangeReviewResponse
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});


api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_info');
      window.dispatchEvent(new Event('auth_required'));
    }
    return Promise.reject(error);
  }
);

// Export the raw axios instance so components can use it directly
export { api };

// ---------------------------------------------------------------------------
// ServiceAPI â€” all backend integration in one place.
// Silent fallbacks are intentional: the platform degrades gracefully when
// the backend is unreachable (dev mode, first boot, no seed yet).
// ---------------------------------------------------------------------------

export const ServiceAPI = {
  login: async (email: string, password: string): Promise<any> => {
    const res = await api.post('/auth/login', { email, password });
    if (res.data.access_token) {
      localStorage.setItem('access_token', res.data.access_token);
      localStorage.setItem('user_info', JSON.stringify(res.data));
    }
    return res.data;
  },

  register: async (full_name: string, email: string, password: string, role?: string): Promise<any> => {
    const res = await api.post('/auth/register', { full_name, email, password, role: role || 'Compliance Officer' });
    if (res.data.access_token) {
      localStorage.setItem('access_token', res.data.access_token);
      localStorage.setItem('user_info', JSON.stringify(res.data));
    }
    return res.data;
  },


  // ---------------------------------------------------------------------------
  // Regulatory Sources â€” Bounded Context: Regulatory Intelligence
  // ---------------------------------------------------------------------------
  getSources: async (): Promise<RegulatorySource[]> => {
    const res = await api.get('/sources');
    return res.data;
  },

  triggerSourceCrawl: async (id: string) => {
    const res = await api.post(`/sources/${id}/trigger`);
    return res.data;
  },

  createSource: async (
    sourceData: Omit<RegulatorySource, 'id' | 'last_fetched_at'>
  ): Promise<RegulatorySource> => {
    const res = await api.post('/sources', sourceData);
    return res.data;
  },

  deleteSource: async (id: string): Promise<any> => {
    const res = await api.delete(`/sources/${id}`);
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Regulations â€” Bounded Context: Regulatory Knowledge
  // ---------------------------------------------------------------------------
  getRegulations: async (search?: string): Promise<Regulation[]> => {
    const res = await api.get('/regulations', { params: { search } });
    return res.data;
  },

  getRegulationById: async (id: string): Promise<Regulation> => {
    const res = await api.get(`/regulations/${id}`);
    return res.data;
  },

  getExtractionAudit: async (regId: string): Promise<any> => {
    const res = await api.get(`/regulations/${regId}/extraction-audit`);
    return res.data;
  },

  getSourceDiff: async (regId: string): Promise<any> => {
    const res = await api.get(`/regulations/${regId}/source-diff`);
    return res.data;
  },

  resolveSourceUrl: async (regId: string): Promise<any> => {
    const res = await api.post(`/regulations/${regId}/resolve-source-url`);
    return res.data;
  },

  re_extract_regulation: async (regId: string): Promise<any> => {
    const res = await api.post(`/regulations/${regId}/re-extract`);
    return res.data;
  },

  batch_re_extract: async (payload: any): Promise<any> => {
    const res = await api.post('/regulations/batch-re-extract', payload);
    return res.data;
  },





  getHumanReviewQueue: async (): Promise<any[]> => {
    const res = await api.get('/regulations/human-review-queue');
    return res.data;
  },

  approveIngestion: async (regId: string, correctedText?: string): Promise<any> => {
    const res = await api.post(`/regulations/${regId}/approve-ingestion`, {
      corrected_text: correctedText,
    });
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Compliance Tasks â€” Bounded Context: Compliance Workflow
  // ---------------------------------------------------------------------------
  getTasks: async (): Promise<ComplianceTask[]> => {
    const res = await api.get('/tasks');
    return res.data;
  },

  createTask: async (
    taskData: Omit<ComplianceTask, 'id' | 'created_at' | 'updated_at'>
  ): Promise<ComplianceTask> => {
    const res = await api.post('/tasks', taskData);
    return res.data;
  },

  updateTaskStatus: async (taskId: string, status: TaskStatus): Promise<ComplianceTask> => {
    const res = await api.put(`/tasks/${taskId}`, { status });
    return res.data;
  },

  completeTask: async (taskId: string, notes?: string): Promise<ComplianceTask> => {
    const payload = notes ? { notes } : {};
    const res = await api.post(`/tasks/${taskId}/complete`, payload);
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // AI Copilot â€” Infrastructure: RAG / LLM
  // ---------------------------------------------------------------------------
  queryCopilot: async (query: string, regulation_id?: string): Promise<CopilotResponse> => {
    const res = await api.post('/copilot/query', { query, regulation_id });
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Dashboard Metrics & Reporting
  // ---------------------------------------------------------------------------
  getAnalyticsOverview: async (): Promise<AnalyticsOverview> => {
    const res = await api.get('/analytics/overview');
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Compliance Intelligence & Defense Pack Layer
  // ---------------------------------------------------------------------------
  generateComplianceSnapshot: async (): Promise<ComplianceIntelligenceSnapshot> => {
    const res = await api.post('/compliance/intelligence/snapshot', {});
    return res.data;
  },

  getComplianceSnapshot: async (): Promise<ComplianceIntelligenceSnapshot> => {
    const res = await api.get('/compliance/intelligence/snapshot');
    return res.data;
  },

  getComplianceSnapshotById: async (id: string): Promise<ComplianceIntelligenceSnapshot> => {
    const res = await api.get(`/compliance/intelligence/snapshot/${id}`);
    return res.data;
  },

  generateDefensePack: async (snapshotId: string): Promise<ComplianceDefensePack> => {
    const res = await api.post('/compliance/defense-pack/generate', { snapshot_id: snapshotId });
    return res.data;
  },

  getDefensePacks: async (): Promise<ComplianceDefensePack[]> => {
    const res = await api.get('/compliance/defense-pack');
    return res.data;
  },

  getDefensePack: async (id: string): Promise<ComplianceDefensePack> => {
    const res = await api.get(`/compliance/defense-pack/${id}`);
    return res.data;
  },

  getDefensePackManifest: async (id: string): Promise<ComplianceEvidenceManifest[]> => {
    const res = await api.get(`/compliance/defense-pack/${id}/manifest`);
    return res.data;
  },

  exportDefensePack: async (id: string): Promise<any> => {
    const res = await api.get(`/compliance/defense-pack/${id}/export`);
    return res.data;
  },

  getAuditLogs: async (): Promise<AuditLog[]> => {
    const res = await api.get('/audit-logs');
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Notifications â€” Bounded Context: Notification
  // Requires auth token. Falls back silently to [] if the user is not yet
  // authenticated (the Navbar calls this on mount before login completes).
  // ---------------------------------------------------------------------------
  getNotifications: async (): Promise<any[]> => {
    const token = localStorage.getItem('access_token');
    if (!token) return [];
    try {
      const res = await api.get('/notifications');
      return res.data;
    } catch {
      // Non-fatal: notification panel shows empty state, doesn't break the app.
      return [];
    }
  },

  markNotificationRead: async (notificationId: string): Promise<any> => {
    const res = await api.post('/notifications/mark-read', {
      notification_id: notificationId,
    });
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Knowledge Graph â€” Bounded Context: Regulatory Knowledge
  // ---------------------------------------------------------------------------
  getKnowledgeGraph: async (regulationId?: string): Promise<any> => {
    const regId = regulationId || '';
    if (!regId) return null;
    const res = await api.get(`/impact/${regId}/graph`);
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Enterprise Profile & Users â€” Bounded Context: Identity & Security
  // ---------------------------------------------------------------------------
  getEnterpriseProfile: async (): Promise<any> => {
    const res = await api.get('/enterprise/profile');
    return res.data;
  },

  saveEnterpriseProfile: async (profileData: {
    organization_name: string;
    industry_sector: string;
    departments: string[];
    country?: string;
    regulator_region?: string;
    discovery_status?: string;
  }): Promise<any> => {
    const res = await api.post('/enterprise/profile', profileData);
    return res.data;
  },

  getUsers: async (): Promise<any[]> => {
    const res = await api.get('/enterprise/users');
    return res.data;
  },

  createUser: async (userData: {
    full_name: string;
    role: string;
    email?: string;
  }): Promise<any> => {
    const res = await api.post('/enterprise/users', userData);
    return res.data;
  },

  deleteUser: async (userId: string): Promise<any> => {
    const res = await api.delete(`/enterprise/users/${userId}`);
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Golden Evaluation Benchmark â€” Bounded Context: Reporting & Audit
  // ---------------------------------------------------------------------------
  getGoldenBenchmark: async (): Promise<any> => {
    // Try the canonical evals endpoint first; fall back to regulations-namespaced alias
    try {
      const res = await api.get('/evals/golden-benchmark');
      return res.data;
    } catch {
      const res = await api.get('/regulations/evals/golden-benchmark');
      return res.data;
    }
  },

  // ---------------------------------------------------------------------------
  // Discovery â€” Organization Discovery Service
  // ---------------------------------------------------------------------------
  startDiscovery: async (websiteUrl: string): Promise<any> => {
    const res = await api.post('/discovery/start', { website_url: websiteUrl });
    return res.data;
  },
  
  getDiscoveryFacts: async (status?: string, factType?: string): Promise<any[]> => {
    const params: Record<string, string> = {};
    if (status) params.status = status;
    if (factType) params.fact_type = factType;
    const res = await api.get('/discovery/facts', { params });
    return res.data;
  },
  
  confirmFact: async (factId: string): Promise<any> => {
    const res = await api.post(`/discovery/facts/${factId}/confirm`);
    return res.data;
  },
  
  editFact: async (factId: string, factValue: string): Promise<any> => {
    const res = await api.put(`/discovery/facts/${factId}/edit`, { fact_value: factValue });
    return res.data;
  },
  
  rejectFact: async (factId: string): Promise<any> => {
    const res = await api.post(`/discovery/facts/${factId}/reject`);
    return res.data;
  },
  
  bulkConfirmFacts: async (minConfidence?: number): Promise<any> => {
    const res = await api.post('/discovery/facts/bulk-confirm', { min_confidence: minConfidence || 0.85 });
    return res.data;
  },
  
  finalizeDiscovery: async (): Promise<any> => {
    const res = await api.post('/discovery/finalize');
    return res.data;
  },
  
  getDiscoveryStatus: async (): Promise<any> => {
    const res = await api.get('/discovery/status');
    return res.data;
  },

  // --- Regulatory Applicability Engine API ---
  evaluateApplicability: async (): Promise<any[]> => {
    const res = await api.post('/regulatory/applicability/evaluate');
    return res.data;
  },

  getApplicabilityAssessments: async (params?: { status?: string; regulation_id?: string }): Promise<any[]> => {
    const res = await api.get('/regulatory/applicability', { params });
    return res.data;
  },

  getApplicabilityAssessment: async (assessmentId: string): Promise<any> => {
    const res = await api.get(`/regulatory/applicability/${assessmentId}`);
    return res.data;
  },

  getApplicabilityReviews: async (params?: { status?: string; regulation_id?: string }): Promise<any[]> => {
    const res = await api.get('/regulatory/applicability/reviews', { params });
    return res.data;
  },

  resolveApplicabilityReview: async (reviewId: string, payload: {
    evidence_fact_value: string;
    evidence_type: string;
    evidence_strength: string;
    source_url: string;
    snippet?: string;
    known_state?: string;
  }): Promise<any> => {
    const res = await api.post(`/regulatory/applicability/reviews/${reviewId}/resolve`, payload);
    return res.data;
  },

  // --- Regulatory Obligation Engine API ---
  generateObligations: async (): Promise<any[]> => {
    const res = await api.post('/regulatory/obligations/generate');
    return res.data;
  },

  getObligations: async (params?: {
    regulation_id?: string;
    status?: string;
    obligation_type?: string;
    priority?: string;
  }): Promise<any[]> => {
    const res = await api.get('/regulatory/obligations', { params });
    return res.data;
  },

  getObligation: async (obligationId: string): Promise<any> => {
    const res = await api.get(`/regulatory/obligations/${obligationId}`);
    return res.data;
  },

  // --- Compliance Tasks & Action Engine API ---
  getComplianceTasks: async (params?: {
    status?: string;
    priority?: string;
    responsible_function?: string;
    regulation_id?: string;
    regulatory_obligation_id?: string;
  }): Promise<ComplianceTask[]> => {
    const res = await api.get('/tasks', { params });
    return res.data;
  },

  generateComplianceTasks: async (): Promise<ComplianceTask[]> => {
    const res = await api.post('/tasks/generate');
    return res.data;
  },

  updateComplianceTaskStatus: async (taskId: string, status: TaskStatus): Promise<ComplianceTask> => {
    const res = await api.put(`/tasks/${taskId}`, { status });
    return res.data;
  },

  createComplianceTask: async (taskData: any): Promise<ComplianceTask> => {
    const res = await api.post('/tasks', taskData);
    return res.data;
  },

  assignComplianceTask: async (taskId: string, data: { assignee: string; responsible_function?: string; notes?: string }): Promise<ComplianceTask> => {
    const res = await api.post(`/tasks/${taskId}/assign`, data);
    return res.data;
  },

  completeComplianceTask: async (taskId: string, confirmationNotes?: string): Promise<ComplianceTask> => {
    const res = await api.post(`/tasks/${taskId}/complete`, { confirmation_notes: confirmationNotes });
    return res.data;
  },

  reopenComplianceTask: async (taskId: string, reopenReason: string): Promise<ComplianceTask> => {
    const res = await api.post(`/tasks/${taskId}/reopen`, { reopen_reason: reopenReason });
    return res.data;
  },

  uploadComplianceTaskEvidence: async (taskId: string, evidenceData: {
    evidence_type: string;
    file_name: string;
    file_url?: string;
    description?: string;
  }): Promise<any> => {
    const res = await api.post(`/tasks/${taskId}/evidence`, evidenceData);
    return res.data;
  },

  getComplianceTaskEvidence: async (taskId: string): Promise<any[]> => {
    const res = await api.get(`/tasks/${taskId}/evidence`);
    return res.data;
  },

  getComplianceTaskActivities: async (taskId: string): Promise<any[]> => {
    const res = await api.get(`/tasks/${taskId}/activities`);
    return res.data;
  },

  addComplianceTaskComment: async (taskId: string, commentText: string): Promise<any> => {
    const res = await api.post(`/tasks/${taskId}/comments`, { comment_text: commentText });
    return res.data;
  },

  // --- Trigger Events API ---
  recordTriggerEvent: async (eventData: {
    event_type: string;
    event_timestamp: string;
    source: string;
    description: string;
    event_metadata?: Record<string, any>;
  }): Promise<any> => {
    const res = await api.post('/compliance/events', eventData);
    return res.data;
  },

  getTriggerEvents: async (params?: { event_type?: string }): Promise<any[]> => {
    const res = await api.get('/compliance/events', { params });
    return res.data;
  },

  // --- Compliance Monitoring & Intelligence API ---
  getCompliancePosture: async (): Promise<CompliancePostureResponse> => {
    const res = await api.get('/compliance/posture');
    return res.data;
  },

  getComplianceAlerts: async (params?: {
    severity?: string;
    alert_type?: string;
    status?: string;
    regulation_id?: string;
    obligation_id?: string;
    task_id?: string;
  }): Promise<ComplianceAlert[]> => {
    const res = await api.get('/compliance/alerts', { params });
    return res.data;
  },

  getComplianceAlert: async (alertId: string): Promise<ComplianceAlert> => {
    const res = await api.get(`/compliance/alerts/${alertId}`);
    return res.data;
  },



  resolveComplianceAlert: async (alertId: string, resolutionNotes: string): Promise<ComplianceAlert> => {
    const res = await api.post(`/compliance/alerts/${alertId}/resolve`, { resolution_notes: resolutionNotes });
    return res.data;
  },

  // --- Posture Breakdown (used by UnifiedAnalyticsDashboard) ---
  getOrganizationPosture: async (): Promise<OrganizationPostureResponse> => {
    const res = await api.get('/posture/organization');
    return res.data;
  },

  getRegulationPostures: async (): Promise<RegulationPostureResponse[]> => {
    const res = await api.get('/posture/regulations');
    return res.data;
  },

  getObligationPostures: async (): Promise<ObligationPostureResponse[]> => {
    const res = await api.get('/posture/obligations');
    return res.data;
  },

  getOrganizationPostureHistory: async (): Promise<OrganizationPostureResponse[]> => {
    const res = await api.get('/posture/organization/history');
    return res.data;
  },

  // --- Internal Controls (used by ControlsLibrary) ---
  getControls: async (): Promise<InternalControl[]> => {
    const res = await api.get('/controls');
    return res.data;
  },

  createControl: async (data: Partial<InternalControl>): Promise<InternalControl> => {
    const res = await api.post('/controls', data);
    return res.data;
  },

  mapControlToObligation: async (controlId: string, obligationId: string, rationale: string): Promise<ObligationControlMapping> => {
    const res = await api.post(`/controls/${controlId}/map`, { obligation_id: obligationId, rationale });
    return res.data;
  },

  // --- Phase 21A Regulatory Intelligence ---
  getRegulatoryIntelligenceSummary: async (): Promise<RegulatoryIntelligenceSummary> => {
    const res = await api.get('/regulatory-intelligence/summary');
    return res.data;
  },

  getRegulatoryChanges: async (skip: number = 0, limit: number = 20, regulationId?: string): Promise<RegulatoryChangeFeedResponse> => {
    const params: any = { skip, limit };
    if (regulationId) params.regulation_id = regulationId;
    const res = await api.get('/regulatory-intelligence/changes', { params });
    return res.data;
  },

  getRegulatoryChange: async (changeId: string): Promise<RegulatoryChangeDetail> => {
    const res = await api.get(`/regulatory-intelligence/changes/${changeId}`);
    return res.data;
  },

  reviewRegulatoryChange: async (changeId: string, payload: RegulatoryChangeReviewRequest): Promise<RegulatoryChangeReviewResponse> => {
    const res = await api.post(`/regulatory-intelligence/changes/${changeId}/review`, payload);
    return res.data;
  },

  propagateChangeImpact: async (changeId: string): Promise<any> => {
    const res = await api.post(`/regulatory-intelligence/changes/${changeId}/propagate-impact`);
    return res.data;
  },

  getChangeImpact: async (changeId: string): Promise<any[]> => {
    const res = await api.get(`/regulatory-intelligence/changes/${changeId}/impact`);
    return res.data;
  },

  verifyHumanSource: async (regulationId: string, verifiedUrl: string, notes?: string): Promise<any> => {
    const res = await api.post(`/regulations/${regulationId}/verify-human-source`, { url: verifiedUrl });
    return res.data;
  }
};

export const apiService = ServiceAPI;
