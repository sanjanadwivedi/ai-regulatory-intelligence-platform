"""
test_control_task_engine.py
Phase 3: Control -> Task Engine Integration tests.

20 tests covering:
1.  CONTROL_GAP generates REMEDIATION task.
2.  INEFFECTIVE generates REMEDIATION task.
3.  CONTROL_REVIEW_REQUIRED generates REVIEW task.
4.  EFFECTIVE generates no new remediation task.
5.  NOT_APPLICABLE (obligation SUPERSEDED) generates no task.
6.  REQUIRES_REVIEW obligation generates no remediation task.
7.  Multiple obligations mapped to one control -> ONE task.
8.  Repeated generation is idempotent.
9.  Existing active task prevents duplicate creation.
10. Control state CONTROL_GAP -> EFFECTIVE: existing open task transitions to SUPERSEDED.
11. Historical tasks remain immutable (COMPLETED stays COMPLETED after re-run).
12. Org A cannot access Org B tasks.
13. Org A cannot trigger task from Org B control.
14. Org A cannot trigger task from Org B obligation.
15. Client organization_id cannot hijack tenant (engine uses org_id parameter, not request body).
16. Task evidence cannot directly change control state (ControlAssessment not mutated by TaskEngine).
17. ControlEngine remains authoritative after evidence submission.
18. AuditLog generated for material task creation.
19. No duplicate AuditLog for idempotent (no-change) generation.
20. Control -> obligation traceability preserved via ObligationControlMapping.
"""

import pytest
import uuid
import datetime
from sqlalchemy.orm import Session
from app.core.database import Base, engine, SessionLocal
from app.models.domain import (
    EnterpriseProfile, RegulatoryObligation,
    Regulation, InternalControl, ControlAssessment,
    ComplianceTask, ObligationControlMapping,
    AuditLog, RegulatoryApplicabilityAssessment,
    DiscoveredFact
)
from app.services.task_engine import TaskEngine


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clean tables in dependency order
    db.query(AuditLog).delete()
    db.query(ComplianceTask).delete()
    db.query(ControlAssessment).delete()
    db.query(ObligationControlMapping).delete()
    db.query(RegulatoryObligation).delete()
    db.query(InternalControl).delete()
    db.query(DiscoveredFact).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def org_a(db_session: Session):
    org = EnterpriseProfile(
        id=str(uuid.uuid4()),
        organization_name="Task Test Org A",
        industry_sector="Tech",
        discovery_status="CONFIRMED"
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture(scope="function")
def org_b(db_session: Session):
    org = EnterpriseProfile(
        id=str(uuid.uuid4()),
        organization_name="Task Test Org B",
        industry_sector="Finance",
        discovery_status="CONFIRMED"
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture(scope="function")
def reg(db_session: Session):
    r = Regulation(
        id=str(uuid.uuid4()),
        title="Test Task Regulation",
        authority="Test Auth",
        publication_date=datetime.date.today(),
        sector="Tech",
        region="Global",
        content_text="Test regulation content"
    )
    db_session.add(r)
    db_session.commit()
    return r


def _make_obligation(db, org, reg, code, status="ACTIVE"):
    ob = RegulatoryObligation(
        organization_id=org.id,
        regulation_id=reg.id,
        applicability_assessment_id="dummy-" + str(uuid.uuid4()),
        obligation_code=code,
        title=f"Obligation {code}",
        description="Test obligation",
        obligation_type="SECURITY_CONTROL",
        source_citation=f"Section {code}",
        status=status,
        priority="HIGH"
    )
    db.add(ob)
    db.commit()
    return ob


def _make_control(db, org, code):
    ctrl = InternalControl(
        organization_id=org.id,
        control_code=code,
        name=f"Control {code}",
        description="Test control",
        category="Security",
        owner_department="InfoSec",
        status="DRAFT"
    )
    db.add(ctrl)
    db.commit()
    return ctrl


def _make_assessment(db, org, control, status="CONTROL_GAP"):
    ca = ControlAssessment(
        organization_id=org.id,
        control_id=control.id,
        assessment_status=status,
        control_state="IMPLEMENTED" if status != "CONTROL_GAP" else "DRAFT",
        evidence_summary="NO_EVIDENCE" if status == "CONTROL_GAP" else "EVIDENCE_PRESENT",
        evaluated_by="Test Engine"
    )
    db.add(ca)
    db.commit()
    return ca


def _map_obligation_to_control(db, org, obligation, control):
    m = ObligationControlMapping(
        organization_id=org.id,
        obligation_id=obligation.id,
        control_id=control.id,
        active=1
    )
    db.add(m)
    db.commit()
    return m


# ============================================================
# Tests
# ============================================================

# Test 1
def test_control_gap_generates_remediation_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T01")
    ob = _make_obligation(db_session, org_a, reg, "OB-T01")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 1, "Expected exactly one task for CONTROL_GAP"
    assert my_tasks[0].task_type == "REMEDIATION"
    assert my_tasks[0].status == "OPEN"
    assert my_tasks[0].organization_id == org_a.id


# Test 2
def test_ineffective_generates_remediation_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T02")
    ob = _make_obligation(db_session, org_a, reg, "OB-T02")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "INEFFECTIVE")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 1
    assert my_tasks[0].task_type == "REMEDIATION"


# Test 3
def test_control_review_required_generates_review_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T03")
    ob = _make_obligation(db_session, org_a, reg, "OB-T03")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_REVIEW_REQUIRED")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 1
    assert my_tasks[0].task_type == "REVIEW"


# Test 4
def test_effective_generates_no_new_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T04")
    ob = _make_obligation(db_session, org_a, reg, "OB-T04")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "EFFECTIVE")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 0, "EFFECTIVE control must not generate any new task"


# Test 5: NOT_APPLICABLE → obligation is SUPERSEDED, not ACTIVE
def test_superseded_obligation_no_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T05")
    ob = _make_obligation(db_session, org_a, reg, "OB-T05", status="SUPERSEDED")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    # The obligation is SUPERSEDED → not active → mapping ignored → no task
    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 0, "SUPERSEDED obligation must not generate any task"


# Test 6: REQUIRES_REVIEW obligation must not generate remediation task
def test_requires_review_obligation_no_remediation_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T06")
    ob = _make_obligation(db_session, org_a, reg, "OB-T06", status="REQUIRES_REVIEW")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    # REQUIRES_REVIEW obligation is not ACTIVE → not included in mapping evaluation
    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 0, "REQUIRES_REVIEW obligation must not trigger remediation task"


# Test 7: Multiple obligations → ONE task for the shared control
def test_multiple_obligations_one_control_one_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T07")
    obs = []
    for i in range(3):
        ob = _make_obligation(db_session, org_a, reg, f"OB-T07-{i}")
        _map_obligation_to_control(db_session, org_a, ob, ctrl)
        obs.append(ob)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 1, (
        f"3 obligations to 1 control must produce 1 task, got {len(my_tasks)}"
    )


# Test 8: Idempotent — second run produces no new tasks
def test_generation_is_idempotent(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T08")
    ob = _make_obligation(db_session, org_a, reg, "OB-T08")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    TaskEngine.generate_tasks(org_a.id, db_session)
    TaskEngine.generate_tasks(org_a.id, db_session)

    task_count = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_a.id,
        ComplianceTask.control_id == ctrl.id,
        ComplianceTask.status.notin_(["SUPERSEDED", "COMPLETED", "CANCELLED"])
    ).count()
    assert task_count == 1, f"Idempotent: expected 1 open task, got {task_count}"


# Test 9: Existing active task prevents duplicate creation
def test_existing_active_task_prevents_duplicate(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T09")
    ob = _make_obligation(db_session, org_a, reg, "OB-T09")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    # First run
    TaskEngine.generate_tasks(org_a.id, db_session)
    first_count = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_a.id,
        ComplianceTask.control_id == ctrl.id,
        ComplianceTask.status == "OPEN"
    ).count()
    assert first_count == 1

    # Second run
    TaskEngine.generate_tasks(org_a.id, db_session)
    second_count = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_a.id,
        ComplianceTask.control_id == ctrl.id,
        ComplianceTask.status == "OPEN"
    ).count()
    assert second_count == 1, "Second run must not create duplicate OPEN task"


# Test 10: CONTROL_GAP → EFFECTIVE: open task transitions to SUPERSEDED
def test_control_gap_to_effective_transitions_task(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T10")
    ob = _make_obligation(db_session, org_a, reg, "OB-T10")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    TaskEngine.generate_tasks(org_a.id, db_session)

    gap_task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_a.id,
        ComplianceTask.control_id == ctrl.id,
        ComplianceTask.task_type == "REMEDIATION"
    ).first()
    assert gap_task is not None
    assert gap_task.status == "OPEN"

    # Now promote to EFFECTIVE
    effective_assess = ControlAssessment(
        organization_id=org_a.id,
        control_id=ctrl.id,
        assessment_status="EFFECTIVE",
        control_state="EFFECTIVE",
        evidence_summary="EVIDENCE_AUTHORITATIVE",
        evaluated_by="Test Engine",
        evaluated_at=datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
    )
    db_session.add(effective_assess)
    db_session.commit()

    TaskEngine.generate_tasks(org_a.id, db_session)

    db_session.refresh(gap_task)
    assert gap_task.status == "SUPERSEDED", (
        f"Gap task should be SUPERSEDED after control becomes EFFECTIVE, got {gap_task.status}"
    )


# Test 11: Historical COMPLETED tasks remain immutable after re-run
def test_completed_tasks_remain_immutable(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T11")
    ob = _make_obligation(db_session, org_a, reg, "OB-T11")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    TaskEngine.generate_tasks(org_a.id, db_session)

    task = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_a.id,
        ComplianceTask.control_id == ctrl.id
    ).first()
    # Manually complete it
    task.status = "COMPLETED"
    task.completed_at = datetime.datetime.utcnow()
    task.completed_by = "Test User"
    db_session.commit()

    # Re-run should not reopen it
    TaskEngine.generate_tasks(org_a.id, db_session)
    db_session.refresh(task)
    assert task.status == "COMPLETED", "COMPLETED task must not be mutated by TaskEngine"


# Test 12: Org A cannot access Org B tasks (engine isolation)
def test_org_a_cannot_see_org_b_tasks(db_session, org_a, org_b, reg):
    ctrl_b = _make_control(db_session, org_b, "CTRL-T12B")
    ob_b = _make_obligation(db_session, org_b, reg, "OB-T12B")
    _map_obligation_to_control(db_session, org_b, ob_b, ctrl_b)
    _make_assessment(db_session, org_b, ctrl_b, "CONTROL_GAP")

    tasks_a = TaskEngine.generate_tasks(org_a.id, db_session)

    assert not any(t.control_id == ctrl_b.id for t in tasks_a), (
        "Org A must not receive Org B tasks"
    )


# Test 13: Org A cannot trigger task from Org B control
def test_org_a_cannot_use_org_b_control(db_session, org_a, org_b, reg):
    ctrl_b = _make_control(db_session, org_b, "CTRL-T13B")
    ob_a = _make_obligation(db_session, org_a, reg, "OB-T13A")
    # Trying to map Org A obligation to Org B control (cross-tenant)
    cross_mapping = ObligationControlMapping(
        organization_id=org_a.id,  # Org A mapping
        obligation_id=ob_a.id,
        control_id=ctrl_b.id,      # But Org B control!
        active=1
    )
    db_session.add(cross_mapping)
    db_session.commit()

    _make_assessment(db_session, org_b, ctrl_b, "CONTROL_GAP")

    tasks_a = TaskEngine.generate_tasks(org_a.id, db_session)

    # The engine verifies control.organization_id == organization_id
    my_tasks = [t for t in tasks_a if t.control_id == ctrl_b.id]
    assert len(my_tasks) == 0, (
        "Org A must not generate tasks from Org B controls"
    )


# Test 14: Org A cannot trigger task from Org B obligation
def test_org_a_cannot_use_org_b_obligation(db_session, org_a, org_b, reg):
    ctrl_a = _make_control(db_session, org_a, "CTRL-T14A")
    ob_b = _make_obligation(db_session, org_b, reg, "OB-T14B")

    # Cross-tenant: Org B obligation mapped in Org A
    cross_mapping = ObligationControlMapping(
        organization_id=org_a.id,
        obligation_id=ob_b.id,   # Org B obligation
        control_id=ctrl_a.id,
        active=1
    )
    db_session.add(cross_mapping)
    db_session.commit()

    _make_assessment(db_session, org_a, ctrl_a, "CONTROL_GAP")

    tasks_a = TaskEngine.generate_tasks(org_a.id, db_session)

    # The engine only evaluates ACTIVE obligations for org_a.id
    # ob_b belongs to org_b → it will NOT appear in org_a's active_obligation_ids
    my_tasks = [t for t in tasks_a if t.regulatory_obligation_id == ob_b.id]
    assert len(my_tasks) == 0, (
        "Org A must not generate tasks from Org B obligations"
    )


# Test 15: Client organization_id cannot hijack tenant context
def test_client_org_id_cannot_hijack_tenant(db_session, org_a, org_b, reg):
    """
    The TaskEngine.generate_tasks(organization_id, ...) uses the server-enforced
    organization_id, not one supplied by the client in a request body.
    This test verifies that calling generate_tasks with org_b.id cannot access org_a's controls.
    """
    ctrl_a = _make_control(db_session, org_a, "CTRL-T15A")
    ob_a = _make_obligation(db_session, org_a, reg, "OB-T15A")
    _map_obligation_to_control(db_session, org_a, ob_a, ctrl_a)
    _make_assessment(db_session, org_a, ctrl_a, "CONTROL_GAP")

    # Generate tasks as Org B — must NOT see Org A's controls
    tasks_for_b = TaskEngine.generate_tasks(org_b.id, db_session)
    assert not any(t.control_id == ctrl_a.id for t in tasks_for_b), (
        "Supplying Org B id must not expose Org A controls"
    )


# Test 16: Task evidence cannot directly mark a control EFFECTIVE
def test_evidence_cannot_directly_mark_control_effective(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T16")
    ob = _make_obligation(db_session, org_a, reg, "OB-T16")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    TaskEngine.generate_tasks(org_a.id, db_session)

    # Add evidence to task — this should NOT change ControlAssessment
    # TaskEngine doesn't read evidence and change ControlAssessment
    assessment_before = db_session.query(ControlAssessment).filter(
        ControlAssessment.organization_id == org_a.id,
        ControlAssessment.control_id == ctrl.id
    ).order_by(ControlAssessment.evaluated_at.desc()).first()

    status_before = assessment_before.assessment_status

    # Re-run engine — without a new ControlAssessment, state is unchanged
    TaskEngine.generate_tasks(org_a.id, db_session)

    assessment_after = db_session.query(ControlAssessment).filter(
        ControlAssessment.organization_id == org_a.id,
        ControlAssessment.control_id == ctrl.id
    ).order_by(ControlAssessment.evaluated_at.desc()).first()

    assert assessment_after.assessment_status == status_before, (
        "TaskEngine must NOT mutate ControlAssessment records"
    )
    assert assessment_after.id == assessment_before.id, (
        "TaskEngine must NOT create new ControlAssessment records"
    )


# Test 17: ControlEngine remains authoritative after evidence submission
def test_control_engine_remains_authoritative(db_session, org_a, reg):
    """
    Verify that after task generation, the ControlAssessment count is unchanged.
    Only ControlEngine.evaluate_organization_controls() should create ControlAssessments.
    """
    ctrl = _make_control(db_session, org_a, "CTRL-T17")
    ob = _make_obligation(db_session, org_a, reg, "OB-T17")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    count_before = db_session.query(ControlAssessment).filter(
        ControlAssessment.organization_id == org_a.id
    ).count()

    TaskEngine.generate_tasks(org_a.id, db_session)
    TaskEngine.generate_tasks(org_a.id, db_session)

    count_after = db_session.query(ControlAssessment).filter(
        ControlAssessment.organization_id == org_a.id
    ).count()

    assert count_after == count_before, (
        f"TaskEngine must not create ControlAssessment records. Before: {count_before}, After: {count_after}"
    )


# Test 18: AuditLog generated for material task creation
def test_audit_log_generated_for_task_creation(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T18")
    ob = _make_obligation(db_session, org_a, reg, "OB-T18")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    audit_count_before = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org_a.id,
        AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
    ).count()

    TaskEngine.generate_tasks(org_a.id, db_session, evaluated_by="Test Auditor")

    audit_count_after = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org_a.id,
        AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
    ).count()

    assert audit_count_after > audit_count_before, (
        "Material task creation must produce an AuditLog entry"
    )


# Test 19: No duplicate AuditLog for idempotent (no-change) generation
def test_no_duplicate_audit_log_for_idempotent_generation(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T19")
    ob = _make_obligation(db_session, org_a, reg, "OB-T19")
    _map_obligation_to_control(db_session, org_a, ob, ctrl)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    # First run (material)
    TaskEngine.generate_tasks(org_a.id, db_session)

    count_after_first = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org_a.id,
        AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
    ).count()

    # Second run (idempotent — no new tasks created, no updates)
    TaskEngine.generate_tasks(org_a.id, db_session)

    count_after_second = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org_a.id,
        AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
    ).count()

    assert count_after_second == count_after_first, (
        "Idempotent run (no new tasks) must not produce additional AuditLog entries"
    )


# Test 20: Complete control → obligation traceability via ObligationControlMapping
def test_complete_obligation_traceability(db_session, org_a, reg):
    ctrl = _make_control(db_session, org_a, "CTRL-T20")
    obs = []
    for i in range(3):
        ob = _make_obligation(db_session, org_a, reg, f"OB-T20-{i}")
        _map_obligation_to_control(db_session, org_a, ob, ctrl)
        obs.append(ob)
    _make_assessment(db_session, org_a, ctrl, "CONTROL_GAP")

    tasks = TaskEngine.generate_tasks(org_a.id, db_session)

    my_tasks = [t for t in tasks if t.control_id == ctrl.id]
    assert len(my_tasks) == 1

    # Verify traceability: we can find all obligations via ObligationControlMapping
    mappings = db_session.query(ObligationControlMapping).filter(
        ObligationControlMapping.organization_id == org_a.id,
        ObligationControlMapping.control_id == ctrl.id,
        ObligationControlMapping.active == 1
    ).all()
    mapped_ob_ids = {m.obligation_id for m in mappings}
    expected_ob_ids = {ob.id for ob in obs}
    assert mapped_ob_ids == expected_ob_ids, (
        "All 3 obligations must remain traceable via ObligationControlMapping"
    )

    # Verify task links to at least one obligation for backward compatibility
    task = my_tasks[0]
    assert task.regulatory_obligation_id is not None, (
        "Task must retain regulatory_obligation_id for backward compatibility"
    )
    assert task.regulatory_obligation_id in expected_ob_ids, (
        "Task's regulatory_obligation_id must point to a real mapped obligation"
    )
