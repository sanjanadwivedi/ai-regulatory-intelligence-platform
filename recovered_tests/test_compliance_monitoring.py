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
    ComplianceAlert,
    AuditLog
)
from app.services.compliance_posture_service import CompliancePostureService
from app.services.compliance_alert_service import ComplianceAlertService
from app.services.task_execution_service import TaskExecutionService
from app.schemas.schemas import EvidenceCreate, TriggerEventCreate
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
            full_name="Monitoring Officer",
            role="Compliance Officer",
            email="ciso@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def setup_org_profile(db_session: Session):
    # Ensure a dummy regulation exists
    reg = db_session.query(Regulation).filter(Regulation.id == "reg-certin").first()
    if not reg:
        reg = Regulation(
            id="reg-certin",
            title="CERT-In Cybersecurity Directions 2022",
            authority="CERT-In",
            region="India",
            sector="Information Technology",
            citation="No. 20(3)/2022-CERT-In"
        )
        db_session.add(reg)
        db_session.commit()

    # Clean previous run data
    db_session.query(ComplianceAlert).delete()
    db_session.query(ComplianceTaskActivity).delete()
    db_session.query(ComplianceTaskEvidence).delete()
    db_session.query(ComplianceTriggerEvent).delete()
    db_session.query(ComplianceTask).delete()
    db_session.query(RegulatoryObligation).delete()
    db_session.query(RegulatoryApplicabilityAssessment).delete()
    db_session.query(EnterpriseProfile).delete()
    db_session.commit()

    profile = EnterpriseProfile(
        organization_name="NEC India",
        industry_sector="Information Technology",
        country="India",
        discovery_status="CONFIRMED"
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile

# ==============================================================================
# TEST 1: HEALTHY POSTURE
# ==============================================================================
def test_healthy_posture(db_session: Session, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        applicability_score=1.0,
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-HEALTHY-01",
        title="Healthy Obligation",
        description="Healthy description",
        obligation_type="SECURITY_CONTROL",
        priority="MEDIUM",
        status="ACTIVE",
        source_citation="CERT-In Dir. 6(1)",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        regulatory_obligation_id=obl.id,
        control_code="OBL-HEALTHY-01",
        title="Healthy Task",
        description="Description",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="IN_PROGRESS",
        priority="MEDIUM",
        due_date=datetime.date.today() + datetime.timedelta(days=10)
    )
    db_session.add(task)
    db_session.commit()

    ev = ComplianceTaskEvidence(
        task_id=task.id,
        organization_id=profile.id,
        uploaded_by="Officer",
        uploader_role="Compliance Officer",
        evidence_type="LOG",
        file_name="health_check.log"
    )
    db_session.add(ev)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "HEALTHY"
    assert "All applicable regulations evaluated" in posture["posture_reasons"][0]

# ==============================================================================
# TEST 2: OVERDUE TASK CREATES CRITICAL ALERT
# ==============================================================================
def test_overdue_task_creates_critical_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Past Due Reporting",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        priority="HIGH",
        due_date=datetime.date.today() - datetime.timedelta(days=2)
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "CRITICAL"
    assert any("OVERDUE" in r for r in posture["posture_reasons"])

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    overdue_alert = next((a for a in alerts if a.alert_type == "OVERDUE_TASK"), None)
    assert overdue_alert is not None
    assert overdue_alert.severity == "CRITICAL"
    assert overdue_alert.task_id == task.id

# ==============================================================================
# TEST 3: BLOCKED CRITICAL TASK CREATES CRITICAL ALERT
# ==============================================================================
def test_blocked_critical_task_creates_critical_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Incident Notification System",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="BLOCKED",
        priority="CRITICAL"
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "CRITICAL"
    assert any("CRITICAL priority task(s) are BLOCKED" in r for r in posture["posture_reasons"])

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "CRITICAL_BLOCKED_TASK"), None)
    assert alert is not None
    assert alert.severity == "CRITICAL"

# ==============================================================================
# TEST 4: HIGH PRIORITY BLOCKED TASK CREATES ATTENTION ALERT
# ==============================================================================
def test_high_priority_blocked_task_creates_attention_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Key Management Policy",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="BLOCKED",
        priority="HIGH"
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "ATTENTION_REQUIRED"

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "HIGH_PRIORITY_BLOCKED_TASK"), None)
    assert alert is not None
    assert alert.severity == "HIGH"

# ==============================================================================
# TEST 5: REQUIRES REVIEW ASSESSMENT CREATES REVIEW ALERT
# ==============================================================================
def test_requires_review_assessment_creates_review_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="REQUIRES_REVIEW",
        rationale="Inconclusive data fiduciary classification",
        reason_summary="Inconclusive data fiduciary classification",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "REQUIRES_REVIEW"
    assert any("require legal review" in r for r in posture["posture_reasons"])

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "REVIEW_REQUIRED"), None)
    assert alert is not None
    assert alert.source_entity_id == assess.id

# ==============================================================================
# TEST 6: MISSING TRIGGER METADATA CREATES REVIEW ALERT
# ==============================================================================
def test_missing_trigger_metadata_creates_review_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Ad-hoc Breach Response",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        priority="MEDIUM",
        trigger_type="DATA_BREACH_IDENTIFIED",
        trigger_offset_value=None,  # Missing offset!
        trigger_offset_unit=None
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["posture_status"] == "REQUIRES_REVIEW"

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "MISSING_TRIGGER_METADATA"), None)
    assert alert is not None

# ==============================================================================
# TEST 7: CONTINUOUS TASK IS NEVER OVERDUE
# ==============================================================================
def test_continuous_task_is_never_overdue(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="180-Day System Log Retention",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="IN_PROGRESS",
        priority="HIGH",
        frequency="CONTINUOUS",
        due_date=None
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["operational_summary"]["overdue_count"] == 0
    assert posture["operational_summary"]["continuous_count"] == 1

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    assert not any(a.alert_type == "OVERDUE_TASK" and a.task_id == task.id for a in alerts)

# ==============================================================================
# TEST 8: COMPLETED TASK IS NOT COMPLIANCE CLAIM
# ==============================================================================
def test_completed_task_is_not_compliance_claim(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-TEST-08",
        title="Test Obligation",
        description="Desc",
        obligation_type="RECORD_KEEPING",
        status="ACTIVE",
        source_citation="Sec 70B",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        regulatory_obligation_id=obl.id,
        title="Operational Log Archival",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="IN_PROGRESS"
    )
    db_session.add(task)
    db_session.commit()

    # Complete the task
    TaskExecutionService.complete_task(task.id, compliance_officer_user, db_session)
    db_session.refresh(task)
    assert task.status == "COMPLETED"

    # Upstream obligation remains unchanged
    db_session.refresh(obl)
    assert obl.status == "ACTIVE"

# ==============================================================================
# TEST 9: COMPLETED WITHOUT EVIDENCE CREATES EVIDENCE ALERT
# ==============================================================================
def test_completed_without_evidence_creates_evidence_alert(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Quick Completed Action",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="COMPLETED"
    )
    db_session.add(task)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["evidence_summary"]["completed_without_evidence_count"] == 1

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "COMPLETED_WITHOUT_EVIDENCE"), None)
    assert alert is not None
    assert alert.task_id == task.id

# ==============================================================================
# TEST 10: ACTIVE OBLIGATION WITHOUT TASK CREATES ORPHAN ALERT
# ==============================================================================
def test_active_obligation_without_task_creates_orphan_alert(db_session: Session, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-ORPHAN-10",
        title="Orphan Obligation",
        description="Desc",
        obligation_type="SECURITY_CONTROL",
        status="ACTIVE",
        source_citation="Sec 70B",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    alert = next((a for a in alerts if a.alert_type == "ORPHANED_ACTIVE_OBLIGATION"), None)
    assert alert is not None
    assert alert.obligation_id == obl.id

# ==============================================================================
# TEST 11: ACTIVE OBLIGATION WITH EVIDENCE HAS NO EVIDENCE GAP
# ==============================================================================
def test_active_obligation_with_evidence_has_no_evidence_gap(db_session: Session, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-COVERED-11",
        title="Covered Obligation",
        description="Desc",
        obligation_type="SECURITY_CONTROL",
        status="ACTIVE",
        source_citation="Sec 70B",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        regulatory_obligation_id=obl.id,
        title="Covered Task",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="IN_PROGRESS"
    )
    db_session.add(task)
    db_session.commit()

    ev = ComplianceTaskEvidence(
        task_id=task.id,
        organization_id=profile.id,
        uploaded_by="Tester",
        uploader_role="Compliance Officer",
        evidence_type="REPORT",
        file_name="soc_audit_report.pdf"
    )
    db_session.add(ev)
    db_session.commit()

    posture = CompliancePostureService.calculate_posture(profile.id, db_session)
    assert posture["evidence_summary"]["obligations_with_evidence"] == 1
    assert posture["evidence_summary"]["obligations_without_evidence"] == 0

    alerts = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    assert not any(a.alert_type == "EVIDENCE_GAP" and a.obligation_id == obl.id for a in alerts)

# ==============================================================================
# TEST 12: ALERT GENERATION IS IDEMPOTENT
# ==============================================================================
def test_alert_generation_is_idempotent(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Overdue Control",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        due_date=datetime.date.today() - datetime.timedelta(days=1)
    )
    db_session.add(task)
    db_session.commit()

    alerts_1 = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    count_1 = len(alerts_1)

    alerts_2 = ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db_session)
    count_2 = len(alerts_2)

    assert count_1 == count_2
    total_db_alerts = db_session.query(ComplianceAlert).filter(ComplianceAlert.organization_id == profile.id).count()
    assert total_db_alerts == count_1

# ==============================================================================
# TEST 13: ALERT RESOLUTION IS IDEMPOTENT
# ==============================================================================
def test_alert_resolution_is_idempotent(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="OVERDUE_TASK",
        severity="CRITICAL",
        title="Alert to Resolve",
        description="Desc",
        source_entity_type="COMPLIANCE_TASK",
        source_entity_id="task-13",
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    resolved_1 = ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Mitigated with SOC team", db_session)
    assert resolved_1.status == "RESOLVED"

    # Second resolution is safe no-op
    resolved_2 = ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Duplicate note", db_session)
    assert resolved_2.status == "RESOLVED"

# ==============================================================================
# TEST 14: ALERT RESOLUTION DOES NOT MODIFY OBLIGATION
# ==============================================================================
def test_alert_resolution_does_not_modify_obligation(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-14",
        title="Unchanged Obligation",
        description="Desc",
        obligation_type="SECURITY_CONTROL",
        status="ACTIVE",
        source_citation="Sec 70B",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="EVIDENCE_GAP",
        severity="HIGH",
        title="Evidence Alert",
        description="Desc",
        source_entity_type="REGULATORY_OBLIGATION",
        source_entity_id=obl.id,
        obligation_id=obl.id,
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Resolved offline", db_session)
    db_session.refresh(obl)
    assert obl.status == "ACTIVE"
    assert obl.obligation_code == "OBL-14"

# ==============================================================================
# TEST 15: ALERT RESOLUTION DOES NOT MODIFY APPLICABILITY
# ==============================================================================
def test_alert_resolution_does_not_modify_applicability(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="REQUIRES_REVIEW",
        rationale="Initial rationale",
        reason_summary="Initial summary",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="REVIEW_REQUIRED",
        severity="MEDIUM",
        title="Review Alert",
        description="Desc",
        source_entity_type="REGULATORY_APPLICABILITY_ASSESSMENT",
        source_entity_id=assess.id,
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Acknowledged review", db_session)
    db_session.refresh(assess)
    assert assess.status == "REQUIRES_REVIEW"
    assert assess.rationale == "Initial rationale"

# ==============================================================================
# TEST 16: ALERT RESOLUTION DOES NOT MODIFY REGULATION
# ==============================================================================
def test_alert_resolution_does_not_modify_regulation(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    reg = db_session.query(Regulation).first()
    title_before = reg.title

    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="REVIEW_REQUIRED",
        severity="MEDIUM",
        title="Reg Alert",
        description="Desc",
        source_entity_type="REGULATION",
        source_entity_id=reg.id,
        regulation_id=reg.id,
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Reg note", db_session)
    db_session.refresh(reg)
    assert reg.title == title_before

# ==============================================================================
# TEST 17: ORGANIZATION ISOLATION
# ==============================================================================
def test_organization_isolation(db_session: Session, setup_org_profile):
    profile_a = setup_org_profile
    profile_b = EnterpriseProfile(organization_name="Org B Corp", industry_sector="Finance", country="USA")
    db_session.add(profile_b)
    db_session.commit()

    # Create task on Org A
    task_a = ComplianceTask(
        organization_id=profile_a.id,
        regulation_id="reg-certin",
        title="Task A",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="BLOCKED",
        priority="CRITICAL"
    )
    db_session.add(task_a)
    db_session.commit()

    alerts_a = ComplianceAlertService.evaluate_and_sync_alerts(profile_a.id, db_session)
    alerts_b = ComplianceAlertService.evaluate_and_sync_alerts(profile_b.id, db_session)

    assert len(alerts_a) > 0
    assert len(alerts_b) == 0

# ==============================================================================
# TEST 18: CROSS ORG ALERT ACCESS DENIED
# ==============================================================================
def test_cross_org_alert_access_denied(db_session: Session, setup_org_profile):
    profile_a = setup_org_profile
    alert_a = ComplianceAlert(
        organization_id=profile_a.id,
        alert_type="OVERDUE_TASK",
        severity="CRITICAL",
        title="Org A Alert",
        description="Desc",
        source_entity_type="COMPLIANCE_TASK",
        source_entity_id="task-a",
        status="ACTIVE"
    )
    db_session.add(alert_a)
    db_session.commit()

    foreign_user = EnterpriseUser(full_name="Foreign Officer", role="Compliance Officer")
    setattr(foreign_user, "organization_id", "org-foreign-999")

    with pytest.raises(HTTPException) as exc_info:
        ComplianceAlertService.resolve_alert(alert_a.id, foreign_user, "Unauthorized resolve", db_session)
    assert exc_info.value.status_code == 403

# ==============================================================================
# TEST 19: CROSS ORG POSTURE ACCESS DENIED
# ==============================================================================
def test_cross_org_posture_access_denied(db_session: Session, setup_org_profile):
    profile_a = setup_org_profile
    foreign_user = EnterpriseUser(full_name="Foreign Officer", role="Compliance Officer")
    setattr(foreign_user, "organization_id", "org-foreign-999")

    from app.services.task_execution_service import _verify_organization_access
    with pytest.raises(HTTPException) as exc_info:
        _verify_organization_access(foreign_user, profile_a.id)
    assert exc_info.value.status_code == 403

# ==============================================================================
# TEST 20: UNAUTHORIZED ALERT RESOLUTION DENIED
# ==============================================================================
def test_unauthorized_alert_resolution_denied(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="OVERDUE_TASK",
        severity="CRITICAL",
        title="Org Alert",
        description="Desc",
        source_entity_type="COMPLIANCE_TASK",
        source_entity_id="task-20",
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    guest_user = EnterpriseUser(full_name="Guest User", role="Guest")
    with pytest.raises(HTTPException) as exc_info:
        ComplianceAlertService.resolve_alert(alert.id, guest_user, "Guest attempt", db_session)
    assert exc_info.value.status_code == 403

# ==============================================================================
# TEST 21: POSTURE REASONS ARE DETERMINISTIC
# ==============================================================================
def test_posture_reasons_are_deterministic(db_session: Session, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Overdue Task",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        due_date=datetime.date.today() - datetime.timedelta(days=1)
    )
    db_session.add(task)
    db_session.commit()

    posture_1 = CompliancePostureService.calculate_posture(profile.id, db_session)
    posture_2 = CompliancePostureService.calculate_posture(profile.id, db_session)

    assert posture_1["posture_status"] == posture_2["posture_status"]
    assert posture_1["posture_reasons"] == posture_2["posture_reasons"]

# ==============================================================================
# TEST 22: DUE DATE ONLY USES STRUCTURED TRIGGER
# ==============================================================================
def test_due_date_only_uses_structured_trigger(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile

    assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id="reg-certin",
        status="APPLICABLE",
        rationale="Entity operates ICT systems in India",
        engine_version="v2.0"
    )
    db_session.add(assess)
    db_session.commit()

    obl = RegulatoryObligation(
        organization_id=profile.id,
        regulation_id="reg-certin",
        applicability_assessment_id=assess.id,
        obligation_code="OBL-22",
        title="Incident 6H Notice",
        description="Desc",
        obligation_type="REPORTING",
        status="ACTIVE",
        source_citation="CERT-In Dir. 6",
        engine_version="v2.0"
    )
    db_session.add(obl)
    db_session.commit()

    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        regulatory_obligation_id=obl.id,
        title="Incident Task",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        trigger_type="INCIDENT_DETECTED",
        trigger_offset_value=6,
        trigger_offset_unit="HOURS",
        due_rule="Mandatory notice within 6 hours"
    )
    db_session.add(task)
    db_session.commit()

    event_ts = datetime.datetime(2026, 8, 13, 10, 0, 0)
    event_in = TriggerEventCreate(
        organization_id=profile.id,
        event_type="INCIDENT_DETECTED",
        event_timestamp=event_ts,
        source="SOC SIEM",
        description="Incident Alert"
    )
    _, affected = TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)
    assert len(affected) == 1
    # 10:00 + 6 hours = 16:00 on 2026-08-13
    assert affected[0].due_date == datetime.date(2026, 8, 13)

# ==============================================================================
# TEST 23: NO NATURAL LANGUAGE DEADLINE PARSING
# ==============================================================================
def test_no_natural_language_deadline_parsing(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    # Even if due_rule contains text like "Within 24 hours", without structured offset it remains due_date = None
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Text-only due rule task",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="OPEN",
        trigger_type="REGULATORY_NOTIFICATION_RECEIVED",
        trigger_offset_value=None,  # No machine offset
        trigger_offset_unit=None,
        due_rule="Within 24 hours of notification"
    )
    db_session.add(task)
    db_session.commit()

    event_in = TriggerEventCreate(
        organization_id=profile.id,
        event_type="REGULATORY_NOTIFICATION_RECEIVED",
        event_timestamp=datetime.datetime.utcnow(),
        source="Notice",
        description="Notice desc"
    )
    _, affected = TaskExecutionService.process_trigger_event(event_in, compliance_officer_user, db_session)
    assert len(affected) == 1
    assert affected[0].due_date is None  # Safe uncertainty enforced!

# ==============================================================================
# TEST 24: EVIDENCE LAYERS REMAIN SEGREGATED
# ==============================================================================
def test_evidence_layers_remain_segregated(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    task = ComplianceTask(
        organization_id=profile.id,
        regulation_id="reg-certin",
        title="Audit Log Task",
        assignee="Compliance Officer",
        reviewer="Legal Counsel",
        status="IN_PROGRESS"
    )
    db_session.add(task)
    db_session.commit()

    ev = TaskExecutionService.add_evidence(
        task.id,
        EvidenceCreate(file_name="operational_run.log", evidence_type="LOG"),
        compliance_officer_user,
        db_session
    )
    assert isinstance(ev, ComplianceTaskEvidence)
    # Operational evidence has task_id and does NOT modify regulations
    assert ev.task_id == task.id

# ==============================================================================
# TEST 25: AUDIT LOG CREATED ON ALERT RESOLUTION
# ==============================================================================
def test_audit_log_created_on_alert_resolution(db_session: Session, compliance_officer_user, setup_org_profile):
    profile = setup_org_profile
    alert = ComplianceAlert(
        organization_id=profile.id,
        alert_type="COMPLETED_WITHOUT_EVIDENCE",
        severity="MEDIUM",
        title="Evidence Alert",
        description="Desc",
        source_entity_type="COMPLIANCE_TASK",
        source_entity_id="task-25",
        status="ACTIVE"
    )
    db_session.add(alert)
    db_session.commit()

    ComplianceAlertService.resolve_alert(alert.id, compliance_officer_user, "Audited and verified manually", db_session)

    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.action == "COMPLIANCE_ALERT_RESOLVED",
        AuditLog.target_id == alert.id
    ).first()
    assert audit_entry is not None
    assert audit_entry.user_name == compliance_officer_user.full_name
    assert audit_entry.details["new_status"] == "RESOLVED"
