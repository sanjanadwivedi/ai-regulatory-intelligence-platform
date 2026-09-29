import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine, get_db
from app.models.domain import EnterpriseProfile, EnterpriseUser, ComplianceTask, RegulatoryObligation, InternalControl, Regulation
from app.core.security import get_password_hash
import uuid

client = TestClient(app)

def setup_module(module):
    Base.metadata.create_all(bind=engine)

def teardown_module(module):
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    db = next(get_db())
    yield db
    db.close()

@pytest.fixture(scope="function")
def setup_data(db_session):
    # Create two tenants
    org1 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Tenant A", industry_sector="Finance")
    org2 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Tenant B", industry_sector="Health")
    db_session.add(org1)
    db_session.add(org2)
    db_session.commit()

    # Create users
    user1 = EnterpriseUser(id=str(uuid.uuid4()), organization_id=org1.id, full_name="User A", role="Compliance Officer", email="a@tenanta.com", hashed_password=get_password_hash("test"))
    user2 = EnterpriseUser(id=str(uuid.uuid4()), organization_id=org2.id, full_name="User B", role="Compliance Officer", email="b@tenantb.com", hashed_password=get_password_hash("test"))
    
    # Global/admin user without org
    user_global = EnterpriseUser(id=str(uuid.uuid4()), full_name="Admin", role="Admin", email="admin@global.com", hashed_password=get_password_hash("test"))
    
    db_session.add_all([user1, user2, user_global])
    db_session.commit()

    import datetime
    # Create dummy regulation
    reg = Regulation(id=str(uuid.uuid4()), title="Test Reg", authority="Authority", publication_date=datetime.date(2026, 1, 1), sector="Finance", region="US", content_text="Text")
    db_session.add(reg)
    db_session.commit()

    # Create obligations
    ob1 = RegulatoryObligation(id=str(uuid.uuid4()), organization_id=org1.id, regulation_id=reg.id, applicability_assessment_id="dummy", obligation_code="OB-A", title="Title", description="Desc", obligation_type="OTHER", source_citation="Cit")
    ob2 = RegulatoryObligation(id=str(uuid.uuid4()), organization_id=org2.id, regulation_id=reg.id, applicability_assessment_id="dummy", obligation_code="OB-B", title="Title", description="Desc", obligation_type="OTHER", source_citation="Cit")
    db_session.add_all([ob1, ob2])
    db_session.commit()

    # Create controls
    ctrl1 = InternalControl(id=str(uuid.uuid4()), organization_id=org1.id, control_code="CTRL-A", name="Name", description="Desc", category="Cat", owner_department="Dept")
    ctrl2 = InternalControl(id=str(uuid.uuid4()), organization_id=org2.id, control_code="CTRL-B", name="Name", description="Desc", category="Cat", owner_department="Dept")
    db_session.add_all([ctrl1, ctrl2])
    db_session.commit()
    

    # Create valid task for Tenant A
    task1 = ComplianceTask(id=str(uuid.uuid4()), organization_id=org1.id, regulation_id=reg.id, title="Tenant A Task", assignee="User A", reviewer="Reviewer A")
    db_session.add(task1)
    
    # Extract data before commit to avoid expiration/detachment issues
    data = {
        "org1_id": org1.id, "org2_id": org2.id,
        "user1_email": user1.email, "user2_email": user2.email, "user_global_email": user_global.email,
        "reg_id": reg.id,
        "ob1_id": ob1.id, "ob2_id": ob2.id,
        "ctrl1_id": ctrl1.id, "ctrl2_id": ctrl2.id,
        "task1_id": task1.id
    }
    db_session.commit()
    return data


def get_token_headers(user_email: str):
    response = client.post("/api/v1/auth/login", json={"email": user_email, "password": "test"})
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_1_authenticated_tenant_assigned(setup_data):
    headers = get_token_headers(setup_data["user1_email"])
    response = client.post("/api/v1/tasks", headers=headers, json={
        "regulation_id": setup_data["reg_id"],
        "title": "New Task",
        "assignee": "User A",
        "reviewer": "Reviewer"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == setup_data["org1_id"]

def test_2_global_task_creation_fails(setup_data):
    headers = get_token_headers(setup_data["user_global_email"])
    # Admin has no organization_id
    response = client.post("/api/v1/tasks", headers=headers, json={
        "regulation_id": setup_data["reg_id"],
        "title": "Global Task",
        "assignee": "Admin",
        "reviewer": "Admin"
    })
    # get_current_organization explicitly throws 403 if no org mapped
    assert response.status_code == 403

def test_3_foreign_organization_assignment_fails(setup_data):
    headers = get_token_headers(setup_data["user1_email"])
    # User 1 belongs to org1. Tries to create task for org2
    response = client.post("/api/v1/tasks", headers=headers, json={
        "organization_id": setup_data["org2_id"],
        "regulation_id": setup_data["reg_id"],
        "title": "Sneaky Task",
        "assignee": "User A",
        "reviewer": "Reviewer"
    })
    # Our fix should reject foreign organization_id
    assert response.status_code == 403
    assert "foreign" in response.json()["detail"].lower()

def test_4_foreign_obligation_reference_fails(setup_data):
    headers = get_token_headers(setup_data["user1_email"])
    response = client.post("/api/v1/tasks", headers=headers, json={
        "regulation_id": setup_data["reg_id"],
        "regulatory_obligation_id": setup_data["ob2_id"], # belongs to org2
        "title": "Task",
        "assignee": "User",
        "reviewer": "Rev"
    })
    assert response.status_code == 403

def test_5_foreign_control_reference_fails(setup_data):
    headers = get_token_headers(setup_data["user1_email"])
    response = client.post("/api/v1/tasks", headers=headers, json={
        "regulation_id": setup_data["reg_id"],
        "control_id": setup_data["ctrl2_id"], # belongs to org2
        "title": "Task",
        "assignee": "User",
        "reviewer": "Rev"
    })
    assert response.status_code == 403

def test_6_task_list_is_tenant_scoped(setup_data):
    headers1 = get_token_headers(setup_data["user1_email"])
    resp1 = client.get("/api/v1/tasks", headers=headers1)
    assert resp1.status_code == 200
    
    headers2 = get_token_headers(setup_data["user2_email"])
    resp2 = client.get("/api/v1/tasks", headers=headers2)
    assert resp2.status_code == 200
    
    tasks1 = resp1.json()
    tasks2 = resp2.json()
    
    # task1 belongs to org1
    assert any(t["id"] == setup_data["task1_id"] for t in tasks1)
    assert not any(t["id"] == setup_data["task1_id"] for t in tasks2)

def test_7_cross_tenant_uuid_does_not_reveal_existence(setup_data):
    headers2 = get_token_headers(setup_data["user2_email"])
    # User 2 tries to GET User 1's task
    response = client.get(f"/api/v1/tasks/{setup_data['task1_id']}", headers=headers2)
    assert response.status_code == 404 # Should NOT be 403 IDOR existence leak

def test_8_cross_tenant_update_fails(setup_data):
    headers2 = get_token_headers(setup_data["user2_email"])
    response = client.patch(f"/api/v1/tasks/{setup_data['task1_id']}", headers=headers2, json={"title": "Hacked"})
    assert response.status_code == 404

def test_9_cross_tenant_completion_fails(setup_data):
    headers2 = get_token_headers(setup_data["user2_email"])
    response = client.post(f"/api/v1/tasks/{setup_data['task1_id']}/complete", headers=headers2, json={"confirmation_notes": "Done"})
    assert response.status_code == 404

def test_10_cross_tenant_reopen_fails(setup_data):
    headers2 = get_token_headers(setup_data["user2_email"])
    response = client.post(f"/api/v1/tasks/{setup_data['task1_id']}/reopen", headers=headers2, json={"reopen_reason": "Because"})
    assert response.status_code == 404

def test_11_cross_tenant_assign_fails(setup_data):
    headers2 = get_token_headers(setup_data["user2_email"])
    response = client.post(f"/api/v1/tasks/{setup_data['task1_id']}/assign", headers=headers2, json={"assignee": "Me"})
    assert response.status_code == 404

def test_12_global_task_is_impossible(db_session, setup_data):
    # Testing at the DB model level. We enforced nullable=False on organization_id
    import sqlalchemy.exc
    try:
        t = ComplianceTask(id=str(uuid.uuid4()), regulation_id=setup_data["reg_id"], title="Global", assignee="A", reviewer="B")
        db_session.add(t)
        db_session.commit()
        assert False, "Should have raised IntegrityError due to NOT NULL constraint"
    except sqlalchemy.exc.IntegrityError:
        db_session.rollback()
        assert True

def test_13_taskengine_preserves_tenant_id(setup_data, db_session):
    from app.services.task_engine import TaskEngine
    # The obligation is ob1 (org1)
    # Ensure generating tasks for org1 creates tasks scoped to org1
    tasks = TaskEngine.generate_tasks(organization_id=setup_data["org1_id"], db=db_session)
    for t in tasks:
        assert t.organization_id == setup_data["org1_id"]

def test_14_new_tasks_always_have_non_null_org_id(setup_data):
    headers = get_token_headers(setup_data["user1_email"])
    response = client.post("/api/v1/tasks", headers=headers, json={
        "regulation_id": setup_data["reg_id"],
        "title": "New Task Test",
        "assignee": "User A",
        "reviewer": "Reviewer"
    })
    assert response.status_code == 200
    assert response.json()["organization_id"] is not None

def test_15_no_task_creation_trusts_untrusted_tenant_id(setup_data):
    # This overlaps with test_3, explicitly verifying the tenant scope ignores/rejects foreign
    headers = get_token_headers(setup_data["user1_email"])
    response = client.post("/api/v1/tasks", headers=headers, json={
        "organization_id": "some-hacked-uuid",
        "regulation_id": setup_data["reg_id"],
        "title": "Task",
        "assignee": "User A",
        "reviewer": "Reviewer"
    })
    assert response.status_code == 403

def test_16_valid_existing_tenant_tasks_remain_accessible(setup_data):
    headers1 = get_token_headers(setup_data["user1_email"])
    response = client.get(f"/api/v1/tasks/{setup_data['task1_id']}", headers=headers1)
    assert response.status_code == 200
    assert response.json()["id"] == setup_data["task1_id"]
