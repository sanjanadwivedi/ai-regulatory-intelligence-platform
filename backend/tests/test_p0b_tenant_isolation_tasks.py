import pytest
import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    RegulatoryObligation,
    RegulatoryApplicabilityAssessment,
    InternalControl,
    ComplianceTask
)
from app.core.security import get_current_user, get_current_organization

client = TestClient(app)

@pytest.fixture(scope="function")
def p0b_seed_data(db_session):
    # Org A (Tenant A)
    org_a = EnterpriseProfile(id="org_a", organization_name="Tenant A", industry_sector="Tech")
    user_a = EnterpriseUser(id="user_a", organization_id="org_a", full_name="User A", role="Compliance Officer")
    
    # Org B (Tenant B)
    org_b = EnterpriseProfile(id="org_b", organization_name="Tenant B", industry_sector="Finance")
    user_b = EnterpriseUser(id="user_b", organization_id="org_b", full_name="User B", role="Compliance Officer")
    
    # Shared / Setup Data
    reg1 = Regulation(id="reg1", title="Test Reg", authority="Authority", publication_date=datetime.date(2020, 1, 1), sector="All", region="All", content_text="Test", status="ACTIVE")
    
    # Applicability Assessments
    app_a = RegulatoryApplicabilityAssessment(id="app_a", organization_id="org_a", regulation_id="reg1", status="APPLICABLE", rationale="Test")
    app_b = RegulatoryApplicabilityAssessment(id="app_b", organization_id="org_b", regulation_id="reg1", status="APPLICABLE", rationale="Test")

    # Org A Data
    obl_a = RegulatoryObligation(id="obl_a", organization_id="org_a", regulation_id="reg1", applicability_assessment_id="app_a", title="Obligation A", description="Desc A", status="ACTIVE", obligation_code="OBL-A", obligation_type="SECURITY", source_citation="Test")
    ctrl_a = InternalControl(id="ctrl_a", organization_id="org_a", control_code="CTRL-A", name="Control A", description="Desc", category="SECURITY", owner_department="IT")
    task_a = ComplianceTask(id="task_a", organization_id="org_a", regulation_id="reg1", title="Task A", assignee="Admin", reviewer="Reviewer", status="OPEN")
    
    # Org B Data
    obl_b = RegulatoryObligation(id="obl_b", organization_id="org_b", regulation_id="reg1", applicability_assessment_id="app_b", title="Obligation B", description="Desc B", status="ACTIVE", obligation_code="OBL-B", obligation_type="SECURITY", source_citation="Test")
    ctrl_b = InternalControl(id="ctrl_b", organization_id="org_b", control_code="CTRL-B", name="Control B", description="Desc", category="SECURITY", owner_department="IT")
    task_b = ComplianceTask(id="task_b", organization_id="org_b", regulation_id="reg1", title="Task B", assignee="Admin", reviewer="Reviewer", status="OPEN")

    db_session.add_all([org_a, org_b, user_a, user_b, reg1, app_a, app_b, obl_a, ctrl_a, task_a, obl_b, ctrl_b, task_b])
    db_session.commit()
    yield
    
@pytest.fixture(autouse=True)
def p0b_auth_overrides():
    def override_get_current_user():
        return EnterpriseUser(id="user_a", organization_id="org_a", full_name="User A", role="Compliance Officer")
    def override_get_current_organization():
        return EnterpriseProfile(id="org_a", organization_name="Tenant A", industry_sector="Tech")
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_organization] = override_get_current_organization
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_organization, None)

def test_p0b_cross_tenant_get_task(p0b_seed_data):
    # Org A tries to get Org B's task
    response = client.get("/api/v1/tasks/task_b")
    assert response.status_code == 404

def test_p0b_cross_tenant_update_task(p0b_seed_data):
    # Org A tries to update Org B's task
    response = client.patch("/api/v1/tasks/task_b", json={"title": "Hacked"})
    assert response.status_code == 404

def test_p0b_cross_tenant_create_task_with_foreign_org(p0b_seed_data):
    # Org A tries to create a task specifying Org B's organization_id
    response = client.post("/api/v1/tasks", json={
        "regulation_id": "reg1",
        "title": "Malicious Task",
        "assignee": "Admin",
        "reviewer": "Reviewer",
        "organization_id": "org_b"
    })
    # The application raises 403 when trying to specify a foreign organization_id
    assert response.status_code == 403

def test_p0b_cross_tenant_create_task_with_foreign_obligation(p0b_seed_data):
    # Org A tries to create a task specifying Org B's regulatory_obligation_id
    response = client.post("/api/v1/tasks", json={
        "regulation_id": "reg1",
        "regulatory_obligation_id": "obl_b",
        "title": "Malicious Task",
        "assignee": "Admin",
        "reviewer": "Reviewer"
    })
    assert response.status_code == 403

def test_p0b_cross_tenant_create_task_with_foreign_control(p0b_seed_data):
    # Org A tries to create a task specifying Org B's control_id
    response = client.post("/api/v1/tasks", json={
        "regulation_id": "reg1",
        "control_id": "ctrl_b",
        "title": "Malicious Task",
        "assignee": "Admin",
        "reviewer": "Reviewer"
    })
    assert response.status_code == 403

def test_p0b_cannot_update_organization_id(p0b_seed_data):
    # Org A tries to move its task to Org B via PATCH
    response = client.patch("/api/v1/tasks/task_a", json={"organization_id": "org_b"})
    # The organization_id is not in TaskUpdate, so it should be ignored or 422 if strict
    # In Pydantic v2 it might ignore extra fields or 422. We just ensure it doesn't change it.
    
    # We fetch it back to verify
    response2 = client.get("/api/v1/tasks/task_a")
    assert response2.status_code == 200
    assert response2.json()["organization_id"] == "org_a"
