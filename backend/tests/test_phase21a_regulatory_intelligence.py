import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import get_db, Base
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseUser, EnterpriseProfile, Regulation, RegulatoryChange,
    DocumentVersion, RegulatoryApplicabilityAssessment, RegulatoryObligation,
    ComplianceTask, RegulatoryChangeTenantReview, AuditLog
)

client = TestClient(app)




@pytest.fixture
def setup_test_data(db_session):
    # Clear existing data first to prevent IntegrityError
    db_session.query(AuditLog).filter(AuditLog.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryChangeTenantReview).filter(RegulatoryChangeTenantReview.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(ComplianceTask).filter(ComplianceTask.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryChange).filter(RegulatoryChange.detected_by == "test_setup_intel").delete()
    db_session.query(DocumentVersion).filter(DocumentVersion.content_text.in_(["V1", "V2"])).delete()
    db_session.query(Regulation).filter(Regulation.title == "Test Regulation Intel").delete()
    db_session.query(EnterpriseUser).filter(EnterpriseUser.email.in_(["admin@orga.com", "admin@orgb.com"])).delete()
    db_session.query(EnterpriseProfile).filter(EnterpriseProfile.id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.commit()

    # Create two organizations
    org_a = EnterpriseProfile(organization_name="Org A - Intelligence", industry_sector="Healthcare", id="org_a_intel")
    org_b = EnterpriseProfile(organization_name="Org B - Intelligence", industry_sector="Finance", id="org_b_intel")
    
    # Create users
    user_a = EnterpriseUser(email="admin@orga.com", full_name="Admin A", role="ADMIN", organization_id=org_a.id)
    user_b = EnterpriseUser(email="admin@orgb.com", full_name="Admin B", role="ADMIN", organization_id=org_b.id)
    
    # Create Regulation and Versions
    reg = Regulation(
        title="Test Regulation Intel", 
        authority="US Gov", 
        publication_date=datetime.date.today(),
        sector="Healthcare",
        region="US",
        content_text="V1",
        status="ACTIVE", 
        source_url="http://test.reg"
    )
    db_session.add_all([org_a, org_b, user_a, user_b, reg])
    db_session.commit()
    
    v1 = DocumentVersion(regulation_id=reg.id, version_no=1, content_text="V1", content_hash="hash1")
    v2 = DocumentVersion(regulation_id=reg.id, version_no=2, content_text="V2", content_hash="hash2", previous_version_id=v1.id)
    db_session.add_all([v1, v2])
    db_session.commit()
    
    # Create Global RegulatoryChange
    change = RegulatoryChange(
        regulation_id=reg.id,
        previous_version_id=v1.id,
        new_version_id=v2.id,
        change_type="UPDATED",
        detected_by="test_setup_intel",
        content_hash_before="hash1",
        content_hash_after="hash2",
    )
    db_session.add(change)
    db_session.commit()
    
    # Org A applicability, obligation, task
    assessment_a = RegulatoryApplicabilityAssessment(organization_id=org_a.id, regulation_id=reg.id, status="APPLICABLE", rationale="Test A")
    db_session.add(assessment_a)
    db_session.commit()
    
    obligation_a = RegulatoryObligation(
        organization_id=org_a.id, 
        regulation_id=reg.id, 
        applicability_assessment_id=assessment_a.id, 
        obligation_type="SECURITY", 
        title="Test Req A",
        description="Test description",
        obligation_code="OBL-TEST-1",
        source_citation="Test citation"
    )
    db_session.add(obligation_a)
    db_session.commit()
    task_a = ComplianceTask(
        organization_id=org_a.id, 
        regulation_id=reg.id, 
        regulatory_obligation_id=obligation_a.id, 
        title="Task A", 
        status="TODO", 
        description="Test description",
        assignee="Test Assignee",
        reviewer="Test Reviewer"
    )
    db_session.add(task_a)
    db_session.commit()
    
    # Org B applicability
    assessment_b = RegulatoryApplicabilityAssessment(organization_id=org_b.id, regulation_id=reg.id, status="APPLICABLE", rationale="Test B")
    db_session.add(assessment_b)
    db_session.commit()
    
    yield {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": user_a,
        "user_b": user_b,
        "reg": reg,
        "change": change,
        "task_a": task_a
    }
    
    # Teardown
    db_session.query(AuditLog).filter(AuditLog.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryChangeTenantReview).filter(RegulatoryChangeTenantReview.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(ComplianceTask).filter(ComplianceTask.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.query(RegulatoryChange).filter(RegulatoryChange.detected_by == "test_setup_intel").delete()
    db_session.query(DocumentVersion).filter(DocumentVersion.content_text.in_(["V1", "V2"])).delete()
    db_session.query(Regulation).filter(Regulation.title == "Test Regulation Intel").delete()
    db_session.query(EnterpriseUser).filter(EnterpriseUser.email.in_(["admin@orga.com", "admin@orgb.com"])).delete()
    db_session.query(EnterpriseProfile).filter(EnterpriseProfile.id.in_(["org_a_intel", "org_b_intel"])).delete()
    db_session.commit()


def override_deps(user, org):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_organization] = lambda: org

def test_tenant_isolation_review(db_session, setup_test_data):
    org_a = setup_test_data["org_a"]
    user_a = setup_test_data["user_a"]
    org_b = setup_test_data["org_b"]
    user_b = setup_test_data["user_b"]
    change = setup_test_data["change"]
    
    # Initial State for Org A
    override_deps(user_a, org_a)
    res_a = client.get(f"/api/v1/regulatory-intelligence/changes/{change.id}")
    assert res_a.status_code == 200
    assert res_a.json()["review_status"] == "REQUIRES_REVIEW"
    assert len(res_a.json()["affected_assessments"]) == 1
    assert len(res_a.json()["affected_obligations"]) == 1
    assert len(res_a.json()["affected_tasks"]) == 1
    
    # Review by Org A
    res_review_a = client.post(f"/api/v1/regulatory-intelligence/changes/{change.id}/review", json={"decision": "ACKNOWLEDGE", "review_notes": "test review A"})
    assert res_review_a.status_code == 200
    assert res_review_a.json()["review_status"] == "REVIEWED"
    
    # Assert Review state is saved for Org A
    res_a = client.get(f"/api/v1/regulatory-intelligence/changes/{change.id}")
    assert res_a.json()["review_status"] == "REVIEWED"
    
    # State for Org B
    override_deps(user_b, org_b)
    res_b = client.get(f"/api/v1/regulatory-intelligence/changes/{change.id}")
    assert res_b.status_code == 200
    assert res_b.json()["review_status"] == "REQUIRES_REVIEW"
    assert len(res_b.json()["affected_assessments"]) == 1
    assert len(res_b.json()["affected_obligations"]) == 0
    assert len(res_b.json()["affected_tasks"]) == 0
    
    # Review by Org B
    res_review_b = client.post(f"/api/v1/regulatory-intelligence/changes/{change.id}/review", json={"decision": "RESOLVE", "review_notes": "test review B"})
    assert res_review_b.status_code == 200
    assert res_review_b.json()["review_status"] == "RESOLVED"
    
    # Assert Review state is saved for Org B
    res_b = client.get(f"/api/v1/regulatory-intelligence/changes/{change.id}")
    assert res_b.json()["review_status"] == "RESOLVED"
    
    # Check Audit Logs
    audit_a = db_session.query(AuditLog).filter(AuditLog.organization_id == org_a.id, AuditLog.target_id == change.id).first()
    assert audit_a is not None
    assert audit_a.action == "REGULATORY_CHANGE_REVIEW"
    assert audit_a.details["decision"] == "ACKNOWLEDGE"
    
    audit_b = db_session.query(AuditLog).filter(AuditLog.organization_id == org_b.id, AuditLog.target_id == change.id).first()
    assert audit_b is not None
    assert audit_b.action == "REGULATORY_CHANGE_REVIEW"
    assert audit_b.details["decision"] == "RESOLVE"
    
    # Idempotency
    res_review_b_idem = client.post(f"/api/v1/regulatory-intelligence/changes/{change.id}/review", json={"decision": "RESOLVE", "review_notes": "test review B duplicate"})
    assert res_review_b_idem.status_code == 200
    # ensure no duplicate audit log
    audit_logs_b = db_session.query(AuditLog).filter(AuditLog.organization_id == org_b.id, AuditLog.target_id == change.id).all()
    assert len(audit_logs_b) == 1
    
    app.dependency_overrides.clear()

def test_summary_and_feed_metrics(db_session, setup_test_data):
    org_a = setup_test_data["org_a"]
    user_a = setup_test_data["user_a"]
    org_b = setup_test_data["org_b"]
    user_b = setup_test_data["user_b"]
    change = setup_test_data["change"]
    
    # Reset review status for test
    db_session.query(RegulatoryChangeTenantReview).filter(RegulatoryChangeTenantReview.change_id == change.id).delete()
    db_session.query(AuditLog).filter(AuditLog.target_id == change.id).delete()
    db_session.commit()
    
    override_deps(user_a, org_a)
    res_summary_a = client.get("/api/v1/regulatory-intelligence/summary")
    assert res_summary_a.status_code == 200
    assert res_summary_a.json()["changes_requiring_review"] == 1
    assert res_summary_a.json()["affected_assessments"] == 1
    assert res_summary_a.json()["affected_obligations"] == 1
    assert res_summary_a.json()["affected_tasks"] == 1
    
    res_feed_a = client.get("/api/v1/regulatory-intelligence/changes")
    assert res_feed_a.status_code == 200
    assert res_feed_a.json()["total"] >= 1
    item_a = next(i for i in res_feed_a.json()["items"] if i["change_id"] == change.id)
    assert item_a["review_status"] == "REQUIRES_REVIEW"
    assert item_a["affected_obligation_count"] == 1
    
    override_deps(user_b, org_b)
    res_summary_b = client.get("/api/v1/regulatory-intelligence/summary")
    assert res_summary_b.status_code == 200
    assert res_summary_b.json()["changes_requiring_review"] == 1
    assert res_summary_b.json()["affected_assessments"] == 1
    assert res_summary_b.json()["affected_obligations"] == 0
    assert res_summary_b.json()["affected_tasks"] == 0
    
    res_feed_b = client.get("/api/v1/regulatory-intelligence/changes")
    assert res_feed_b.status_code == 200
    item_b = next(i for i in res_feed_b.json()["items"] if i["change_id"] == change.id)
    assert item_b["review_status"] == "REQUIRES_REVIEW"
    assert item_b["affected_obligation_count"] == 0
    
    app.dependency_overrides.clear()
