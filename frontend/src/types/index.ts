export type NavSection =
  | 'workspace'
  | 'repository'
  | 'graph'
  | 'reviews'
  | 'cases'
  | 'copilot'
  | 'sources'
  | 'insights'
  | 'security'
  | 'batch_re_extract';


export type TaskStatus =
  | 'NEW'
  | 'NEEDS_REVIEW'
  | 'MY_TASKS'
  | 'WAITING_APPROVAL'
  | 'DUE_TODAY'
  | 'COMPLETED';

export type RiskLevelType = 'HIGH' | 'MEDIUM' | 'LOW';

export interface Requirement {
  id: string;
  requirement_text: string;
  deadline?: string;
  penalty_description?: string;
  statutory_reference?: string;
  affected_entities?: string[];
}

export interface Obligation {
  id: string;
  summary: string;
  requirements?: Requirement[];
}

export interface Section {
  id: string;
  section_number: string;
  title: string;
  content_text: string;
  obligations?: Obligation[];
}

export interface KnowledgeGraphChain {
  id: string;
  regulation_id: string;
  requirement_id?: string;
  control_code: string;
  policy_code: string;
  process_code: string;
  department_name: string;
  application_code: string;
}

export interface Regulation {
  id: string;
  title: string;
  authority: string;
  doc_number?: string;
  publication_date: string;
  effective_date?: string;
  sector: string;
  region: string;
  content_text: string;
  source_url?: string;
  resolved_source_url?: string | null;
  status: string;
  extraction_method?: string;
  calibration_score?: number;
  ocr_confidence?: number;
  needs_human_review?: number;
  // Source-URL live grounding verification (0 = unchecked, 1 = verified, -1 = mismatch)
  source_url_verified?: number;
  source_url_verification_score?: number | null;
  source_url_last_verified_at?: string | null;
  source_url_verification_note?: string | null;
  possible_amendment_detected?: number;
  created_at: string;
  sections?: Section[];
  graph_chains?: KnowledgeGraphChain[];
}



export interface ComplianceTask {
  id: string;
  regulation_id: string;
  regulation_title?: string;
  control_code?: string;
  title: string;
  description?: string;
  assignee: string;
  reviewer: string;
  priority: RiskLevelType;
  status: TaskStatus;
  due_date: string;
  created_at?: string;
  updated_at?: string;
}

export interface RegulatorySource {
  id: string;
  authority_name: string;
  feed_url: string;
  feed_type: string;
  fetch_schedule: string;
  region: string;
  sector: string;
  status: string;
  last_fetched_at: string;
}

export interface CopilotCitation {
  regulation_id: string;
  regulation_title: string;
  authority: string;
  section_text: string;
  relevance_score: number;
  page_number?: number;
  paragraph_number?: number;
  evidence_star_rating?: string;
  highlighted_sentence?: string;
}

export type GroundedCitation = CopilotCitation;


export interface CopilotResponse {
  answer: string;
  grounded_citations: CopilotCitation[];
  confidence_score: number;
  model_version: string;
}

export interface AuditLog {
  id: string;
  user_name: string;
  user_role: string;
  action: string;
  target_type: string;
  target_id?: string;
  details?: Record<string, any>;
  created_at: string;
}

export interface AnalyticsOverview {
  total_regulations: number;
  high_impact_count: number;
  open_tasks: number;
  completed_tasks: number;
  compliance_score: number;
  review_turnaround_days: number;
  risk_distribution: Record<string, number>;
}
