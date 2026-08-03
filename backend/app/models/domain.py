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
    control_code = Column(String(64), nullable=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    assignee = Column(String(128), nullable=False)
    reviewer = Column(String(128), nullable=False)
    priority = Column(String(32), default="HIGH")
    status = Column(String(64), default="NEEDS_REVIEW") # DRAFT, INTERNAL_REVIEW, LEGAL_SIGNOFF, EXECUTIVE_APPROVAL, COMPLETED
    due_date = Column(Date, nullable=False)
    legal_signoff_by = Column(String(128), nullable=True)
    executive_approval_by = Column(String(128), nullable=True)
    digital_signature_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")

class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("compliance_tasks.id", ondelete="CASCADE"), nullable=False)
    author_name = Column(String(128), nullable=False)
    author_role = Column(String(64), nullable=False)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("ComplianceTask", back_populates="comments")



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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class EnterpriseUser(Base):
    """Real enterprise users with assigned compliance roles — not demo personas."""
    __tablename__ = "enterprise_users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
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
