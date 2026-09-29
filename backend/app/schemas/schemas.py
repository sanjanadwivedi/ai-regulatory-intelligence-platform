from datetime import date, datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from enum import Enum

# --- Regulatory Knowledge Ontology Schemas ---
class RequirementSchema(BaseModel):
    id: str
    requirement_text: str
    source_span: Optional[str] = None
    grounding_status: Optional[str] = "VERIFIED"
    grounding_score: Optional[float] = 1.0
    verifier_verdict: Optional[str] = "SUPPORTED"
    verifier_citation: Optional[str] = None
    deadline: Optional[date] = None
    penalty_description: Optional[str] = None
    statutory_reference: Optional[str] = None
    affected_entities: Optional[List[str]] = None

    class Config:
        from_attributes = True

class ObligationSchema(BaseModel):
    id: str
    summary: str
    requirements: List[RequirementSchema] = []

    class Config:
        from_attributes = True

class SectionSchema(BaseModel):
    id: str
    section_number: str
    title: Optional[str] = None
    content_text: str
    obligations: List[ObligationSchema] = []

    class Config:
        from_attributes = True

class KnowledgeGraphChainSchema(BaseModel):
    id: str
    regulation_id: str
    requirement_id: Optional[str] = None
    control_code: Optional[str] = None
    policy_code: Optional[str] = None
    process_code: Optional[str] = None
    department_name: Optional[str] = None
    application_code: Optional[str] = None

    class Config:
        from_attributes = True

class RegulatoryApplicabilityCriterionSchema(BaseModel):
    id: str
    regulation_id: str
    criterion_type: str
    description: str
    is_mandatory: int
    operator: str
    expected_value: str
    evidence_fact_type: str
    provenance_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RegulationSchema(BaseModel):
    id: str
    title: str
    authority: str
    doc_number: Optional[str] = None
    publication_date: date
    effective_date: Optional[date] = None
    sector: str
    region: str
    content_text: str
    source_url: Optional[str] = None
    resolved_source_url: Optional[str] = None
    file_format: Optional[str] = "PDF/HTML"

    ocr_confidence: Optional[float] = 0.95
    needs_human_review: Optional[int] = 0
    status: str
    extraction_method: Optional[str] = "GEMINI_EXTRACTED"
    calibration_score: Optional[float] = 1.0
    # Source-URL live grounding verification
    source_url_verified: Optional[int] = 0          # 0=unchecked, 1=verified, -1=mismatch
    source_url_verification_score: Optional[float] = None
    source_url_last_verified_at: Optional[datetime] = None
    source_url_verification_note: Optional[str] = None
    possible_amendment_detected: Optional[int] = 0
    created_at: datetime
    sections: List[SectionSchema] = []
    graph_chains: List[KnowledgeGraphChainSchema] = []
    applicability_criteria: List[RegulatoryApplicabilityCriterionSchema] = []


    class Config:
        from_attributes = True

class RegulationCreate(BaseModel):
    title: str
    authority: str
    doc_number: Optional[str] = None
    publication_date: date
    effective_date: Optional[date] = None
    sector: str
    region: str
    content_text: str
    source_url: Optional[str] = None
    file_format: Optional[str] = "PDF/HTML"
    ocr_confidence: Optional[float] = 0.95
    needs_human_review: Optional[int] = 0

# --- Compliance Task Schemas ---
class TaskStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"

class EvidenceType(str, Enum):
    ORGANIZATION_PROFILE = "ORGANIZATION_PROFILE"
    LICENSE = "LICENSE"
    CERTIFICATE = "CERTIFICATE"
    REGULATORY_REGISTRATION = "REGULATORY_REGISTRATION"
    POLICY_DOCUMENT = "POLICY_DOCUMENT"
    CONTRACT = "CONTRACT"
    SYSTEM_RECORD = "SYSTEM_RECORD"
    AUTHORITATIVE_EXTERNAL_SOURCE = "AUTHORITATIVE_EXTERNAL_SOURCE"
    USER_ATTESTATION = "USER_ATTESTATION"
    OTHER = "OTHER"

class EvidenceStrength(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    DOCUMENTED = "DOCUMENTED"
    ATTESTED = "ATTESTED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    assignee: str
    assignee_id: Optional[str] = None
    reviewer: Optional[str] = None
    reviewer_id: Optional[str] = None
    completion_signature: Optional[str] = None
    priority: str = "HIGH"
    status: str = "OPEN" # OPEN, IN_PROGRESS, BLOCKED, COMPLETED, REOPENED, NEEDS_REVIEW, MY_TASKS, WAITING_APPROVAL, DUE_TODAY, CANCELLED, SUPERSEDED
    due_date: Optional[date] = None
    organization_id: Optional[str] = None
    regulatory_obligation_id: Optional[str] = None
    control_id: Optional[str] = None
    responsible_function: Optional[str] = None
    due_rule: Optional[str] = None
    frequency: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_offset_value: Optional[int] = None
    trigger_offset_unit: Optional[str] = None
    trigger_event_id: Optional[str] = None
    trigger_timestamp: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None
    source_citation: Optional[str] = None
    authoritative_source_url: Optional[str] = None
    regulatory_evidence_refs: Optional[List[Dict[str, Any]]] = None
    organization_evidence_refs: Optional[List[Dict[str, Any]]] = None
    operational_evidence: Optional[List[Dict[str, Any]]] = None
    engine_version: Optional[str] = "v1.0.0-deterministic"

class TaskCreate(TaskBase):
    regulation_id: str
    control_code: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    reviewer: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    responsible_function: Optional[str] = None
    due_rule: Optional[str] = None
    operational_evidence: Optional[List[Dict[str, Any]]] = None

class TaskAssignRequest(BaseModel):
    assignee: str
    assignee_id: Optional[str] = None
    responsible_function: Optional[str] = None
    notes: Optional[str] = None

class TaskStatusTransitionRequest(BaseModel):
    status: str
    reason: Optional[str] = None

class TaskCompleteRequest(BaseModel):
    confirmation_notes: Optional[str] = None

class TaskReopenRequest(BaseModel):
    reopen_reason: str

class EvidenceCreate(BaseModel):
    evidence_type: str = "DOCUMENT"  # DOCUMENT, SCREENSHOT, LOG, REPORT, POLICY, CERTIFICATE, INCIDENT_RECORD, OTHER
    file_name: str
    file_url: Optional[str] = None
    description: Optional[str] = None
    evidence_strength: Optional[str] = "UNKNOWN"
    evidence_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None

class EvidenceResponse(BaseModel):
    id: str
    task_id: str
    organization_id: Optional[str] = None
    uploaded_by: str
    uploader_role: str
    evidence_type: str
    file_name: str
    file_url: Optional[str] = None
    description: Optional[str] = None
    evidence_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ActivityResponse(BaseModel):
    id: str
    task_id: str
    organization_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: str
    actor_role: str
    activity_type: str
    message: str
    activity_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    comment_text: str

class CommentResponse(BaseModel):
    id: str
    task_id: str
    author_name: str
    author_role: str
    comment_text: str
    created_at: datetime

    class Config:
        from_attributes = True

class TriggerEventCreate(BaseModel):
    organization_id: Optional[str] = None
    event_type: str  # INCIDENT_DETECTED, REGULATORY_NOTIFICATION_RECEIVED, DATA_BREACH_IDENTIFIED, OTHER
    event_timestamp: datetime
    source: str
    description: str
    event_metadata: Optional[Dict[str, Any]] = None

class TriggerEventResponse(BaseModel):
    id: str
    organization_id: str
    event_type: str
    event_timestamp: datetime
    source: str
    description: str
    event_metadata: Optional[Dict[str, Any]] = None
    created_by: str
    created_at: datetime
    affected_tasks_count: Optional[int] = 0

    class Config:
        from_attributes = True

class TaskResponse(TaskBase):
    id: str
    regulation_id: str
    control_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    regulation_title: Optional[str] = None
    obligation_code: Optional[str] = None
    evidence_count: Optional[int] = 0
    activity_count: Optional[int] = 0
    is_overdue: Optional[bool] = False
    deadline_status_message: Optional[str] = None

    class Config:
        from_attributes = True

# --- Source & Audit Schemas ---
class CopilotQueryRequest(BaseModel):
    query: str
    regulation_id: Optional[str] = None
    sector: Optional[str] = None

class GroundedCitation(BaseModel):
    regulation_id: str
    regulation_title: str
    authority: str
    section_text: str
    relevance_score: float

class CopilotQueryResponse(BaseModel):
    answer: str
    grounded_citations: List[GroundedCitation]
    confidence_score: float
    model_version: str

class SourceBase(BaseModel):
    authority_name: str
    feed_url: str
    feed_type: str = "RSS"
    fetch_schedule: str = "HOURLY"
    region: str
    sector: str
    status: str = "ACTIVE"


class SourceCreate(SourceBase):
    pass

class SourceResponse(SourceBase):
    id: str
    last_fetched_at: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    user_name: str
    user_role: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AnalyticsOverviewResponse(BaseModel):
    total_regulations: int
    high_impact_count: int
    open_tasks: int
    completed_tasks: int
    compliance_score: float
    review_turnaround_days: float
    risk_distribution: Dict[str, int]


# --- Regulatory Applicability Engine Schemas ---
class RegulatoryApplicabilityAssessmentOut(BaseModel):
    id: str
    organization_id: str
    regulation_id: str
    regulation_title: Optional[str] = None
    regulation_authority: Optional[str] = None
    regulation_region: Optional[str] = None
    regulation_sector: Optional[str] = None
    status: str  # APPLICABLE, NOT_APPLICABLE, REQUIRES_REVIEW
    applicability_score: float
    rationale: str
    matched_criteria: Optional[List[Dict[str, Any]]] = None
    unmet_criteria: Optional[List[Dict[str, Any]]] = None
    missing_information: Optional[List[Dict[str, Any]]] = None
    organization_evidence_refs: Optional[List[Dict[str, Any]]] = None
    regulatory_evidence_refs: Optional[List[Dict[str, Any]]] = None
    regulatory_signal_refs: Optional[List[Dict[str, Any]]] = None
    engine_version: str
    evaluated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ApplicabilityReviewItemOut(BaseModel):
    id: str
    organization_id: str
    regulation_id: str
    assessment_id: str
    criterion_id: str
    status: str
    question: str
    reason: str
    required_fact: str
    requested_value_type: Optional[str] = None
    evidence_required: Optional[str] = None
    suggested_evidence_sources: Optional[List[str]] = None
    assigned_role: str
    priority: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_evidence_reference: Optional[str] = None

    class Config:
        from_attributes = True

class ApplicabilityReviewResolutionRequest(BaseModel):
    evidence_fact_value: str
    evidence_type: EvidenceType
    evidence_strength: EvidenceStrength
    source_url: str
    snippet: Optional[str] = None
    # For booleans or negative evidence, user explicitly passes state, e.g. "TRUE" or "FALSE"
    known_state: Optional[str] = "TRUE" 

# --- Regulatory Obligation Engine Schemas ---
class RegulatoryObligationOut(BaseModel):
    id: str
    regulation_id: str
    organization_id: str
    applicability_assessment_id: str
    obligation_code: str
    title: str
    description: str
    obligation_type: str
    responsible_function: Optional[str] = None
    frequency: Optional[str] = None
    due_rule: Optional[str] = None
    effective_date: Optional[date] = None
    source_citation: str
    authoritative_source_url: Optional[str] = None
    regulatory_evidence_refs: Optional[List[Dict[str, Any]]] = None
    organization_evidence_refs: Optional[List[Dict[str, Any]]] = None
    missing_information: Optional[List[Dict[str, Any]]] = None
    status: str
    priority: str
    engine_version: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Compliance Monitoring & Intelligence Schemas ---
class LegalPostureSummary(BaseModel):
    total_regulations_evaluated: int
    applicable_count: int
    not_applicable_count: int
    requires_review_count: int
    applicable_regulation_ids: List[str]

class ObligationPostureSummary(BaseModel):
    total_obligations: int
    active_obligations_count: int
    requires_review_count: int
    superseded_count: int
    by_priority: Dict[str, int]
    regulations_represented: int

class OperationalPostureSummary(BaseModel):
    total_tasks: int
    open_count: int
    in_progress_count: int
    blocked_count: int
    completed_count: int
    reopened_count: int
    superseded_count: int
    overdue_count: int
    continuous_count: int
    awaiting_trigger_count: int

class EvidencePostureSummary(BaseModel):
    total_evidence_records: int
    obligations_with_evidence: int
    obligations_without_evidence: int
    completed_without_evidence_count: int

class CompliancePostureResponse(BaseModel):
    organization: Dict[str, Any]
    legal_summary: LegalPostureSummary
    obligation_summary: ObligationPostureSummary
    operational_summary: OperationalPostureSummary
    evidence_summary: EvidencePostureSummary
    posture_status: str  # HEALTHY, ATTENTION_REQUIRED, CRITICAL, REQUIRES_REVIEW
    posture_reasons: List[str]
    generated_at: str

class ComplianceAlertResponse(BaseModel):
    id: str
    organization_id: str
    alert_type: str
    severity: str
    title: str
    description: str
    source_entity_type: str
    source_entity_id: str
    regulation_id: Optional[str] = None
    obligation_id: Optional[str] = None
    task_id: Optional[str] = None
    status: str
    evidence_refs: Optional[Dict[str, Any]] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True

class AlertResolveRequest(BaseModel):
    resolution_notes: str


# ============================================================
# Compliance Intelligence & Defense Pack Schemas
# ============================================================

class SnapshotGenerateRequest(BaseModel):
    """Request to generate a new point-in-time compliance intelligence snapshot."""
    pass  # Future: allow snapshot_type override


class ComplianceIntelligenceSnapshotResponse(BaseModel):
    id: str
    organization_id: str
    snapshot_type: str
    generated_by: Optional[str] = None
    generated_at: datetime
    engine_version: str
    legal_summary: Optional[Dict[str, Any]] = None
    obligation_summary: Optional[Dict[str, Any]] = None
    operational_summary: Optional[Dict[str, Any]] = None
    evidence_summary: Optional[Dict[str, Any]] = None
    alert_summary: Optional[Dict[str, Any]] = None
    deadline_summary: Optional[Dict[str, Any]] = None
    unresolved_items: Optional[List[Dict[str, Any]]] = None
    review_items: Optional[List[Dict[str, Any]]] = None
    provenance_summary: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DefensePackGenerateRequest(BaseModel):
    """Request to generate a Defense Pack from a specific snapshot."""
    snapshot_id: str


class ComplianceDefensePackResponse(BaseModel):
    id: str
    organization_id: str
    snapshot_id: str
    pack_version: str
    generated_by: Optional[str] = None
    generated_at: datetime
    status: str
    content_hash: str
    engine_version: str
    manifest: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComplianceEvidenceManifestResponse(BaseModel):
    id: str
    defense_pack_id: str
    organization_id: str
    evidence_layer: str
    evidence_type: Optional[str] = None
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    source_citation: Optional[str] = None
    captured_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    provenance_refs: Optional[Dict[str, Any]] = None
    evidence_status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DefensePackExportResponse(BaseModel):
    pack_id: str
    pack_version: str
    organization_id: str
    snapshot_id: str
    status: str
    content_hash: str
    engine_version: str
    generated_at: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None

# --- Control Framework Schemas ---
class ControlStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    IMPLEMENTED = "IMPLEMENTED"
    GAPPED = "GAPPED"
    FAILED = "FAILED"
    RETIRED = "RETIRED"

class InternalControlBase(BaseModel):
    control_code: str
    name: str
    description: str
    category: str
    owner_department: str
    status: Optional[str] = "DRAFT"
    implementation_notes: Optional[str] = None

class InternalControlCreate(InternalControlBase):
    pass

class InternalControlUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    owner_department: Optional[str] = None
    status: Optional[str] = None
    implementation_notes: Optional[str] = None

class InternalControlResponse(InternalControlBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ObligationControlMappingCreate(BaseModel):
    rationale: Optional[str] = None
    mapping_source: Optional[str] = "MANUAL"

class ObligationControlMappingResponse(BaseModel):
    id: str
    organization_id: str
    obligation_id: str
    control_id: str
    rationale: Optional[str] = None
    mapping_source: str
    active: int
    created_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

class ControlAssessmentResponse(BaseModel):
    id: str
    organization_id: str
    control_id: str
    assessment_status: str
    control_state: str
    evidence_summary: str
    missing_information: Optional[Dict[str, Any]] = None
    evaluated_at: datetime
    evaluated_by: str
    engine_version: str

    class Config:
        from_attributes = True



# --- Regulatory Intelligence ---
class RegulatoryIntelligenceSummaryResponse(BaseModel):
    total_regulations: int
    new_regulations: int
    updated_regulations: int
    changes_requiring_review: int
    affected_assessments: int
    affected_obligations: int
    affected_tasks: int

class RegulatoryChangeFeedItem(BaseModel):
    change_id: str
    regulation_id: str
    regulation_name: str
    previous_version: Optional[str]
    new_version: str
    change_type: str
    detected_timestamp: datetime
    effective_date: Optional[date]
    source: Optional[str]
    review_status: str
    affected_assessment_count: int
    affected_obligation_count: int
    affected_task_count: int

class RegulatoryChangeFeedResponse(BaseModel):
    items: List[RegulatoryChangeFeedItem]
    total: int
    page: int
    size: int

class RegulatoryChangeDetailResponse(BaseModel):
    change_id: str
    regulation_id: str
    regulation_name: str
    previous_version: Optional[str]
    new_version: str
    change_type: str
    detected_timestamp: datetime
    effective_date: Optional[date]
    source: Optional[str]
    review_status: str
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    diff_hunks: Optional[List[dict]]
    changed_sections: Optional[List[dict]]
    affected_assessments: List[str]
    affected_obligations: List[str]
    affected_tasks: List[str]

class RegulatoryChangeReviewRequest(BaseModel):
    decision: str
    review_notes: Optional[str] = None

class RegulatoryChangeReviewResponse(BaseModel):
    status: str
    change_id: str
    review_status: str

class RegulatoryObligationImpactOut(BaseModel):
    id: str
    organization_id: str
    regulatory_change_id: str
    obligation_id: str
    impact_status: str
    review_status: str
    reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ImpactPropagationSummary(BaseModel):
    obligations_affected: int
    controls_affected: int
    tasks_affected: int
    human_review_required: int

class ImpactPropagationResponse(BaseModel):
    regulatory_change_id: str
    organization_id: str
    impact_status: str
    summary: ImpactPropagationSummary
    mapping_gap: bool
    reason: Optional[str] = None

class ProvenanceNodeResponse(BaseModel):
    id: str
    type: str # REGULATION, APPLICABILITY, OBLIGATION, CONTROL, TASK, EVIDENCE
    title: str
    status: Optional[str] = None
    meta: Optional[str] = None
    link: Optional[str] = None

class ProvenanceChainResponse(BaseModel):
    nodes: List[ProvenanceNodeResponse]
    status: str = "AVAILABLE"
    message: Optional[str] = None
