import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# --- Shared Kernel Value Objects & Primitives ---

class RegulationId(BaseModel):
    value: str = Field(default_factory=lambda: str(uuid.uuid4()))

class UserId(BaseModel):
    value: str = Field(default_factory=lambda: str(uuid.uuid4()))

class OrganizationId(BaseModel):
    value: str = Field(default_factory=lambda: str(uuid.uuid4()))

class Jurisdiction(BaseModel):
    region: str
    country_code: str = "IN"

class RiskLevel(BaseModel):
    score: int # 1 - 100
    label: str # HIGH, MEDIUM, LOW

class AuditMetadata(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "SYSTEM"

# --- Domain Event Catalog ---

class DomainEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    event_type: str

class DocumentDiscoveredEvent(DomainEvent):
    event_type: str = "DocumentDiscovered"
    source_id: str
    external_url: str

class DocumentParsedEvent(DomainEvent):
    event_type: str = "DocumentParsed"
    regulation_id: str
    content_hash: str

class KnowledgeExtractedEvent(DomainEvent):
    event_type: str = "KnowledgeExtracted"
    regulation_id: str
    sections_count: int

class ImpactAssessedEvent(DomainEvent):
    event_type: str = "ImpactAssessed"
    regulation_id: str
    relevance_level: str
    risk_score: int
    mapped_controls: list

class TaskCreatedEvent(DomainEvent):
    event_type: str = "TaskCreated"
    task_id: str
    regulation_id: str
    assignee: str

class TaskApprovedEvent(DomainEvent):
    event_type: str = "TaskApproved"
    task_id: str
    approver: str

class WorkflowCompletedEvent(DomainEvent):
    event_type: str = "WorkflowCompleted"
    task_id: str
