import pytest
import datetime
import uuid
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    DiscoveredFact,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    AuditLog
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.obligation_engine import ObligationEngine
from app.services.task_engine import TaskEngine
from app.core.security import create_access_token
from fastapi.testclient import TestClient
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
def auth_headers(db_session: Session):
    user = db_session.query(EnterpriseUser).first()
    if not user:
        user = EnterpriseUser(
            full_name="Compliance Auditor",
            role="Compliance Officer",
            email="auditor@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def setup_org_and_obligations(db_session: Session):
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

    # Run applicability and obligation generation
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    ObligationEngine.generate_obligations(profile.id, db_session)
    return profile

def test_active_obligation_generates_task(db_session: Session, setup_org_and_obligations):
    """
    TEST 1: ACTIVE obligations (e.g. CERT-In) generate operational compliance tasks.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    
    cert_in_tasks = [t for t in tasks if t.regulation_id == "reg-cyber-2026"]
    assert len(cert_in_tasks) == 4
    for t in cert_in_tasks:
        assert t.regulatory_obligation_id is not None
        assert t.organization_id == profile.id
        assert t.status == "OPEN"

def test_not_applicable_generates_zero_tasks(db_session: Session, setup_org_and_obligations):
    """
    TEST 2: NOT_APPLICABLE regulations (HIPAA, SEC Release) generate ZERO tasks.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)

    hipaa_tasks = [t for t in tasks if t.regulation_id == "reg-hipaa-2026"]
    assert len(hipaa_tasks) == 0

    sec_tasks = [t for t in tasks if t.regulation_id == "reg-sec-trading-2026"]
    assert len(sec_tasks) == 0

def test_requires_review_assessment_generates_zero_tasks(db_session: Session, setup_org_and_obligations):
    """
    TEST 3: REQUIRES_REVIEW assessments (e.g. RBI publications, generic scans) generate ZERO tasks.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)

    srva_tasks = [t for t in tasks if t.regulation_id == "reg-scan-rbi-2026"]
    assert len(srva_tasks) == 0

def test_requires_review_obligation_generates_zero_tasks(db_session: Session, setup_org_and_obligations):
    """
    TEST 4: Any obligation with status == REQUIRES_REVIEW MUST NOT generate an operational task.
    """
    profile = setup_org_and_obligations
    # Create a dummy REQUIRES_REVIEW obligation
    dummy_ob = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-cyber-2026",
        applicability_assessment_id="dummy-assessment-id",
        obligation_code=f"OBL-REV-{uuid.uuid4().hex[:6]}",
        title="Unreviewed Obligation",
        description="Requires legal clarification",
        obligation_type="OTHER",
        source_citation="Uncertain Section",
        status="REQUIRES_REVIEW",
        priority="MEDIUM"
    )
    db_session.add(dummy_ob)
    db_session.commit()

    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    dummy_tasks = [t for t in tasks if t.regulatory_obligation_id == dummy_ob.id]
    assert len(dummy_tasks) == 0

def test_superseded_obligation_generates_zero_tasks(db_session: Session, setup_org_and_obligations):
    """
    TEST 5: SUPERSEDED obligations do NOT generate new tasks.
    """
    profile = setup_org_and_obligations
    dummy_sup = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-cyber-2026",
        applicability_assessment_id="dummy-assessment-id",
        obligation_code=f"OBL-SUP-{uuid.uuid4().hex[:6]}",
        title="Old Replaced Obligation",
        description="Replaced by new version",
        obligation_type="REPORTING",
        source_citation="Old Citation",
        status="SUPERSEDED",
        priority="LOW"
    )
    db_session.add(dummy_sup)
    db_session.commit()

    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    sup_tasks = [t for t in tasks if t.regulatory_obligation_id == dummy_sup.id]
    assert len(sup_tasks) == 0

def test_regulatory_signal_cannot_generate_task(db_session: Session, setup_org_and_obligations):
    """
    TEST 6: Website regulatory signals MUST NEVER directly generate a compliance task.
    """
    profile = setup_org_and_obligations
    signal = DiscoveredFact(
        organization_id=profile.id,
        fact_type="REGULATORY_SIGNAL",
        fact_value="Direct Website Regulatory Signal",
        source_url="https://in.nec.com/legal",
        snippet="Legal statement mentioning external standard.",
        status="CONFIRMED",
        confidence=0.95
    )
    db_session.add(signal)
    db_session.commit()

    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    signal_tasks = [t for t in tasks if "Direct Website" in t.title]
    assert len(signal_tasks) == 0

def test_task_preserves_obligation_provenance(db_session: Session, setup_org_and_obligations):
    """
    TEST 7: Every generated task maintains full provenance back to obligation and regulation.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    for t in tasks:
        assert t.regulatory_obligation_id is not None
        assert t.organization_id == profile.id
        assert t.regulation_id is not None

def test_task_preserves_statutory_citation(db_session: Session, setup_org_and_obligations):
    """
    TEST 8: Every task preserves the authoritative statutory citation.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    for t in tasks:
        assert t.source_citation is not None
        assert "70B(6)" in t.source_citation
        assert t.authoritative_source_url is not None

def test_task_preserves_due_rule(db_session: Session, setup_org_and_obligations):
    """
    TEST 9: Tasks preserve exact statutory due rules (e.g. 6 hours, 180 days).
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    incident_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert "6 hours" in incident_task.due_rule

    log_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-LOGS-180D")
    assert "180 days" in log_task.due_rule

def test_no_hallucinated_due_date(db_session: Session, setup_org_and_obligations):
    """
    TEST 10: Event-based / continuous tasks have due_date == NULL (NO hallucinated calendar deadlines).
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    incident_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert incident_task.due_date is None

    ntp_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-NTP-SYNC")
    assert ntp_task.due_date is None

def test_responsible_function_preserved(db_session: Session, setup_org_and_obligations):
    """
    TEST 11: Responsible function is preserved from the obligation without inventing a specific person.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    incident_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert "Incident Response" in incident_task.responsible_function or "SecOps" in incident_task.responsible_function
    assert incident_task.assignee == incident_task.responsible_function

def test_priority_preserved(db_session: Session, setup_org_and_obligations):
    """
    TEST 12: Obligation priority (CRITICAL/HIGH/MEDIUM) is preserved without AI recalculation.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    incident_task = next(t for t in tasks if t.control_code == "OBL-CERTIN-INCIDENT-6H")
    assert incident_task.priority == "CRITICAL"

def test_generation_is_idempotent_no_duplicates(db_session: Session, setup_org_and_obligations):
    """
    TEST 13, 14: Repeated generation updates existing task records without creating duplicates.
    """
    profile = setup_org_and_obligations
    tasks_1 = TaskEngine.generate_tasks(profile.id, db_session)
    count_1 = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).count()

    tasks_2 = TaskEngine.generate_tasks(profile.id, db_session)
    count_2 = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == profile.id,
        ComplianceTask.regulatory_obligation_id.isnot(None)
    ).count()

    assert count_1 == count_2
    assert len(tasks_1) == len(tasks_2) == 4

def test_audit_log_created(db_session: Session, auth_headers: dict, setup_org_and_obligations):
    """
    TEST 15: POST /api/v1/tasks/generate creates an immutable AuditLog entry.
    """
    resp = client.post("/api/v1/tasks/generate", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 4

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.target_type == "COMPLIANCE_TASK"
    assert "active_obligations_evaluated" in audit.details
    assert "engine_version" in audit.details

def test_task_completion_does_not_modify_obligation_or_applicability(db_session: Session, setup_org_and_obligations):
    """
    TEST 16 & 17: Completing a compliance task updates ONLY operational state,
    and NEVER alters RegulatoryObligation.status or RegulatoryApplicabilityAssessment.status.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    first_task = tasks[0]
    ob_id = first_task.regulatory_obligation_id

    # Complete the task
    first_task.status = "COMPLETED"
    db_session.commit()

    # Verify obligation remains ACTIVE
    ob = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.id == ob_id).first()
    assert ob.status == "ACTIVE"

    # Verify applicability assessment remains APPLICABLE
    assess = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.id == ob.applicability_assessment_id
    ).first()
    assert assess.status == "APPLICABLE"

def test_existing_manual_tasks_still_work(db_session: Session, auth_headers: dict):
    """
    TEST 18: Existing manual task creation flow continues working with no regressions.
    """
    payload = {
        "regulation_id": "reg-cyber-2026",
        "title": "Manual Ad-hoc Audit Task",
        "description": "Perform internal quarterly checklist",
        "assignee": "Auditor Team",
        "reviewer": "CISO",
        "priority": "MEDIUM",
        "status": "NEEDS_REVIEW",
        "due_date": "2026-11-30"
    }
    resp = client.post("/api/v1/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    created = resp.json()
    assert created["title"] == "Manual Ad-hoc Audit Task"
    assert created["regulatory_obligation_id"] is None
    assert created["due_date"] == "2026-11-30"

def test_regulatory_task_and_manual_task_can_coexist(db_session: Session, setup_org_and_obligations):
    """
    TEST 19: Regulatory generated tasks and manual tasks coexist in the database without collision.
    """
    profile = setup_org_and_obligations
    reg_tasks = TaskEngine.generate_tasks(profile.id, db_session)
    
    # Add a manual task
    manual = ComplianceTask(
        regulation_id="reg-cyber-2026",
        title="Custom Manual Policy Review",
        assignee="Legal Team",
        reviewer="CISO",
        priority="LOW",
        status="NEEDS_REVIEW",
        due_date=datetime.date(2026, 12, 1)
    )
    db_session.add(manual)
    db_session.commit()

    all_tasks = db_session.query(ComplianceTask).all()
    assert any(t.regulatory_obligation_id is not None for t in all_tasks)
    assert any(t.regulatory_obligation_id is None for t in all_tasks)

def test_superseded_obligation_does_not_remain_active_task(db_session: Session, setup_org_and_obligations):
    """
    TEST 20: If an obligation becomes SUPERSEDED, re-running task generation transitions the task to SUPERSEDED.
    """
    profile = setup_org_and_obligations
    tasks = TaskEngine.generate_tasks(profile.id, db_session)
    target_task = tasks[0]
    ob = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.id == target_task.regulatory_obligation_id).first()
    
    # Simulate obligation supersession
    ob.status = "SUPERSEDED"
    db_session.commit()

    # Re-run task generation
    updated_tasks = TaskEngine.generate_tasks(profile.id, db_session)
    
    refreshed_task = db_session.query(ComplianceTask).filter(ComplianceTask.id == target_task.id).first()
    assert refreshed_task.status == "SUPERSEDED"
