from datetime import date, datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel

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
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    assignee: str
    reviewer: Optional[str] = None
    priority: str = "HIGH"
    status: str = "NEEDS_REVIEW" # NEW, NEEDS_REVIEW, MY_TASKS, WAITING_APPROVAL, DUE_TODAY, COMPLETED
    due_date: date

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

class TaskResponse(TaskBase):
    id: str
    regulation_id: str
    control_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    regulation_title: Optional[str] = None

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

