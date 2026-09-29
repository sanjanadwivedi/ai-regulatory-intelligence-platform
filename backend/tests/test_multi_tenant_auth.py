import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.domain import EnterpriseProfile, EnterpriseUser, ComplianceTask
from app.core.security import get_current_user
import uuid

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def org_a(db_session: Session):
    org = db_session.query(EnterpriseProfile).filter_by(organization_name="Org A Auth Test").first()
    if not org:
        org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org A Auth Test", industry_sector="Tech")
        db_session.add(org)
        db_session.commit()
    return org

@pytest.fixture(scope="function")
def org_b(db_session: Session):
    org = db_session.query(EnterpriseProfile).filter_by(organization_name="Org B Auth Test").first()
    if not org:
        org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org B Auth Test", industry_sector="Tech")
        db_session.add(org)
        db_session.commit()
    return org

@pytest.fixture(scope="function")
def task_org_a(db_session: Session, org_a):
    task = db_session.query(ComplianceTask).filter_by(organization_id=org_a.id, title="Org A Task Auth").first()
    if not task:
        task = ComplianceTask(id=str(uuid.uuid4()), regulation_id="test-reg", organization_id=org_a.id, title="Org A Task Auth", assignee="tester", reviewer="tester", priority="LOW")
        db_session.add(task)
        db_session.commit()
    return task

def test_1_user_mapped_to_org_a_can_access_org_a_resources(client, db_session, org_a, task_org_a):
    user_a = EnterpriseUser(id="user_a", organization_id=org_a.id, full_name="User A", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_a
    
    response = client.get(f"/api/v1/tasks/{task_org_a.id}")
    assert response.status_code == 200
    app.dependency_overrides.clear()

def test_2_user_mapped_to_org_b_cannot_access_org_a_resources(client, db_session, org_b, task_org_a):
    user_b = EnterpriseUser(id="user_b", organization_id=org_b.id, full_name="User B", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_b
    
    response = client.get(f"/api/v1/tasks/{task_org_a.id}")
    assert response.status_code == 404
    app.dependency_overrides.clear()

def test_3_user_without_org_cannot_access_resources(client, db_session, task_org_a):
    user_no_org = EnterpriseUser(id="user_no_org", organization_id=None, full_name="User No Org", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_no_org
    
    response = client.get(f"/api/v1/tasks/{task_org_a.id}")
    assert response.status_code == 403  # get_current_organization fails closed with 403 when org_id is None
    app.dependency_overrides.clear()

def test_4_user_with_invalid_org_cannot_access_resources(client, db_session, task_org_a):
    user_invalid = EnterpriseUser(id="user_invalid", organization_id="invalid_org_id", full_name="User Invalid Org", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_invalid
    
    response = client.get(f"/api/v1/tasks/{task_org_a.id}")
    assert response.status_code == 403  # get_current_organization fails closed with 403 when org profile not found
    app.dependency_overrides.clear()

def test_5_sending_org_a_in_body_does_not_allow_user_b_to_access_org_a(client, db_session, org_a, org_b):
    user_b = EnterpriseUser(id="user_b", organization_id=org_b.id, full_name="User B", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_b
    
    payload = {
        "event_type": "INCIDENT_DETECTED",
        "event_timestamp": "2026-08-22T00:00:00Z",
        "source": "Test",
        "description": "Test",
        "organization_id": org_a.id
    }
    
    response = client.post("/api/v1/compliance/events", json=payload)
    # org_a spoofing in body is ignored — server uses user_b's own org from auth.
    # The event endpoint scopes to user_b's org, so org_a's events are not accessible.
    assert response.status_code in (403, 404)  # Either org context blocks it (403) or event not found (404)
    app.dependency_overrides.clear()
