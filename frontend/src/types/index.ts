// IA v3.0 / Terminology Refinement — 4 primary pillars + ambient copilot + settings
// Copilot is NOT a primary sidebar pillar; access via FloatingCopilotWidget or
// the "Open full workspace" action within contextual AI responses.
export type NavSection =
  | 'landing'
  | 'organization-discovery' // Dedicated canonical route for Organization Discovery & Re-discovery
  | 'workspace'    // Compliance Overview   — daily triage & monitoring
  | 'repository'   // Regulatory Repository — search & investigate
  | 'actions'      // Compliance Actions    — tasks + 4-eyes approvals
  | 'intelligence' // Compliance Intelligence & Defense Pack
  | 'audit'        // Audit & Defense       — immutable trail + analytics
  | 'settings'     // Settings              — sources, feeds, admin
  | 'copilot';     // Ambient deep workspace



export type TaskStatus =
  | 'NEW'
  | 'NEEDS_REVIEW'
  | 'MY_TASKS'
  | 'OPEN'
  | 'IN_PROGRESS'
  | 'WAITING_APPROVAL'
  | 'DUE_TODAY'
  | 'COMPLETED'
  | 'REOPENED'
  | 'BLOCKED'
  | 'CANCELLED'
  | 'SUPERSEDED';

export type RiskLevelType = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

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
  obligation_code?: string;
  control_code?: string;
  title: string;
  description?: string;
  assignee: string;
  reviewer: string;
  priority: RiskLevelType;
  status: TaskStatus;
  due_date?: string | null;
  organization_id?: string;
  regulatory_obligation_id?: string;
  responsible_function?: string;
  due_rule?: string;
  frequency?: string;
  trigger_type?: string | null;
  trigger_offset_value?: number | null;
  trigger_offset_unit?: string | null;
  trigger_event_id?: string | null;
  trigger_timestamp?: string | null;
  completed_at?: string | null;
  completed_by?: string | null;
  reopened_at?: string | null;
  reopened_by?: string | null;
  evidence_count?: number;
  activity_count?: number;
  evidence_file_path?: string;
  evidence_url?: string;
  is_overdue?: boolean;
  deadline_status_message?: string;
  source_citation?: string;
  authoritative_source_url?: string;
  regulatory_evidence_refs?: Array<{
    regulation_id: string;
    title: string;
    authority: string;
    source_url: string;
    statutory_reference: string;
  }>;
  organization_evidence_refs?: Array<{
    organization_name: string;
    matched_jurisdiction: string;
    matched_activities: string[];
    applicability_assessment_id: string;
  }>;
  operational_evidence?: any[];
  engine_version?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComplianceTaskEvidence {
  id: string;
  task_id: string;
  organization_id?: string;
  uploaded_by: string;
  uploader_role: string;
  evidence_type: 'DOCUMENT' | 'SCREENSHOT' | 'LOG' | 'REPORT' | 'POLICY' | 'CERTIFICATE' | 'INCIDENT_RECORD' | 'OTHER';
  file_name: string;
  file_url?: string;
  description?: string;
  evidence_date: string;
  created_at: string;
  updated_at: string;
}

export interface ComplianceTaskActivity {
  id: string;
  task_id: string;
  organization_id?: string;
  actor_id?: string;
  actor_name: string;
  actor_role: string;
  activity_type: string;
  message: string;
  activity_metadata?: Record<string, any>;
  created_at: string;
}

export interface ComplianceTriggerEvent {
  id: string;
  organization_id: string;
  event_type: 'INCIDENT_DETECTED' | 'REGULATORY_NOTIFICATION_RECEIVED' | 'DATA_BREACH_IDENTIFIED' | 'OTHER';
  event_timestamp: string;
  source: string;
  description: string;
  event_metadata?: Record<string, any>;
  created_by: string;
  created_at: string;
  affected_tasks_count?: number;
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

export interface RegulatoryApplicabilityAssessment {
  id: string;
  organization_id: string;
  regulation_id: string;
  regulation_title?: string;
  regulation_authority?: string;
  regulation_region?: string;
  regulation_sector?: string;
  status: 'APPLICABLE' | 'NOT_APPLICABLE' | 'REQUIRES_REVIEW';
  applicability_score: number;
  rationale: string;
  matched_criteria?: Array<{
    criterion_id: string;
    criterion_name: string;
    result: string;
    evidence: string;
    authoritative_source?: string;
  }>;
  unmet_criteria?: Array<{
    criterion_id: string;
    criterion_name: string;
    result: string;
    reason: string;
    authoritative_source?: string;
  }>;
  missing_information?: string[];
  organization_evidence_refs?: Array<{
    type: string;
    value: string;
    source: string;
  }>;
  regulatory_evidence_refs?: Array<{
    regulation_id: string;
    title: string;
    authority: string;
    statutory_region: string;
    statutory_sector: string;
    source_url: string;
    effective_date?: string;
  }>;
  regulatory_signal_refs?: Array<{
    signal_id: string;
    signal_name: string;
    confidence: number;
    evidence_quote: string;
    source_url: string;
    interpretation: string;
  }>;
  engine_version: string;
  evaluated_at?: string;
}

export interface RegulatoryObligation {
  id: string;
  regulation_id: string;
  organization_id: string;
  applicability_assessment_id: string;
  obligation_code: string;
  title: string;
  description: string;
  obligation_type:
    | 'REPORTING'
    | 'RECORD_KEEPING'
    | 'SECURITY_CONTROL'
    | 'NOTIFICATION'
    | 'GOVERNANCE'
    | 'AUDIT'
    | 'DOCUMENTATION'
    | 'DATA_PROTECTION'
    | 'OTHER';
  responsible_function?: string;
  frequency?: string;
  due_rule?: string;
  effective_date?: string;
  source_citation: string;
  authoritative_source_url?: string;
  regulatory_evidence_refs?: Array<{
    regulation_id: string;
    title: string;
    authority: string;
    source_url: string;
    statutory_reference?: string;
  }>;
  organization_evidence_refs?: Array<{
    organization_name: string;
    matched_jurisdiction: string;
    matched_activities: string[];
    applicability_assessment_id: string;
  }>;
  missing_information?: string[];
  status: 'ACTIVE' | 'SUPERSEDED' | 'REQUIRES_REVIEW';
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  engine_version: string;
  created_at?: string;
  updated_at?: string;
}

export type PostureStatus = 'HEALTHY' | 'ATTENTION_REQUIRED' | 'CRITICAL' | 'REQUIRES_REVIEW';
export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type AlertType =
  | 'OVERDUE_TASK'
  | 'CRITICAL_BLOCKED_TASK'
  | 'HIGH_PRIORITY_BLOCKED_TASK'
  | 'EVIDENCE_GAP'
  | 'COMPLETED_WITHOUT_EVIDENCE'
  | 'REVIEW_REQUIRED'
  | 'MISSING_TRIGGER_METADATA'
  | 'ORPHANED_ACTIVE_OBLIGATION'
  | 'UNRESOLVED_TRIGGER';

export interface ComplianceAlert {
  id: string;
  organization_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string;
  source_entity_type: string;
  source_entity_id: string;
  regulation_id?: string;
  obligation_id?: string;
  task_id?: string;
  status: 'ACTIVE' | 'RESOLVED';
  evidence_refs?: Record<string, any>;
  created_at: string;
  resolved_at?: string;
  resolved_by?: string;
  resolution_notes?: string;
  context_data?: any;
}

export interface LegalPostureSummary {
  total_regulations_evaluated: number;
  applicable_count: number;
  not_applicable_count: number;
  requires_review_count: number;
  applicable_regulation_ids: string[];
}

export interface ObligationPostureSummary {
  total_obligations: number;
  active_obligations_count: number;
  requires_review_count: number;
  superseded_count: number;
  by_priority: Record<string, number>;
  regulations_represented: number;
}

export interface OperationalPostureSummary {
  total_tasks: number;
  open_count: number;
  in_progress_count: number;
  blocked_count: number;
  completed_count: number;
  reopened_count: number;
  superseded_count: number;
  overdue_count: number;
  continuous_count: number;
  awaiting_trigger_count: number;
}

export interface EvidencePostureSummary {
  total_evidence_records: number;
  obligations_with_evidence: number;
  obligations_without_evidence: number;
  completed_without_evidence_count: number;
}

export interface CompliancePostureResponse {
  organization: {
    id: string;
    organization_name: string;
    country?: string;
    industry_sector?: string;
    discovery_status?: string;
  };
  legal_summary: LegalPostureSummary;
  obligation_summary: ObligationPostureSummary;
  operational_summary: OperationalPostureSummary;
  evidence_summary: EvidencePostureSummary;
  posture_status: PostureStatus;
  posture_reasons: string[];
  generated_at: string;
}

export interface UnresolvedItem {
  category: string;
  severity: AlertSeverity | string;
  entity_type: string;
  entity_id: string;
  title: string;
  reason: string;
  provenance_refs: Record<string, any>;
}

export interface ComplianceIntelligenceSnapshot {
  id: string;
  organization_id: string;
  snapshot_type: string;
  generated_by: string | null;
  generated_at: string;
  engine_version: string;
  legal_summary: Record<string, any>;
  obligation_summary: Record<string, any>;
  operational_summary: Record<string, any>;
  evidence_summary: Record<string, any>;
  alert_summary: Record<string, any>;
  deadline_summary: Record<string, any>;
  unresolved_items: UnresolvedItem[];
  review_items: any[];
  provenance_summary: Record<string, any>;
  created_at: string;
}

export interface ComplianceEvidenceManifest {
  id: string;
  defense_pack_id: string;
  evidence_layer: string;
  evidence_type: string | null;
  source_entity_type: string;
  source_entity_id: string;
  organization_id: string;
  title: string;
  description: string;
  source_url: string | null;
  source_citation: string | null;
  captured_at: string | null;
  hash: string | null;
  provenance_refs: Record<string, any> | null;
  evidence_status: string;
  created_at: string;
}

export interface ComplianceDefensePack {
  id: string;
  organization_id: string;
  snapshot_id: string;
  pack_version: string;
  generated_by: string | null;
  generated_at: string;
  status: string;
  file_path: string | null;
  content_hash: string;
  manifest: any;
  engine_version: string;
  created_at: string;
  updated_at: string | null;
  evidence_manifests?: ComplianceEvidenceManifest[];
}

