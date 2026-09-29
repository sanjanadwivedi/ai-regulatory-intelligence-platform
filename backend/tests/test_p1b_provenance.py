import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    InternalControl,
    ComplianceTask,
    ComplianceAlert,
    ObligationControlMapping
)
from app.core.security import get_current_user, get_current_organization

client = TestClient(app)

@pytest.fixture(scope="function")
def seed_data(db_session):
    # Create test data
    org1 = EnterpriseProfile(id="org1", organization_name="Tenant 1", industry_sector="Tech")
    org2 = EnterpriseProfile(id="org2", organization_name="Tenant 2", industry_sector="Finance")
    
    user1 = EnterpriseUser(id="user1", organization_id="org1", full_name="User 1", role="Admin")
    
    reg1 = Regulation(id="reg1", title="GDPR", authority="EU", publication_date=datetime.date(2016, 4, 27), sector="All", region="EU", content_text="Test", status="ACTIVE")
    
    app1 = RegulatoryApplicabilityAssessment(id="app1", organization_id="org1", regulation_id="reg1", rationale="Test", status="APPLICABLE")
    
    obl1 = RegulatoryObligation(id="obl1", organization_id="org1", regulation_id="reg1", applicability_assessment_id="app1", title="Data Protection", description="Test Description", status="ACTIVE", obligation_code="OBL-01", obligation_type="SECURITY", source_citation="Test")
    
    ctrl1 = InternalControl(id="ctrl1", organization_id="org1", control_code="CTRL-1", name="Access Control", description="Test", category="SECURITY", owner_department="IT")
    
    mapping1 = ObligationControlMapping(id="map1", organization_id="org1", obligation_id="obl1", control_id="ctrl1")
    
    task1 = ComplianceTask(id="task1", organization_id="org1", regulation_id="reg1", control_id="ctrl1", title="Review Access", description="Test", assignee="Admin", reviewer="Reviewer")
    
    alert1 = ComplianceAlert(id="alert1", organization_id="org1", alert_type="EVIDENCE_GAP", severity="HIGH", title="Test Alert", description="Test", source_entity_type="COMPLIANCE_TASK", source_entity_id="task1")
    
    # Cross tenant data
    task2 = ComplianceTask(id="task2", organization_id="org2", regulation_id="reg1", control_id="ctrl1", title="Tenant 2 Task", description="Test", assignee="Admin", reviewer="Reviewer")

    db_session.add_all([org1, org2, user1, reg1, app1, obl1, ctrl1, mapping1, task1, task2, alert1])
    db_session.commit()
    
    yield

@pytest.fixture(autouse=True)
def auth_overrides():
    def override_get_current_user():
        return EnterpriseUser(id="user1", organization_id="org1", full_name="User 1", role="Admin")

    def override_get_current_organization():
        return EnterpriseProfile(id="org1", organization_name="Tenant 1", industry_sector="Tech")

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_organization] = override_get_current_organization
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_organization, None)

def test_p1b_real_provenance_task(seed_data):
    response = client.get("/api/v1/provenance/TASK/task1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AVAILABLE"
    
    types = [n["type"] for n in data["nodes"]]
    assert "TASK" in types
    assert "CONTROL" in types
    assert "OBLIGATION" in types
    assert "APPLICABILITY" in types
    assert "REGULATION" in types
    
    # Ensure no fabricated mock data
    assert "CERT-In" not in str(data)

def test_p1b_real_provenance_alert(seed_data):
    response = client.get("/api/v1/provenance/ALERT/alert1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AVAILABLE"
    types = [n["type"] for n in data["nodes"]]
    assert "TASK" in types # Alert resolves to Task

def test_p1b_tenant_isolation_blocked(seed_data):
    # org1 trying to access org2's task
    response = client.get("/api/v1/provenance/TASK/task2")
    assert response.status_code == 200 # Returns 200 with UNAVAILABLE status per user request
    data = response.json()
    assert data["status"] == "UNAVAILABLE"
    assert data["nodes"] == []

def test_p1b_nonexistent_entity(seed_data):
    response = client.get("/api/v1/provenance/TASK/does_not_exist")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNAVAILABLE"
    assert data["nodes"] == []

def test_p1b_unsupported_entity(seed_data):
    response = client.get("/api/v1/provenance/INVALID/task1")
    assert response.status_code == 422
