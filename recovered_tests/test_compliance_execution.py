import pytest
import datetime
import uuid
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
    TriggerEventCreate
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
            full_name="Sarah Jenkins",
            role="Compliance Officer",
            email="sjenkins@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def unauthorized_user(db_session: Session):
    user = db_session.query(EnterpriseUser).filter(EnterpriseUser.role == "Guest Reader").first()
    if not user:
        user = EnterpriseUser(
            full_name="Guest User",
            role="Guest Reader",
            email="guest@external.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(compliance_officer_user):
    token = create_access_token(compliance_officer_user.id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def unauthorized_auth_headers(unauthorized_user):
    token = create_access_token(unauthorized_user.id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def setup_execution_baseline(db_session: Session):
    # Setup clean baseline profile for NEC India
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
    else:
        profile.organization_name = "NEC India"
        profile.country = "India"
        profile.locations = ["India", "Mumbai", "Noida"]
        profile.business_activities = ["ICT & Digital Transformation Solutions", "Cloud & Technology Infrastructure", "Digital Identity & Biometrics"]
        profile.discovery_status = "CONFIRMED"
        db_session.commit()

    # Clean up test-created dummy obligations and tasks for clean baseline
    db_session.query(ComplianceTaskActivity).delete()
    db_session.query(ComplianceTaskEvidence).delete()
    db_session.query(ComplianceTriggerEvent).delete()
    db_session.query(ComplianceTask).filter(ComplianceTask.regulatory_obligation_id.isnot(None)).delete()
    db_session.query(RegulatoryObligation).delete()
    db_session.commit()

    # Run applicability, obligation, and task generation
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    ObligationEngine.generate_obligations(profile.id, db_session)
    TaskEngine.generate_tasks(profile.id, db_session)

    return profile

def test_active_task_can_be_assigned(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 1: An active compliance task can be assigned to a user and responsible function."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).first()

    assign_in = TaskAssignRequest(
        assignee="DevSecOps Lead Engineer",
        responsible_function="Information Security / SecOps",
        notes="Urgent response protocol setup"
    )
    updated_task = TaskExecutionService.assign_task(
        task_id=task.id,
        assign_in=assign_in,
        current_user=compliance_officer_user,
        db=db_session
    )
    assert updated_task.assignee == "DevSecOps Lead Engineer"
    assert updated_task.responsible_function == "Information Security / SecOps"

    # Verify Activity recorded
    act = db_session.query(ComplianceTaskActivity).filter(
        ComplianceTaskActivity.task_id == task.id,
        ComplianceTaskActivity.activity_type == "ASSIGNED"
    ).first()
    assert act is not None
    assert "DevSecOps Lead Engineer" in act.message

def test_task_status_transition_open_to_in_progress(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 2: Task can transition from OPEN to IN_PROGRESS."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.status == "OPEN"
    ).first()

    updated = TaskExecutionService.transition_status(
        task_id=task.id,
        target_status="IN_PROGRESS",
        current_user=compliance_officer_user,
        db=db_session,
        reason="Work commenced on incident response workflow"
    )
    assert updated.status == "IN_PROGRESS"

def test_task_can_be_blocked(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 3: Task can be marked BLOCKED."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    updated = TaskExecutionService.transition_status(
        task_id=task.id,
        target_status="BLOCKED",
        current_user=compliance_officer_user,
        db=db_session,
        reason="Awaiting NTP server hardware credentials from NOC"
    )
    assert updated.status == "BLOCKED"

def test_blocked_task_can_resume(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 4: A BLOCKED task can transition back to IN_PROGRESS."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()
    task.status = "BLOCKED"
    db_session.commit()

    updated = TaskExecutionService.transition_status(
        task_id=task.id,
        target_status="IN_PROGRESS",
        current_user=compliance_officer_user,
        db=db_session,
        reason="NOC credentials received, synchronization resumed"
    )
    assert updated.status == "IN_PROGRESS"

def test_task_completion_records_timestamp_and_user(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 5: Task completion records completed_at and completed_by."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    completed = TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session,
        complete_in=TaskCompleteRequest(confirmation_notes="All standard NTP servers configured")
    )
    assert completed.status == "COMPLETED"
    assert completed.completed_at is not None
    assert completed.completed_by == compliance_officer_user.full_name

def test_task_completion_creates_activity(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 6: Completing a task creates a COMPLETED ComplianceTaskActivity."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session
    )
    act = db_session.query(ComplianceTaskActivity).filter(
        ComplianceTaskActivity.task_id == task.id,
        ComplianceTaskActivity.activity_type == "COMPLETED"
    ).first()
    assert act is not None
    assert act.actor_name == compliance_officer_user.full_name

def test_task_completion_creates_audit_log(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 7: Completing a task creates an immutable AuditLog entry."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session
    )
    audit = db_session.query(AuditLog).filter(
        AuditLog.target_id == task.id,
        AuditLog.action == "TASK_COMPLETED"
    ).first()
    assert audit is not None
    assert audit.user_name == compliance_officer_user.full_name

def test_task_completion_does_not_modify_obligation(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 8: Completing a task does NOT alter RegulatoryObligation.status."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).first()
    ob_id = task.regulatory_obligation_id

    TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session
    )
    ob = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.id == ob_id).first()
    assert ob.status == "ACTIVE"

def test_task_completion_does_not_modify_applicability(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 9: Completing a task does NOT alter RegulatoryApplicabilityAssessment.status."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).first()

    TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session
    )
    assess = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.regulation_id == task.regulation_id,
        RegulatoryApplicabilityAssessment.organization_id == profile.id
    ).first()
    assert assess.status == "APPLICABLE"

def test_reopen_preserves_history(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 10: Reopening a task transitions status to REOPENED and preserves completion history."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    TaskExecutionService.complete_task(
        task_id=task.id,
        current_user=compliance_officer_user,
        db=db_session
    )
    comp_time = task.completed_at

    reopened = TaskExecutionService.reopen_task(
        task_id=task.id,
        reopen_in=TaskReopenRequest(reopen_reason="Quarterly audit revealed secondary DNS NTP drift"),
        current_user=compliance_officer_user,
        db=db_session
    )
    assert reopened.status == "REOPENED"
    assert reopened.reopened_at is not None
    assert reopened.reopened_by == compliance_officer_user.full_name
    assert reopened.completed_at == comp_time  # Historical timestamp preserved!

def test_operational_evidence_attaches_to_task(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 11: Operational evidence (screenshot, config, log) attaches to task."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    ev_in = EvidenceCreate(
        evidence_type="LOG",
        file_name="ntp_drift_audit_log_2026.log",
        file_url="https://s3.compliance.corp/logs/ntp_drift_2026.log",
        description="NTP daemon synchronization logs verified against NPL server"
    )
    ev = TaskExecutionService.add_evidence(
        task_id=task.id,
        evidence_in=ev_in,
        current_user=compliance_officer_user,
        db=db_session
    )
    assert ev.id is not None
    assert ev.file_name == "ntp_drift_audit_log_2026.log"
    assert ev.evidence_type == "LOG"
    assert ev.task_id == task.id

def test_evidence_records_uploader(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 12: Evidence records preserve uploader and role."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    ev_in = EvidenceCreate(
        evidence_type="CERTIFICATE",
        file_name="ciso_poc_designation_form.pdf",
        description="Form signed by CISO and submitted to CERT-In"
    )
    ev = TaskExecutionService.add_evidence(
        task_id=task.id,
        evidence_in=ev_in,
        current_user=compliance_officer_user,
        db=db_session
    )
    assert ev.uploaded_by == compliance_officer_user.full_name
    assert ev.uploader_role == compliance_officer_user.role

def test_event_driven_task_has_null_due_date_before_trigger(db_session: Session, setup_execution_baseline):
    """TEST 13: Event-driven tasks have due_date == NULL before a trigger event occurs."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.control_code == "OBL-CERTIN-INCIDENT-6H"
    ).first()
    assert task.due_date is None
    assert task.trigger_event_id is None
    assert task.trigger_type == "INCIDENT_DETECTED"

def test_incident_trigger_calculates_due_date(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 14: An INCIDENT_DETECTED trigger event deterministically calculates due_date (6 hours)."""
    profile = setup_execution_baseline
    trigger_time = datetime.datetime(2026, 8, 13, 10, 0, 0)

    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=trigger_time,
        source="SOC Alert #98234",
        description="Ransomware lateral movement detected on intranet core switch"
    )
    event, affected = TaskExecutionService.process_trigger_event(
        event_in=event_in,
        current_user=compliance_officer_user,
        db=db_session
    )
    assert len(affected) >= 1
    incident_task = next(t for t in affected if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert incident_task.trigger_event_id == event.id
    assert incident_task.trigger_timestamp == trigger_time
    assert incident_task.due_date == trigger_time.date()

def test_trigger_calculation_preserves_due_rule(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 15: Trigger event calculation preserves the statutory due_rule string."""
    profile = setup_execution_baseline
    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=datetime.datetime.utcnow(),
        source="SOC Monitoring System",
        description="DDoS flood detected on external gateway"
    )
    event, affected = TaskExecutionService.process_trigger_event(
        event_in=event_in,
        current_user=compliance_officer_user,
        db=db_session
    )
    incident_task = next(t for t in affected if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert "Within 6 hours" in incident_task.due_rule

def test_no_due_date_for_continuous_obligation(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 16: Continuous obligations have no trigger_type and remain due_date == NULL."""
    profile = setup_execution_baseline
    log_task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.control_code == "OBL-CERTIN-LOGS-180D"
    ).first()
    assert log_task.due_date is None
    assert log_task.trigger_type is None

    # Even after recording an INCIDENT_DETECTED event, continuous tasks are unaffected
    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=datetime.datetime.utcnow(),
        source="SOC Monitoring",
        description="Incident notification"
    )
    TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)

    refreshed_log_task = db_session.query(ComplianceTask).filter(ComplianceTask.id == log_task.id).first()
    assert refreshed_log_task.due_date is None

def test_untriggered_event_task_is_not_overdue(db_session: Session, auth_headers: dict, setup_execution_baseline):
    """TEST 17: Untriggered event-driven task (due_date == NULL) is NOT marked overdue."""
    resp = client.get("/api/v1/tasks", headers=auth_headers)
    assert resp.status_code == 200
    tasks_data = resp.json()
    incident_task = next(t for t in tasks_data if t["control_code"] == "OBL-CERTIN-INCIDENT-6H")
    assert incident_task["is_overdue"] is False
    assert "Awaiting trigger event" in incident_task["deadline_status_message"]

def test_triggered_task_can_be_overdue(db_session: Session, compliance_officer_user, auth_headers: dict, setup_execution_baseline):
    """TEST 18: A triggered task with past due_date is marked overdue."""
    profile = setup_execution_baseline
    # Trigger an incident 3 days in the past
    past_trigger = datetime.datetime.utcnow() - datetime.timedelta(days=3)
    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=past_trigger,
        source="Historical Breach Log",
        description="Old unresolved incident"
    )
    TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)

    resp = client.get("/api/v1/tasks", headers=auth_headers)
    tasks_data = resp.json()
    incident_task = next(t for t in tasks_data if t["control_code"] == "OBL-CERTIN-INCIDENT-6H")
    assert incident_task["is_overdue"] is True

def test_trigger_event_is_audited(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 19: Recording a trigger event creates an immutable AuditLog entry."""
    profile = setup_execution_baseline
    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=datetime.datetime.utcnow(),
        source="CISO Emergency Broadcast",
        description="Phishing attack compromised credential vault"
    )
    event, affected = TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)

    audit = db_session.query(AuditLog).filter(
        AuditLog.target_id == event.id,
        AuditLog.action == "COMPLIANCE_TRIGGER_EVENT_RECORDED"
    ).first()
    assert audit is not None
    assert audit.target_type == "COMPLIANCE_TRIGGER_EVENT"

def test_task_provenance_remains_intact(db_session: Session, auth_headers: dict, setup_execution_baseline):
    """TEST 20: GET /api/v1/tasks/{task_id} returns full upstream legal and organizational provenance."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).first()

    resp = client.get(f"/api/v1/tasks/{task.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["regulation_id"] is not None
    assert data["regulatory_obligation_id"] is not None
    assert data["source_citation"] is not None
    assert data["authoritative_source_url"] is not None
    assert len(data["regulatory_evidence_refs"]) > 0
    assert len(data["organization_evidence_refs"]) > 0

def test_manual_tasks_are_not_broken(db_session: Session, auth_headers: dict, setup_execution_baseline):
    """TEST 21: Existing manual compliance tasks continue to work alongside regulatory tasks."""
    payload = {
        "regulation_id": "reg-cyber-2026",
        "title": "Manual Annual Pentest Verification",
        "assignee": "Lead Pentester",
        "reviewer": "CISO",
        "priority": "HIGH",
        "status": "OPEN",
        "due_date": "2026-12-31"
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    created = resp.json()
    assert created["regulatory_obligation_id"] is None
    assert created["due_date"] == "2026-12-31"

def test_authorization_prevents_unauthorized_completion(db_session: Session, unauthorized_auth_headers: dict, setup_execution_baseline):
    """TEST 22: Unauthorized users (e.g. Guest Reader) cannot complete compliance tasks."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    resp = client.post(f"/api/v1/tasks/{task.id}/complete", headers=unauthorized_auth_headers)
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()

def test_duplicate_trigger_does_not_create_duplicate_deadline(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 23: Duplicate trigger event application does not corrupt or duplicate task deadlines."""
    profile = setup_execution_baseline
    event_timestamp = datetime.datetime(2026, 8, 13, 11, 0, 0)
    event_in = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=event_timestamp,
        source="SIEM Alert Stream",
        description="Port scanning detected"
    )
    event, affected_1 = TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)
    task = db_session.query(ComplianceTask).filter(ComplianceTask.control_code == "OBL-CERTIN-INCIDENT-6H").first()
    first_due_date = task.due_date

    # Re-process same event instance
    event_in_2 = TriggerEventCreate(
        event_type="INCIDENT_DETECTED",
        event_timestamp=event_timestamp,
        source="SIEM Alert Stream",
        description="Port scanning detected (duplicate packet)"
    )
    event_2, affected_2 = TaskExecutionService.process_trigger_event(event_in_2, compliance_officer_user, db_session)
    refreshed_task = db_session.query(ComplianceTask).filter(ComplianceTask.control_code == "OBL-CERTIN-INCIDENT-6H").first()
    assert refreshed_task.due_date == first_due_date

def test_task_completion_does_not_change_regulation(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 24: Completing a task does NOT alter Regulation records or content."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()
    reg_id = task.regulation_id

    reg_before = db_session.query(Regulation).filter(Regulation.id == reg_id).first()
    reg_title_before = reg_before.title

    TaskExecutionService.complete_task(task.id, compliance_officer_user, db_session)

    reg_after = db_session.query(Regulation).filter(Regulation.id == reg_id).first()
    assert reg_after.title == reg_title_before

def test_reopening_does_not_delete_evidence(db_session: Session, compliance_officer_user, setup_execution_baseline):
    """TEST 25: Reopening a completed task preserves all previously attached operational evidence."""
    profile = setup_execution_baseline
    task = db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()

    # 1. Attach evidence
    ev_in = EvidenceCreate(
        evidence_type="REPORT",
        file_name="initial_pentest_remediation.pdf",
        description="First remediation report"
    )
    TaskExecutionService.add_evidence(task.id, ev_in, compliance_officer_user, db_session)

    # 2. Complete task
    TaskExecutionService.complete_task(task.id, compliance_officer_user, db_session)

    # 3. Reopen task
    TaskExecutionService.reopen_task(task.id, TaskReopenRequest(reopen_reason="Audit follow-up"), compliance_officer_user, db_session)

    # 4. Verify evidence remains intact
    ev_list = db_session.query(ComplianceTaskEvidence).filter(ComplianceTaskEvidence.task_id == task.id).all()
    assert len(ev_list) == 1
    assert ev_list[0].file_name == "initial_pentest_remediation.pdf"
