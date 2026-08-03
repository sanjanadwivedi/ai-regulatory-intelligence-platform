import axios from 'axios';
import {
  Regulation,
  ComplianceTask,
  RegulatorySource,
  CopilotResponse,
  AuditLog,
  AnalyticsOverview,
  TaskStatus
} from '../types';

const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
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
// ServiceAPI — all backend integration in one place.
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

  // ---------------------------------------------------------------------------
  // Regulatory Sources — Bounded Context: Regulatory Intelligence
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
  // Regulations — Bounded Context: Regulatory Knowledge
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
  // Compliance Tasks — Bounded Context: Compliance Workflow
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

  // ---------------------------------------------------------------------------
  // AI Copilot — Infrastructure: RAG / LLM
  // ---------------------------------------------------------------------------
  queryCopilot: async (query: string, regulation_id?: string): Promise<CopilotResponse> => {
    const res = await api.post('/copilot/query', { query, regulation_id });
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Analytics & Audit — Bounded Context: Reporting & Audit
  // ---------------------------------------------------------------------------
  getAnalyticsOverview: async (): Promise<AnalyticsOverview> => {
    const res = await api.get('/analytics/overview');
    return res.data;
  },

  getAuditLogs: async (): Promise<AuditLog[]> => {
    const res = await api.get('/audit-logs');
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Notifications — Bounded Context: Notification
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
  // Knowledge Graph — Bounded Context: Regulatory Knowledge
  // ---------------------------------------------------------------------------
  getKnowledgeGraph: async (regulationId?: string): Promise<any> => {
    const regId = regulationId || '';
    if (!regId) return null;
    const res = await api.get(`/impact/${regId}/graph`);
    return res.data;
  },

  // ---------------------------------------------------------------------------
  // Enterprise Profile & Users — Bounded Context: Identity & Security
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
  // Golden Evaluation Benchmark — Bounded Context: Reporting & Audit
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
};
