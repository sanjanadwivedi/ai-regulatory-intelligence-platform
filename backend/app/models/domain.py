import uuid
import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

# ==========================================
# 1. REGULATORY KNOWLEDGE ONTOLOGY DOMAIN
# Hierarchy: Regulation -> Section -> Obligation -> Requirement -> Penalty
# ==========================================

class Regulation(Base):
    __tablename__ = "regulations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(512), nullable=False)
    authority = Column(String(128), nullable=False)
    doc_number = Column(String(128), nullable=True)
    publication_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=True)
    sector = Column(String(128), nullable=False)
    region = Column(String(64), nullable=False)
    content_text = Column(Text, nullable=False)
    source_url = Column(String(1024), nullable=True)
    resolved_source_url = Column(String(1024), nullable=True)  # Resolved direct document URL if source_url is an index page
    file_format = Column(String(32), default="PDF/HTML") # PDF, HTML, SCAN_IMAGE

    ocr_confidence = Column(Float, default=0.95) # 0.0 to 1.0 score
    needs_human_review = Column(Integer, default=0) # 1 if OCR < 0.80 or parsing error
    status = Column(String(64), default="INGESTED")
    extraction_method = Column(String(64), default="GEMINI_EXTRACTED") # GEMINI_EXTRACTED, VERIFIED_EXTRACTION, EXTRACTION_PENDING, HUMAN_CORRECTED
    calibration_score = Column(Float, default=1.0) # Computed multi-signal confidence
    current_version_no = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Source-URL live grounding verification
    # 0 = unchecked, 1 = verified OK, -1 = mismatch/drift detected
    source_url_verified = Column(Integer, default=0)
    source_url_verification_score = Column(Float, nullable=True)  # 0.0-1.0 overlap score
    source_url_last_verified_at = Column(DateTime, nullable=True)
    # VERIFIED | CONTENT_DRIFT_DETECTED | POSSIBLE_WRONG_SOURCE | FETCH_FAILED | JS_RENDER_REQUIRED
    source_url_verification_note = Column(String(512), nullable=True)
    # Most recent amendment/drift flag from periodic re-verification
    possible_amendment_detected = Column(Integer, default=0)  # 1 if live source newer than stored

    # Relationships
    versions = relationship("DocumentVersion", back_populates="regulation", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="regulation", cascade="all, delete-orphan")
    graph_chains = relationship("KnowledgeGraphChain", back_populates="regulation", cascade="all, delete-orphan")
    applicability_criteria = relationship("RegulatoryApplicabilityCriterion", back_populates="regulation", cascade="all, delete-orphan")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    version_no = Column(Integer, nullable=False) # 1, 2, 3
    effective_date = Column(Date, nullable=True)
    content_text = Column(Text, nullable=False)
    diff_summary = Column(JSON, nullable=True) # Added / Modified / Removed requirements
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    regulation = relationship("Regulation", back_populates="versions")


class RegulatoryApplicabilityCriterion(Base):
    """
    Deterministic rule criteria for regulatory applicability.
    Replaces hardcoded logic.
    """
    __tablename__ = "regulatory_applicability_criteria"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    criterion_type = Column(String(64), nullable=False)  # JURISDICTION, SECTOR, THRESHOLD, DATA_TYPE, ACTIVITY
    description = Column(Text, nullable=False)
    is_mandatory = Column(Integer, default=1)  # 1 for required, 0 for optional/supporting
    operator = Column(String(32), nullable=False)  # EQUALS, CONTAINS, GREATER_THAN, GREATER_THAN_EQUAL, LESS_THAN
    expected_value = Column(String(256), nullable=False)
    evidence_fact_type = Column(String(64), nullable=False)  # matches fact_type in DiscoveredFact
    minimum_evidence_strength = Column(String(32), default="DOCUMENTED") # AUTHORITATIVE, DOCUMENTED, ATTESTED, INFERRED
    criterion_group = Column(String(64), nullable=True) # E.g. "HIPAA_COVERED_ENTITY"
    group_operator = Column(String(16), nullable=True) # "OR", "AND"
    provenance_reference = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    regulation = relationship("Regulation", back_populates="applicability_criteria")


class Section(Base):
    __tablename__ = "sections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    section_number = Column(String(64), nullable=False) # e.g. "Section 4.1(a)"
    title = Column(String(256), nullable=True)
    content_text = Column(Text, nullable=False)

    regulation = relationship("Regulation", back_populates="sections")
    obligations = relationship("Obligation", back_populates="section", cascade="all, delete-orphan")

class Obligation(Base):
    __tablename__ = "obligations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=False)

    section = relationship("Section", back_populates="obligations")
    requirements = relationship("Requirement", back_populates="obligation", cascade="all, delete-orphan")

class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    obligation_id = Column(String(36), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False)
    requirement_text = Column(Text, nullable=False)
    source_span = Column(Text, nullable=True) # Verbatim quoted sentence/phrase from source text
    grounding_status = Column(String(64), default="VERIFIED") # VERIFIED, UNVERIFIED_GROUNDING
    grounding_score = Column(Float, default=1.0) # Fuzzy similarity ratio (0.0 to 1.0)
    verifier_verdict = Column(String(64), default="SUPPORTED") # SUPPORTED, PARTIALLY_SUPPORTED, NOT_SUPPORTED
    verifier_citation = Column(Text, nullable=True) # Adversarial verifier citing evidence
    deadline = Column(Date, nullable=True)
    penalty_description = Column(Text, nullable=True)
    statutory_reference = Column(String(128), nullable=True)
    affected_entities = Column(JSON, nullable=True) # Array of entity names

    obligation = relationship("Obligation", back_populates="requirements")



# ==========================================
# 2. ORGANIZATION CONTEXT DOMAIN
# Enterprise Context: Business Units, Controls, Policies, Processes, Applications
# ==========================================

class InternalControl(Base):
    __tablename__ = "internal_controls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    control_code = Column(String(64), unique=True, nullable=False) # e.g., "CTRL-KYC-04"
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(128), nullable=False)
    owner_department = Column(String(128), nullable=False)

class EnterprisePolicy(Base):
    __tablename__ = "enterprise_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    policy_code = Column(String(64), unique=True, nullable=False) # e.g., "POL-KYC-2026"
    title = Column(String(256), nullable=False)
    version = Column(String(32), default="v3.1")
    owner_department = Column(String(128), nullable=False)
    content_summary = Column(Text, nullable=False)

class EnterpriseProcess(Base):
    __tablename__ = "enterprise_processes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    process_code = Column(String(64), unique=True, nullable=False) # e.g., "PRC-ONBOARDING-01"
    name = Column(String(256), nullable=False)
    owner_department = Column(String(128), nullable=False)

class EnterpriseApplication(Base):
    __tablename__ = "enterprise_applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    app_code = Column(String(64), unique=True, nullable=False) # e.g., "APP-CORE-BANKING"
    name = Column(String(256), nullable=False)
    owner_team = Column(String(128), nullable=False)


# ==========================================
# 3. KNOWLEDGE GRAPH RELATIONSHIP CHAIN
# Regulation -> Requirement -> Control -> Policy -> Process -> Department -> Application -> Task
# ==========================================

class KnowledgeGraphChain(Base):
    __tablename__ = "knowledge_graph_chains"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True)
    control_code = Column(String(64), nullable=True)
    policy_code = Column(String(64), nullable=True)
    process_code = Column(String(64), nullable=True)
    department_name = Column(String(128), nullable=True)
    application_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    regulation = relationship("Regulation", back_populates="graph_chains")


# ==========================================
# 4. COMPLIANCE WORKFLOW DOMAIN
# ==========================================

class ComplianceTask(Base):
    __tablename__ = "compliance_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=True)
    regulatory_obligation_id = Column(String(36), ForeignKey("regulatory_obligations.id", ondelete="CASCADE"), nullable=True)
    control_code = Column(String(64), nullable=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    assignee = Column(String(128), nullable=False)
    reviewer = Column(String(128), nullable=False)
    priority = Column(String(32), default="HIGH")
    status = Column(String(64), default="OPEN") # OPEN, IN_PROGRESS, BLOCKED, COMPLETED, REOPENED, NEEDS_REVIEW, MY_TASKS, WAITING_APPROVAL, DUE_TODAY, CANCELLED, SUPERSEDED
    due_date = Column(Date, nullable=True)
    responsible_function = Column(String(128), nullable=True)
    due_rule = Column(String(256), nullable=True)
    frequency = Column(String(64), nullable=True)
    trigger_type = Column(String(64), nullable=True)  # Preserved from originating RegulatoryObligation
    trigger_offset_value = Column(Integer, nullable=True)  # Preserved from originating RegulatoryObligation
    trigger_offset_unit = Column(String(32), nullable=True)  # Preserved from originating RegulatoryObligation
    trigger_event_id = Column(String(36), ForeignKey("compliance_trigger_events.id", ondelete="SET NULL"), nullable=True)
    trigger_timestamp = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(128), nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    reopened_by = Column(String(128), nullable=True)
    source_citation = Column(String(256), nullable=True)
    authoritative_source_url = Column(String(1024), nullable=True)
    regulatory_evidence_refs = Column(JSON, nullable=True)
    organization_evidence_refs = Column(JSON, nullable=True)
    operational_evidence = Column(JSON, nullable=True)
    engine_version = Column(String(32), default="v1.0.0-deterministic")
    legal_signoff_by = Column(String(128), nullable=True)
    executive_approval_by = Column(String(128), nullable=True)
    digital_signature_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    evidence_items = relationship("ComplianceTaskEvidence", back_populates="task", cascade="all, delete-orphan")
    activities = relationship("ComplianceTaskActivity", back_populates="task", cascade="all, delete-orphan")
    trigger_event = relationship("ComplianceTriggerEvent")
    regulatory_obligation = relationship("RegulatoryObligation")
    regulation = relationship("Regulation")

class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("compliance_tasks.id", ondelete="CASCADE"), nullable=False)
    author_name = Column(String(128), nullable=False)
    author_role = Column(String(64), nullable=False)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("ComplianceTask", back_populates="comments")

class ComplianceTaskEvidence(Base):
    __tablename__ = "compliance_task_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("compliance_tasks.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=True)
    uploaded_by = Column(String(128), nullable=False)
    uploader_role = Column(String(64), nullable=False)
    evidence_type = Column(String(64), nullable=False)  # DOCUMENT, SCREENSHOT, LOG, REPORT, POLICY, CERTIFICATE, INCIDENT_RECORD, OTHER
    file_name = Column(String(256), nullable=False)
    file_url = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    evidence_date = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    task = relationship("ComplianceTask", back_populates="evidence_items")

class ComplianceTaskActivity(Base):
    __tablename__ = "compliance_task_activities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("compliance_tasks.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=True)
    actor_id = Column(String(128), nullable=True)
    actor_name = Column(String(128), nullable=False)
    actor_role = Column(String(64), nullable=False)
    activity_type = Column(String(64), nullable=False)  # CREATED, ASSIGNED, STATUS_CHANGED, COMMENT_ADDED, EVIDENCE_ADDED, COMPLETED, BLOCKED, REOPENED, REASSIGNED, TRIGGER_APPLIED
    message = Column(Text, nullable=False)
    activity_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("ComplianceTask", back_populates="activities")

class ComplianceTriggerEvent(Base):
    __tablename__ = "compliance_trigger_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(64), nullable=False)  # INCIDENT_DETECTED, REGULATORY_NOTIFICATION_RECEIVED, DATA_BREACH_IDENTIFIED, OTHER
    event_timestamp = Column(DateTime, nullable=False)
    source = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    event_metadata = Column(JSON, nullable=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ComplianceAlert(Base):
    """
    Deterministic Compliance Monitoring Alert.
    Calculated strictly from authoritative upstream records (overdues, evidence gaps, blocked critical tasks, review needs).
    Resolution changes ONLY the operational alert status and never mutates upstream regulations or obligations.
    """
    __tablename__ = "compliance_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(64), nullable=False)  # OVERDUE_TASK, CRITICAL_BLOCKED_TASK, HIGH_PRIORITY_BLOCKED_TASK, EVIDENCE_GAP, COMPLETED_WITHOUT_EVIDENCE, REVIEW_REQUIRED, MISSING_TRIGGER_METADATA, ORPHANED_ACTIVE_OBLIGATION, UNRESOLVED_TRIGGER
    severity = Column(String(32), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    source_entity_type = Column(String(64), nullable=False)  # COMPLIANCE_TASK, REGULATORY_OBLIGATION, REGULATORY_APPLICABILITY_ASSESSMENT, COMPLIANCE_TRIGGER_EVENT
    source_entity_id = Column(String(36), nullable=False)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True)
    obligation_id = Column(String(36), ForeignKey("regulatory_obligations.id", ondelete="SET NULL"), nullable=True)
    task_id = Column(String(36), ForeignKey("compliance_tasks.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), default="ACTIVE")  # ACTIVE, RESOLVED
    evidence_refs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    regulation = relationship("Regulation")
    obligation = relationship("RegulatoryObligation")
    task = relationship("ComplianceTask")

# ==========================================
# 5. ENTERPRISE PROFILE DOMAIN
# ==========================================

class EnterpriseProfile(Base):
    __tablename__ = "enterprise_profile"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_name = Column(String(256), nullable=False)
    industry_sector = Column(String(128), nullable=False)
    departments = Column(JSON, nullable=True)
    country = Column(String(64), nullable=True)
    regulator_region = Column(String(64), nullable=True)
    website_url = Column(String(512), nullable=True)
    business_activities = Column(JSON, nullable=True)
    products_services = Column(JSON, nullable=True)
    licenses = Column(JSON, nullable=True)
    locations = Column(JSON, nullable=True)
    discovery_status = Column(String(64), default="UNINITIALIZED")  # UNINITIALIZED, DISCOVERING, REVIEW_PENDING, CONFIRMED
    last_discovered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class DiscoveryRun(Base):
    """
    Execution identity for an automated corporate discovery cycle.
    Strictly scopes discovered candidate facts to the website and run session.
    """
    __tablename__ = "discovery_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    website_url = Column(String(512), nullable=False)
    final_url = Column(String(512), nullable=True)
    root_domain = Column(String(256), nullable=False)
    status = Column(String(64), default="DISCOVERING")  # DISCOVERING, REVIEW_PENDING, CONFIRMED, FAILED
    failure_reason = Column(String(64), nullable=True)  # INSUFFICIENT_PUBLIC_INFORMATION, ACCESS_RESTRICTED, UNREACHABLE_HOST
    error_message = Column(Text, nullable=True)
    crawled_pages_count = Column(Integer, default=0)
    discovered_urls_count = Column(Integer, default=0)
    crawl_duration_seconds = Column(Float, default=0.0)
    created_by = Column(String(256), nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    facts = relationship("DiscoveredFact", back_populates="discovery_run", cascade="all, delete-orphan")


class DiscoveredFact(Base):
    """
    Evidence-driven discovered organizational facts harvested from public company data.
    Every fact preserves full provenance (source URL, title, tier, verbatim quote snippet, extraction method, confidence, discovery_run_id).
    """
    __tablename__ = "discovered_facts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=True)
    discovery_run_id = Column(String(36), ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=True)
    fact_type = Column(String(64), nullable=False)  # COMPANY, BUSINESS_ACTIVITY, PRODUCT_SERVICE, LOCATION, DEPARTMENT, LICENSE, REGULATORY_SIGNAL, THRESHOLD
    fact_value = Column(String(512), nullable=False)
    data_type = Column(String(32), default="STRING")  # STRING, BOOLEAN, NUMERIC, DATE, LIST
    known_state = Column(String(32), default="TRUE")  # TRUE, FALSE, UNKNOWN
    source_url = Column(String(1024), nullable=False)
    source_title = Column(String(256), nullable=True)
    source_tier = Column(Integer, default=2)  # Tier 1 to 6
    snippet = Column(Text, nullable=False)  # Verbatim quote proving fact
    extraction_method = Column(String(64), default="RULE_MATCHED")  # RULE_MATCHED, NER_EXTRACTED, AI_EXTRACTED, USER_PROVIDED
    confidence = Column(Float, default=0.85)  # 0.0 to 1.0
    status = Column(String(32), default="PENDING")  # PENDING, CONFIRMED, REJECTED, EDITED
    evidence_type = Column(String(64), default="OTHER") # ORGANIZATION_PROFILE, LICENSE, CERTIFICATE, REGULATORY_REGISTRATION, POLICY_DOCUMENT, CONTRACT, SYSTEM_RECORD, AUTHORITATIVE_EXTERNAL_SOURCE, USER_ATTESTATION, OTHER
    evidence_strength = Column(String(32), default="UNKNOWN") # AUTHORITATIVE, DOCUMENTED, ATTESTED, INFERRED, UNKNOWN
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    discovery_run = relationship("DiscoveryRun", back_populates="facts")


class EnterpriseUser(Base):
    """Real enterprise users with assigned compliance roles — not demo personas."""
    __tablename__ = "enterprise_users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=True)
    full_name = Column(String(256), nullable=False)
    role = Column(String(128), nullable=False)  # e.g. Compliance Officer, Legal Counsel
    email = Column(String(256), nullable=True)
    hashed_password = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 6. REGULATORY SOURCE & AUDIT DOMAINS
# ==========================================

class RegulatorySource(Base):
    __tablename__ = "regulatory_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    authority_name = Column(String(128), nullable=False)
    feed_url = Column(String(1024), nullable=False)
    feed_type = Column(String(32), default="RSS")
    fetch_schedule = Column(String(32), default="HOURLY")
    region = Column(String(64), nullable=False)
    sector = Column(String(64), nullable=False)
    status = Column(String(32), default="ACTIVE")
    last_fetched_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_name = Column(String(128), nullable=False)
    user_role = Column(String(64), nullable=False)
    action = Column(String(128), nullable=False)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ==========================================
# 7. REGULATORY APPLICABILITY DOMAIN
# ==========================================

class RegulatoryApplicabilityAssessment(Base):
    """
    Deterministic, explainable regulatory applicability determinations.
    Evaluates confirmed organization context and authoritative regulatory criteria.
    Status values: APPLICABLE, NOT_APPLICABLE, REQUIRES_REVIEW (Never CONFIRMED).
    """
    __tablename__ = "regulatory_applicability_assessments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(32), nullable=False, default="REQUIRES_REVIEW")  # APPLICABLE, NOT_APPLICABLE, REQUIRES_REVIEW
    applicability_score = Column(Float, default=0.0)  # Informational metric (0.0 to 1.0)
    rationale = Column(Text, nullable=False)
    matched_criteria = Column(JSON, nullable=True)  # List of matched criteria with rule/evidence refs
    unmet_criteria = Column(JSON, nullable=True)    # List of unmet/excluded criteria
    missing_information = Column(JSON, nullable=True)  # List of missing items requiring human review
    organization_evidence_refs = Column(JSON, nullable=True)  # Evidence from organization profile & facts
    regulatory_evidence_refs = Column(JSON, nullable=True)    # Evidence from authoritative regulation/source
    regulatory_signal_refs = Column(JSON, nullable=True)      # Discovered regulatory signal references
    engine_version = Column(String(32), default="v1.0.0-deterministic")
    evaluated_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    review_items = relationship("ApplicabilityReviewItem", back_populates="assessment", cascade="all, delete-orphan")

class ApplicabilityReviewItem(Base):
    """
    Actionable human review workflow item derived from an unresolved regulatory criterion.
    """
    __tablename__ = "applicability_review_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    assessment_id = Column(String(36), ForeignKey("regulatory_applicability_assessments.id", ondelete="CASCADE"), nullable=False)
    criterion_id = Column(String(36), ForeignKey("regulatory_applicability_criteria.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String(32), default="OPEN") # OPEN, EVIDENCE_REQUESTED, EVIDENCE_RECEIVED, UNDER_REVIEW, RESOLVED, CLOSED
    question = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    required_fact = Column(String(64), nullable=False)
    requested_value_type = Column(String(32), nullable=True)
    evidence_required = Column(Text, nullable=True)
    suggested_evidence_sources = Column(JSON, nullable=True)
    
    assigned_role = Column(String(64), nullable=False)
    priority = Column(String(32), default="HIGH")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    resolution_evidence_reference = Column(String(1024), nullable=True)

    organization = relationship("EnterpriseProfile")
    regulation = relationship("Regulation")
    assessment = relationship("RegulatoryApplicabilityAssessment", back_populates="review_items")
    criterion = relationship("RegulatoryApplicabilityCriterion")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    regulation = relationship("Regulation")


# ==========================================
# 8. REGULATORY OBLIGATION DOMAIN
# ==========================================

class RegulatoryObligation(Base):
    """
    Authoritative, deterministic regulatory obligations extracted strictly
    from APPLICABLE RegulatoryApplicabilityAssessment records.
    Status values: ACTIVE, SUPERSEDED, REQUIRES_REVIEW.
    """
    __tablename__ = "regulatory_obligations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    regulation_id = Column(String(36), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    applicability_assessment_id = Column(String(36), ForeignKey("regulatory_applicability_assessments.id", ondelete="CASCADE"), nullable=False)
    obligation_code = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    obligation_type = Column(String(64), nullable=False)  # REPORTING, RECORD_KEEPING, SECURITY_CONTROL, NOTIFICATION, GOVERNANCE, AUDIT, DOCUMENTATION, DATA_PROTECTION, OTHER
    responsible_function = Column(String(128), nullable=True)
    frequency = Column(String(64), nullable=True)
    due_rule = Column(String(256), nullable=True)
    trigger_type = Column(String(64), nullable=True)  # INCIDENT_DETECTED, REGULATORY_NOTIFICATION_RECEIVED, DATA_BREACH_IDENTIFIED, OTHER
    trigger_offset_value = Column(Integer, nullable=True)  # e.g. 6
    trigger_offset_unit = Column(String(32), nullable=True)  # MINUTES, HOURS, DAYS
    effective_date = Column(Date, nullable=True)
    source_citation = Column(String(256), nullable=False)
    authoritative_source_url = Column(String(1024), nullable=True)
    regulatory_evidence_refs = Column(JSON, nullable=True)
    organization_evidence_refs = Column(JSON, nullable=True)
    missing_information = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")  # ACTIVE, SUPERSEDED, REQUIRES_REVIEW
    priority = Column(String(32), default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    engine_version = Column(String(32), default="v1.0.0-deterministic")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    regulation = relationship("Regulation")
    applicability_assessment = relationship("RegulatoryApplicabilityAssessment")


# ==========================================
# 8. COMPLIANCE INTELLIGENCE & DEFENSE PACK DOMAIN
# READ-ONLY aggregation layer; never mutates upstream legal records.
# ==========================================

class ComplianceIntelligenceSnapshot(Base):
    """Immutable point-in-time compliance intelligence snapshot.
    Once generated, JSON fields must never be mutated.
    A new evaluation always creates a new record.
    """
    __tablename__ = "compliance_intelligence_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    snapshot_type = Column(String(64), nullable=False, default="POINT_IN_TIME")
    generated_by = Column(String(128), nullable=True)
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    engine_version = Column(String(32), default="v1.0.0-deterministic")

    # Aggregated dimensions — never updated after creation
    legal_summary = Column(JSON, nullable=True)          # APPLICABLE/NOT_APPLICABLE/REQUIRES_REVIEW counts
    obligation_summary = Column(JSON, nullable=True)     # ACTIVE/SUPERSEDED/REQUIRES_REVIEW counts + breakdowns
    operational_summary = Column(JSON, nullable=True)    # Task status counts
    evidence_summary = Column(JSON, nullable=True)       # PRESENT/GAP/COMPLETED_WITHOUT_EVIDENCE
    alert_summary = Column(JSON, nullable=True)          # Active/resolved/critical alerts
    deadline_summary = Column(JSON, nullable=True)       # Triggered/awaiting/continuous/missing metadata/overdue
    unresolved_items = Column(JSON, nullable=True)       # Deterministic list of every unresolved item
    review_items = Column(JSON, nullable=True)           # Items requiring human review
    provenance_summary = Column(JSON, nullable=True)     # Full 5-tier provenance graph

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    organization = relationship("EnterpriseProfile")
    defense_packs = relationship("ComplianceDefensePack", back_populates="snapshot")


class ComplianceDefensePack(Base):
    """Immutable versioned defense pack built from an intelligence snapshot.
    Previous packs become SUPERSEDED when a newer version is generated.
    Historical packs are never overwritten.
    SHA-256 hash is computed over stable canonical content, excluding volatile fields.
    """
    __tablename__ = "compliance_defense_packs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("enterprise_profile.id", ondelete="CASCADE"), nullable=False)
    snapshot_id = Column(String(36), ForeignKey("compliance_intelligence_snapshots.id", ondelete="CASCADE"), nullable=False)
    pack_version = Column(String(32), nullable=False)   # "v1", "v2", "v3" …
    generated_by = Column(String(128), nullable=True)
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(32), nullable=False, default="GENERATED")  # GENERATED | SUPERSEDED | REQUIRES_REVIEW
    file_path = Column(String(1024), nullable=True)     # Optional path to exported JSON artifact
    content_hash = Column(String(128), nullable=False)  # SHA-256 of canonical stable content
    manifest = Column(JSON, nullable=True)              # Full 13-section pack manifest
    engine_version = Column(String(32), default="v1.0.0-deterministic")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    organization = relationship("EnterpriseProfile")
    snapshot = relationship("ComplianceIntelligenceSnapshot", back_populates="defense_packs")
    evidence_manifests = relationship("ComplianceEvidenceManifest", back_populates="defense_pack", cascade="all, delete-orphan")


class ComplianceEvidenceManifest(Base):
    """Structured evidence inventory for a defense pack.
    Contains BOTH existing evidence (PRESENT) and expected-but-missing gaps (MISSING).
    This ensures an auditor sees the full evidence picture, not just what was uploaded.
    Evidence is classified into three non-overlapping layers:
      REGULATORY — statutory citations, source URLs, effective dates
      ORGANIZATION — confirmed org facts, jurisdiction, business activities
      OPERATIONAL — uploaded logs, audit reports, completion records
    """
    __tablename__ = "compliance_evidence_manifests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    defense_pack_id = Column(String(36), ForeignKey("compliance_defense_packs.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String(36), nullable=False)
    evidence_layer = Column(String(32), nullable=False)     # REGULATORY | ORGANIZATION | OPERATIONAL
    evidence_type = Column(String(64), nullable=True)       # Sub-type within layer (e.g. LOG, DOCUMENT, AUDIT_REPORT)
    source_entity_type = Column(String(64), nullable=True)  # Regulation, RegulatoryObligation, ComplianceTask, etc.
    source_entity_id = Column(String(36), nullable=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    source_url = Column(String(1024), nullable=True)
    source_citation = Column(String(256), nullable=True)
    captured_at = Column(DateTime, nullable=True)           # Actual timestamp; never invented
    content_hash = Column(String(128), nullable=True)       # SHA-256 of file content if available
    provenance_refs = Column(JSON, nullable=True)           # Chain of upstream entity IDs
    evidence_status = Column(String(32), nullable=False)    # PRESENT | MISSING | REQUIRES_REVIEW
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    defense_pack = relationship("ComplianceDefensePack", back_populates="evidence_manifests")

