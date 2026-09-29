import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.domain import (
    EnterpriseProfile, EnterpriseUser, ComplianceTask,
    InternalControl, RegulatoryObligation, Regulation
)
from app.core.security import create_access_token
from app.main import app
from app.core.database import Base, engine, SessionLocal

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

def test_cross_tenant_task_access_denied(client: TestClient, db_session: Session):
    # Create two distinct organizations
    org_a_id = str(uuid.uuid4())
    org_b_id = str(uuid.uuid4())
    org_a = EnterpriseProfile(id=org_a_id, organization_name="Org A", industry_sector="Tech", regulator_region="Global", discovery_status="CONFIRMED")
    org_b = EnterpriseProfile(id=org_b_id, organization_name="Org B", industry_sector="Tech", regulator_region="Global", discovery_status="CONFIRMED")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    # Create users for each organization
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())
    user_b_email = f"bob_{user_b_id}@orgb.com"
    user_a = EnterpriseUser(id=user_a_id, organization_id=org_a_id, full_name="Alice", email=f"alice_{user_a_id}@orga.com", hashed_password="pw", role="Compliance Officer")
    user_b = EnterpriseUser(id=user_b_id, organization_id=org_b_id, full_name="Bob", email=user_b_email, hashed_password="pw", role="Compliance Officer")
    db_session.add_all([user_a, user_b])
    db_session.commit()

    # Create a regulation and obligation (needed for task)
    from datetime import date
    reg_id = str(uuid.uuid4())
    reg = Regulation(
        id=reg_id, 
        title="Reg 1", 
        authority="AUTH", 
        sector="Tech", 
        region="Global",
        publication_date=date.today(),
        effective_date=date.today(),
        content_text="Sample text"
    )
    db_session.add(reg)
    db_session.commit()

    # Create a task owned by Org A
    task_a_id = str(uuid.uuid4())
    task_a = ComplianceTask(
        id=task_a_id,
        organization_id=org_a_id,
        regulation_id=reg_id,
        title="Org A Task",
        assignee="Alice",
        reviewer="Bob",
        status="NEEDS_REVIEW",
        due_date=date.today()
    )
    db_session.add(task_a)
    db_session.commit()

    # Generate token for User B
    token_b = create_access_token(subject=user_b_id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B attempts to fetch User A's task
    response = client.get(f"/api/v1/tasks/{task_a.id}", headers=headers_b)
    assert response.status_code in [403, 404]

    # User B attempts to update User A's task
    response = client.put(f"/api/v1/tasks/{task_a.id}", headers=headers_b, json={"title": "Hacked"})
    assert response.status_code in [403, 404]

def test_cross_tenant_control_access_denied(client: TestClient, db_session: Session):
    # Setup uses test data from previous or fresh if needed
    org_c_id = str(uuid.uuid4())
    org_d_id = str(uuid.uuid4())
    org_c = EnterpriseProfile(id=org_c_id, organization_name="Org C", industry_sector="Tech", regulator_region="Global", discovery_status="CONFIRMED")
    org_d = EnterpriseProfile(id=org_d_id, organization_name="Org D", industry_sector="Tech", regulator_region="Global", discovery_status="CONFIRMED")
    db_session.add_all([org_c, org_d])
    db_session.commit()

    user_c_id = str(uuid.uuid4())
    user_d_id = str(uuid.uuid4())
    user_d_email = f"bob2_{user_d_id}@orgb.com"
    user_c = EnterpriseUser(id=user_c_id, organization_id=org_c_id, full_name="Alice", email=f"alice2_{user_c_id}@orga.com", hashed_password="pw", role="Compliance Officer")
    user_d = EnterpriseUser(id=user_d_id, organization_id=org_d_id, full_name="Bob", email=user_d_email, hashed_password="pw", role="Compliance Officer")
    db_session.add_all([user_c, user_d])
    db_session.commit()
    
    # Generate token for User B
    token_b = create_access_token(subject=user_d_id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create a control owned by Org C
    control_c_id = str(uuid.uuid4())
    control_c = InternalControl(
        id=control_c_id,
        organization_id=org_c_id,
        control_code="CTRL-A",
        name="Org C Control",
        description="Desc",
        category="Access",
        owner_department="IT"
    )
    db_session.add(control_c)
    db_session.commit()

    # User B (Org D) attempts to fetch User A's (Org C) control
    response = client.get(f"/api/v1/controls/{control_c.id}", headers=headers_b)
    assert response.status_code in [403, 404]

    # User B attempts to patch User A's control
    response = client.patch(f"/api/v1/controls/{control_c.id}", headers=headers_b, json={"status": "IMPLEMENTED"})
    assert response.status_code in [403, 404]
