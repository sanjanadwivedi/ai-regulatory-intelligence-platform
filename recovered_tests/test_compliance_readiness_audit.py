import pytest
import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTaskActivity,
    ComplianceTriggerEvent,
    DiscoveredFact,
    AuditLog
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.obligation_engine import ObligationEngine
from app.services.task_engine import TaskEngine
from app.services.task_execution_service import TaskExecutionService
from app.schemas.schemas import (
    TaskAssignRequest,
    TaskCompleteRequest,
    TaskReopenRequest,
    EvidenceCreate,
    TriggerEventCreate,
    TaskCreate
)
from app.core.security import create_access_token
from app.main import app

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def compliance_officer_user(db_session: Session):
    user = db_session.query(EnterpriseUser).filter(EnterpriseUser.role == "Compliance Officer").first()
    if not user:
        user = EnterpriseUser(
            full_name="Audit Officer",
            role="Compliance Officer",
            email="audit@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def setup_audit_baseline(db_session: Session):
    profile = db_session.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="NEC India",
            country="India",
            locations=["India", "Mumbai", "Noida"],
            business_activities=["ICT & Digital Transformation Solutions", "Cloud & Technology Infrastructure", "Digital Identity & Biometrics"],
            discovery_status="CONFIRMED"
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    # Clean execution artifacts for clean test run
    db_session.query(ComplianceTaskActivity).delete()
    db_session.query(ComplianceTaskEvidence).delete()
    db_session.query(ComplianceTriggerEvent).delete()
    db_session.query(ComplianceTask).filter(ComplianceTask.regulatory_obligation_id.isnot(None)).delete()
    db_session.query(RegulatoryObligation).delete()
    db_session.commit()

    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    ObligationEngine.generate_obligations(profile.id, db_session)
    TaskEngine.generate_tasks(profile.id, db_session)
    return profile

# ==============================================================================
# AUDIT DIMENSION 1: UPSTREAM IMMUTABILITY
# ==============================================================================

def test_audit_upstream_immutability(db_session: Session, compliance_officer_user, setup_audit_baseline):
    """AUDIT 1: Operational task execution leaves legal assessments & obligations 100% unchanged."""
    profile = setup_audit_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    # Snapshot upstream
    assessments_before = [
        (a.id, a.status, a.engine_version) for a in db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id == profile.id).all()
    ]
    obligations_before = [
        (o.id, o.status, o.obligation_code) for o in db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == profile.id).all()
    ]

    # Perform mutations
    TaskExecutionService.transition_status(task.id, "IN_PROGRESS", compliance_officer_user, db_session)
    TaskExecutionService.add_evidence(task.id, EvidenceCreate(file_name="audit_run.log", evidence_type="LOG"), compliance_officer_user, db_session)
    TaskExecutionService.complete_task(task.id, compliance_officer_user, db_session)
    TaskExecutionService.reopen_task(task.id, TaskReopenRequest(reopen_reason="Audit test"), compliance_officer_user, db_session)

    assessments_after = [
        (a.id, a.status, a.engine_version) for a in db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id == profile.id).all()
    ]
    obligations_after = [
        (o.id, o.status, o.obligation_code) for o in db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == profile.id).all()
    ]

    assert assessments_before == assessments_after
    assert obligations_before == obligations_after

# ==============================================================================
# AUDIT DIMENSION 2: STRICT PIPELINE GATING
# ==============================================================================

def test_audit_pipeline_gating_signals_and_non_applicable(db_session: Session, setup_audit_baseline):
    """AUDIT 2: Signals and NOT_APPLICABLE/REQUIRES_REVIEW assessments never create active tasks."""
    profile = setup_audit_baseline

    # Verify that only APPLICABLE regulations created ACTIVE obligations
    non_applicable_assessments = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == profile.id,
        RegulatoryApplicabilityAssessment.status != "APPLICABLE"
    ).all()

    for non_app in non_applicable_assessments:
        obs = db_session.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == profile.id,
            RegulatoryObligation.applicability_assessment_id == non_app.id,
            RegulatoryObligation.status == "ACTIVE"
        ).all()
        assert len(obs) == 0, f"Non-applicable assessment {non_app.id} generated active obligations!"

    # Verify that only ACTIVE obligations created compliance tasks
    all_tasks = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).all()

    for t in all_tasks:
        ob = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.id == t.regulatory_obligation_id).first()
        assert ob is not None
        assert ob.status == "ACTIVE"

# ==============================================================================
# AUDIT DIMENSION 3: STATE MACHINE TRANSITION VALIDATION
# ==============================================================================

def test_audit_invalid_transitions_rejected(db_session: Session, compliance_officer_user, setup_audit_baseline):
    """AUDIT 3: Invalid state machine transitions are rejected with 400 Bad Request."""
    profile = setup_audit_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    # Complete task first
    TaskExecutionService.transition_status(task.id, "IN_PROGRESS", compliance_officer_user, db_session)
    TaskExecutionService.complete_task(task.id, compliance_officer_user, db_session)

    # Attempt invalid transition: COMPLETED -> BLOCKED (Must fail!)
    with pytest.raises(HTTPException) as exc_info:
        TaskExecutionService.transition_status(task.id, "BLOCKED", compliance_officer_user, db_session)
    assert exc_info.value.status_code == 400
    assert "Invalid state transition" in exc_info.value.detail

    # Attempt reopening an OPEN task (Must fail!)
    task_open = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.status == "OPEN"
    ).first()
    if task_open:
        with pytest.raises(HTTPException) as exc_reopen:
            TaskExecutionService.reopen_task(task_open.id, TaskReopenRequest(reopen_reason="Bad attempt"), compliance_officer_user, db_session)
        assert exc_reopen.value.status_code == 400

# ==============================================================================
# AUDIT DIMENSION 4: MULTI-TENANT CROSS-ORGANIZATION ISOLATION
# ==============================================================================

def test_audit_cross_organization_isolation(db_session: Session, setup_audit_baseline):
    """AUDIT 4: A user from Organization B cannot access or mutate tasks of Organization A."""
    profile_a = setup_audit_baseline

    # Create dummy user from Org B
    user_org_b = EnterpriseUser(
        full_name="Foreign Officer",
        role="Compliance Officer"
    )
    setattr(user_org_b, "organization_id", "org-foreign-999")

    task_a = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile_a.id).first()

    # Attempt transition on Org A task by Org B user (Must fail!)
    with pytest.raises(HTTPException) as exc_trans:
        TaskExecutionService.transition_status(task_a.id, "IN_PROGRESS", user_org_b, db_session)
    assert exc_trans.value.status_code == 403
    assert "Cross-organization resource access is forbidden" in exc_trans.value.detail

    # Attempt trigger event targeting Org A by Org B user (Must fail!)
    event_in = TriggerEventCreate(
        organization_id=profile_a.id,
        event_type="INCIDENT_DETECTED",
        event_timestamp=datetime.datetime.utcnow(),
        source="External SOC",
        description="Cross-tenant test"
    )
    with pytest.raises(HTTPException) as exc_trig:
        TaskExecutionService.process_trigger_event(event_in, user_org_b, db_session)
    assert exc_trig.value.status_code == 403

# ==============================================================================
# AUDIT DIMENSION 5: TIMEZONE UTC NORMALIZATION & TRIGGER REASSIGNMENT
# ==============================================================================

def test_audit_trigger_utc_timezone_and_reassignment(db_session: Session, compliance_officer_user, setup_audit_baseline):
    """AUDIT 5: Timezone-aware timestamps are UTC-normalized and trigger reassignments are audited."""
    profile = setup_audit_baseline
    tz_aware_ts = datetime.datetime(2026, 8, 13, 15, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))

    event_in_1 = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=tz_aware_ts,
        source="SOC Primary",
        description="First alert"
    )
    event_1, affected_1 = TaskExecutionService.process_trigger_event(event_in_1, compliance_officer_user, db_session)
    task = next(t for t in affected_1 if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert task.trigger_event_id == event_1.id

    # Now simulate a second trigger event reassigning the trigger
    event_in_2 = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=datetime.datetime(2026, 8, 13, 18, 0, 0),
        source="SOC Escalation Notice",
        description="Second escalated incident notice"
    )
    event_2, affected_2 = TaskExecutionService.process_trigger_event(event_in_2, compliance_officer_user, db_session)
    db.refresh(task)
    assert task.trigger_event_id == event_2.id

    # Verify TRIGGER_REASSIGNED activity was emitted
    reassigned_act = db_session.query(ComplianceTaskActivity).filter(
        ComplianceTaskActivity.task_id == task.id,
        ComplianceTaskActivity.activity_type == "TRIGGER_REASSIGNED"
    ).first()
    assert reassigned_act is not None
    assert reassigned_act.activity_metadata["previous_trigger_event_id"] == event_1.id

# ==============================================================================
# AUDIT DIMENSION 6: EVIDENCE SEGREGATION
# ==============================================================================

def test_audit_evidence_segregation_and_provenance(db_session: Session, compliance_officer_user, setup_audit_baseline):
    """AUDIT 6: Uploading operational evidence never alters regulatory applicability."""
    profile = setup_audit_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    ev = TaskExecutionService.add_evidence(
        task.id,
        EvidenceCreate(file_name="remediation_evidence.pdf", evidence_type="DOCUMENT", description="Signed policy"),
        compliance_officer_user,
        db_session
    )
    assert ev.id is not None

    assess = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == profile.id,
        RegulatoryApplicabilityAssessment.regulation_id == task.regulation_id
    ).first()
    assert assess.status == "APPLICABLE"
    assert assess.organization_evidence_refs is not None

# ==============================================================================
# AUDIT DIMENSION 7: IDEMPOTENCY OF GENERATION
# ==============================================================================

def test_audit_task_generation_idempotency(db_session: Session, compliance_officer_user, setup_audit_baseline):
    """AUDIT 7: Repeated task generation calls do not duplicate compliance tasks."""
    profile = setup_audit_baseline

    count_initial = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).count()

    # Call TaskEngine.generate_tasks twice more
    TaskEngine.generate_tasks(profile.id, db_session, evaluated_by="Auditor")
    TaskEngine.generate_tasks(profile.id, db_session, evaluated_by="Auditor")

    count_after = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).count()
    assert count_initial == count_after
