"""
test_evidence_control_feedback.py
Phase 4: Evidence -> Control Assessment Feedback Loop tests.
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
    DiscoveredFact, ComplianceTaskEvidence
)
from app.services.control_engine import ControlEngine
from app.services.task_engine import TaskEngine
from app.services.task_execution_service import TaskExecutionService
from app.schemas.schemas import EvidenceCreate

class DummyUser:
    def __init__(self, full_name="Test User", role="Compliance Officer", org_id=""):
        self.full_name = full_name
        self.role = role
        self.organization_id = org_id
        self.id = "user-123"

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clean tables
    db.query(AuditLog).delete()
    db.query(ComplianceTaskEvidence).delete()
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
        db.close()

def setup_tenant(db: Session, name="Test Org"):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name=name, industry_sector="Tech")
    db.add(org)
    
    reg = Regulation(id=str(uuid.uuid4()), title="Test Reg", authority="Authority", publication_date=datetime.date.today(), sector="Tech", region="Global", content_text="Test")
    db.add(reg)
    
    ob = RegulatoryObligation(
        id=str(uuid.uuid4()),
        organization_id=org.id, regulation_id=reg.id, applicability_assessment_id="dummy",
        obligation_code="OB-01", title="Obligation", description="Desc",
        obligation_type="SECURITY_CONTROL", source_citation="Sec 1", status="ACTIVE", priority="HIGH"
    )
    db.add(ob)
    
    control = InternalControl(
        id=str(uuid.uuid4()), organization_id=org.id,
        control_code="CTRL-01", name="Access Control", description="desc",
        category="Security", owner_department="IT", status="IMPLEMENTED"
    )
    db.add(control)
    
    mapping = ObligationControlMapping(
        id=str(uuid.uuid4()),
        organization_id=org.id, obligation_id=ob.id, control_id=control.id,
        rationale="Test", mapping_source="MANUAL", created_by="Test"
    )
    db.add(mapping)
    db.commit()
    
    # Initial manual state to appease tests that assume task is REMEDIATION
    task = ComplianceTask(
        id=str(uuid.uuid4()), organization_id=org.id, regulation_id=reg.id,
        regulatory_obligation_id=ob.id, control_id=control.id,
        title="Fix Control", description="...", status="OPEN", task_type="REMEDIATION",
        assignee="system", reviewer="system"
    )
    db.add(task)
    db.commit()
    
    return org, control, task

# 1. Evidence submission for a control-linked task.
def test_evidence_submission_for_control_linked_task(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE")
    ev = TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    assert ev.id is not None
    assert ev.evidence_strength == "AUTHORITATIVE"

# 2. Evidence automatically receives task.control_id.
def test_evidence_receives_task_control_id(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf")
    ev = TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    assert ev.control_id == control.id

# 3. AUTHORITATIVE evidence can support EFFECTIVE control.
def test_authoritative_evidence_produces_effective(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED" # Wait, control_state is IMPLEMENTED, so it needs to be EFFECTIVE to be EFFECTIVE!
    
    # If control state is EFFECTIVE, AUTHORITATIVE makes it EFFECTIVE
    control.status = "EFFECTIVE"
    db_session.commit()
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "EFFECTIVE"

# 4. DOCUMENTED evidence does not automatically satisfy authoritative requirement.
def test_documented_evidence_insufficient_for_effective(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="DOCUMENTED")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED"
    assert assessment.evidence_summary == "EVIDENCE_PRESENT"

# 5. ATTESTED evidence remains insufficient.
def test_attested_evidence_insufficient(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="ATTESTED")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED"
    assert assessment.evidence_summary == "EVIDENCE_INSUFFICIENT"

# 6. INFERRED evidence remains insufficient.
def test_inferred_evidence_insufficient(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="INFERRED")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED"

# 7. UNKNOWN evidence remains insufficient.
def test_unknown_evidence_insufficient(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED"

# 8. Expired evidence is ignored.
def test_expired_evidence_ignored(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    past_date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE", valid_until=past_date)
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.evidence_summary == "NO_EVIDENCE"
    assert assessment.assessment_status == "CONTROL_REVIEW_REQUIRED"

# 9. Valid evidence is considered.
def test_valid_evidence_considered(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    future_date = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE", valid_until=future_date)
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    assessment = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).order_by(ControlAssessment.evaluated_at.desc()).first()
    assert assessment.evidence_summary == "EVIDENCE_AUTHORITATIVE"
    assert assessment.assessment_status == "EFFECTIVE"

# 10. Reassessment creates a new ControlAssessment when state changes.
# 11. Reassessment is idempotent when nothing materially changes.
# 12. Historical ControlAssessment remains unchanged.
def test_reassessment_creates_new_assessment_if_changed(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    # Initial evaluation
    ControlEngine.evaluate_control(control.id, org.id, db_session)
    count1 = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).count()
    
    # Second evaluation (idempotent)
    ControlEngine.evaluate_control(control.id, org.id, db_session)
    count2 = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).count()
    assert count1 == count2
    
    # Change state materially
    control.status = "EFFECTIVE"
    db_session.commit()
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    count3 = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).count()
    assert count3 > count2 # New assessment was created

# 13. Evidence remains preserved as provenance.
def test_evidence_preserved(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf")
    ev = TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    saved = db_session.query(ComplianceTaskEvidence).filter(ComplianceTaskEvidence.id == ev.id).first()
    assert saved.file_name == "test.pdf"

# 14. EFFECTIVE control supersedes open remediation task.
# 15. EFFECTIVE control does NOT mark remediation task COMPLETED automatically.
def test_effective_control_supersedes_not_completed(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    db_session.refresh(task)
    assert task.status == "SUPERSEDED" # NOT COMPLETED

# 16. CONTROL_GAP creates/remains associated with remediation task.
def test_control_gap_remains_open(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "DRAFT"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    db_session.refresh(task)
    assert task.status == "OPEN"

# 17. CONTROL_REVIEW_REQUIRED creates/remains associated with review task.
def test_control_review_required_creates_review_task(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "UNDER_REVIEW"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    review_task = db_session.query(ComplianceTask).filter(
        ComplianceTask.control_id == control.id,
        ComplianceTask.task_type == "REVIEW"
    ).first()
    assert review_task is not None
    assert review_task.status == "OPEN"

# 18. INEFFECTIVE control produces remediation requirement.
def test_ineffective_produces_remediation(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "INEFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    db_session.refresh(task)
    assert task.status == "OPEN"
    assert task.task_type == "REMEDIATION"

# 19. Multiple obligations sharing one control do not create duplicate tasks.
# Already covered by Phase 3, but evidence trigger shouldn't duplicate either.
def test_no_duplicate_tasks_on_evidence(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    tasks_after_first = db_session.query(ComplianceTask).filter(ComplianceTask.control_id == control.id).all()
    first_count = len(tasks_after_first)
    
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    tasks_after_second = db_session.query(ComplianceTask).filter(ComplianceTask.control_id == control.id).all()
    assert len(tasks_after_second) == first_count

# 20. Org A cannot submit evidence to Org B task.
def test_cross_tenant_evidence_submission_rejected(db_session):
    org_a, control_a, task_a = setup_tenant(db_session, "Org A")
    org_b, control_b, task_b = setup_tenant(db_session, "Org B")
    user_b = DummyUser(org_id=org_b.id)
    
    ev_in = EvidenceCreate(file_name="test.pdf")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        TaskExecutionService.add_evidence(task_a.id, ev_in, user_b, org_a, db_session)
    assert exc.value.status_code == 403

# 21. Org A cannot reassess Org B control.
def test_cross_tenant_reassess_rejected(db_session):
    # This is an API-level rule, but we test the service layer isolation if applicable.
    # ControlEngine.evaluate_control uses org_id filter, so it should return None if org_id mismatches.
    org_a, control_a, task_a = setup_tenant(db_session, "Org A")
    org_b = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org B", industry_sector="Tech")
    db_session.add(org_b)
    db_session.commit()
    
    assessment = ControlEngine.evaluate_control(control_a.id, org_b.id, db_session)
    assert assessment is None

# 22. Cross-tenant evidence cannot influence control assessment.
def test_cross_tenant_evidence_isolation(db_session):
    org_a, control_a, task_a = setup_tenant(db_session, "Org A")
    org_b = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org B", industry_sector="Tech")
    db_session.add(org_b)
    db_session.commit()
    
    # Force add evidence bypassing service layer to simulate bug
    ev = ComplianceTaskEvidence(
        task_id=task_a.id,
        organization_id=org_b.id, # Wrong org!
        control_id=control_a.id,
        uploaded_by="Hacker",
        uploader_role="Hacker",
        evidence_type="DOCUMENT",
        evidence_strength="AUTHORITATIVE",
        file_name="test.pdf"
    )
    db_session.add(ev)
    db_session.commit()
    
    control_a.status = "EFFECTIVE"
    db_session.commit()
    
    assessment = ControlEngine.evaluate_control(control_a.id, org_a.id, db_session)
    # Evidence is ignored because it belongs to Org B
    assert assessment.evidence_summary == "NO_EVIDENCE"

# 23. Duplicate evidence submission does not create duplicate ControlAssessments.
def test_duplicate_evidence_idempotent_assessment(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    count1 = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).count()
    
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    count2 = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control.id).count()
    assert count1 == count2

# 24. AuditLog is generated only for material assessment changes.
def test_audit_log_material_changes(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="UNKNOWN")
    
    count_before = db_session.query(AuditLog).filter(AuditLog.action == "CONTROL_EVALUATED").count()
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    count_after = db_session.query(AuditLog).filter(AuditLog.action == "CONTROL_EVALUATED").count()
    assert count_after > count_before
    
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    count_final = db_session.query(AuditLog).filter(AuditLog.action == "CONTROL_EVALUATED").count()
    assert count_final == count_after # No new audit log for idempotent eval

# 25. AuditLog preserves tenant organization_id.
def test_audit_log_tenant_isolation(db_session):
    org, control, task = setup_tenant(db_session)
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    logs = db_session.query(AuditLog).filter(AuditLog.organization_id == org.id).all()
    assert len(logs) > 0

# 26. Existing DiscoveredFact evidence remains supported.
def test_discovered_fact_evidence_supported(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    fact = DiscoveredFact(
        organization_id=org.id,
        fact_type="CONTROL_IMPLEMENTATION",
        fact_value=control.control_code,
        source_url="http://test.com",
        snippet="snippet",
        evidence_strength="AUTHORITATIVE"
    )
    db_session.add(fact)
    db_session.commit()
    
    assessment = ControlEngine.evaluate_control(control.id, org.id, db_session)
    assert assessment.evidence_summary == "EVIDENCE_AUTHORITATIVE"
    assert assessment.assessment_status == "EFFECTIVE"

# 27. Legacy evidence records remain readable.
def test_legacy_evidence_readable(db_session):
    org, control, task = setup_tenant(db_session)
    # Add legacy evidence without valid_until or control_id
    ev = ComplianceTaskEvidence(
        task_id=task.id,
        organization_id=org.id,
        uploaded_by="Legacy",
        uploader_role="Legacy",
        evidence_type="DOCUMENT",
        file_name="legacy.pdf"
    )
    db_session.add(ev)
    db_session.commit()
    
    # Should read fine and map as UNKNOWN strength
    from app.services.control_engine import ControlEngine
    summary, missing = ControlEngine._evaluate_evidence(control, db_session)
    assert summary == "EVIDENCE_INSUFFICIENT"

# 28. TaskEngine does not recreate a superseded remediation task unnecessarily.
def test_superseded_task_not_recreated(db_session):
    org, control, task = setup_tenant(db_session)
    control.status = "EFFECTIVE"
    db_session.commit()
    user = DummyUser(org_id=org.id)
    ev_in = EvidenceCreate(file_name="test.pdf", evidence_strength="AUTHORITATIVE")
    TaskExecutionService.add_evidence(task.id, ev_in, user, org, db_session)
    
    db_session.refresh(task)
    assert task.status == "SUPERSEDED"
    
    # Run generation again
    TaskEngine.generate_tasks(org.id, db_session)
    
    # Should not have created a new REMEDIATION task
    open_tasks = db_session.query(ComplianceTask).filter(
        ComplianceTask.control_id == control.id,
        ComplianceTask.status == "OPEN",
        ComplianceTask.task_type == "REMEDIATION"
    ).count()
    assert open_tasks == 0

