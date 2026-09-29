import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime
from jose import jwt
from passlib.context import CryptContext

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    RegulatoryObligation,
    ComplianceTask,
    DiscoveredFact,
    ComplianceAlert,
    AuditLog
)

# SQLite for isolated tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./pytest_test_only.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_token(user_id: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    to_encode = {"exp": expire, "sub": str(user_id)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.fixture
def setup_tenants(db_session):
    # Clean up
    db_session.query(EnterpriseUser).delete()
    db_session.query(EnterpriseProfile).delete()
    db_session.query(ComplianceAlert).delete()
    db_session.query(DiscoveredFact).delete()
    db_session.query(RegulatoryObligation).delete()
    db_session.query(ComplianceTask).delete()
    db_session.commit()

    # Tenant A
    org_a = EnterpriseProfile(id="org_a_id", organization_name="Tenant A", industry_sector="Finance")
    db_session.add(org_a)
    
    admin_a = EnterpriseUser(id="admin_a_id", organization_id="org_a_id", full_name="Admin A", role="Admin", email="admina@a.com")
    user_a = EnterpriseUser(id="user_a_id", organization_id="org_a_id", full_name="User A", role="Compliance Officer", email="usera@a.com")
    db_session.add_all([admin_a, user_a])

    # Tenant B
    org_b = EnterpriseProfile(id="org_b_id", organization_name="Tenant B", industry_sector="Health")
    db_session.add(org_b)
    
    admin_b = EnterpriseUser(id="admin_b_id", organization_id="org_b_id", full_name="Admin B", role="Admin", email="adminb@b.com")
    user_b = EnterpriseUser(id="user_b_id", organization_id="org_b_id", full_name="User B", role="Compliance Officer", email="userb@b.com")
    db_session.add_all([admin_b, user_b])

    db_session.commit()
    
    return {
        "org_a": org_a.id,
        "admin_a": admin_a.id,
        "user_a": user_a.id,
        "org_b": org_b.id,
        "admin_b": admin_b.id,
        "user_b": user_b.id,
        "token_admin_a": create_token(admin_a.id),
        "token_user_a": create_token(user_a.id),
        "token_admin_b": create_token(admin_b.id)
    }

# --- 1. User Management Tests ---

def test_unauthenticated_delete_rejected(setup_tenants):
    res = client.delete(f"/api/v1/enterprise/users/{setup_tenants['user_a']}")
    assert res.status_code == 401

def test_same_tenant_authorized_admin_delete_succeeds(setup_tenants):
    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    res = client.delete(f"/api/v1/enterprise/users/{setup_tenants['user_a']}", headers=headers)
    assert res.status_code == 200

def test_same_tenant_unauthorized_non_admin_delete_rejected(setup_tenants):
    # Need a new user for A since previous test deleted user_a
    db = TestingSessionLocal()
    new_user = EnterpriseUser(id="new_user_a", organization_id=setup_tenants["org_a"], full_name="New", role="USER", email="new@a.com")
    db.add(new_user)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {setup_tenants['token_user_a']}"} # COMPLIANCE_OFFICER (not ADMIN)
    res = client.delete("/api/v1/enterprise/users/new_user_a", headers=headers)
    assert res.status_code == 403

def test_cross_tenant_admin_delete_rejected(setup_tenants):
    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    # Admin A trying to delete User B
    res = client.delete(f"/api/v1/enterprise/users/{setup_tenants['user_b']}", headers=headers)
    assert res.status_code == 404 # Non-disclosing response

def test_tenant_a_cannot_list_tenant_b_users(setup_tenants):
    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    res = client.get("/api/v1/enterprise/users", headers=headers)
    assert res.status_code == 200
    users = res.json()
    for u in users:
        assert u["id"] in [setup_tenants["admin_a"], setup_tenants["user_a"], "new_user_a"]

def test_user_organization_cannot_be_changed(setup_tenants):
    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    # Create user attempts to inject organization_id for Tenant B
    payload = {"full_name": "Hack User", "role": "USER", "email": "hack@h.com", "organization_id": setup_tenants["org_b"]}
    res = client.post("/api/v1/enterprise/users", json=payload, headers=headers)
    assert res.status_code == 200
    # The organization_id should be overwritten with org_a
    db = TestingSessionLocal()
    user = db.query(EnterpriseUser).filter(EnterpriseUser.full_name == "Hack User").first()
    assert user.organization_id == setup_tenants["org_a"]
    db.close()


# --- 2. Obligations Tests ---

def test_tenant_a_can_access_own_obligation_but_not_b(setup_tenants, db_session):
    ob_a = RegulatoryObligation(id="ob_a", regulation_id="reg_1", organization_id=setup_tenants["org_a"], applicability_assessment_id="x", obligation_code="OA", title="OA", description="DA", obligation_type="REPORTING", source_citation="cit")
    ob_b = RegulatoryObligation(id="ob_b", regulation_id="reg_1", organization_id=setup_tenants["org_b"], applicability_assessment_id="x", obligation_code="OB", title="OB", description="DB", obligation_type="REPORTING", source_citation="cit")
    db_session.add_all([ob_a, ob_b])
    db_session.commit()

    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    # Can access A
    res = client.get("/api/v1/regulatory/obligations/ob_a", headers=headers)
    assert res.status_code == 200
    # Cannot access B
    res = client.get("/api/v1/regulatory/obligations/ob_b", headers=headers)
    assert res.status_code == 404


# --- 3. Analytics Tests ---

def test_analytics_excludes_cross_tenant_tasks(setup_tenants, db_session):
    t_a_open = ComplianceTask(id="ta1", regulation_id="r", organization_id=setup_tenants["org_a"], title="ta", assignee="u", reviewer="u", status="OPEN")
    t_a_closed = ComplianceTask(id="ta2", regulation_id="r", organization_id=setup_tenants["org_a"], title="ta", assignee="u", reviewer="u", status="COMPLETED")
    t_b_open = ComplianceTask(id="tb1", regulation_id="r", organization_id=setup_tenants["org_b"], title="tb", assignee="u", reviewer="u", status="OPEN")
    db_session.add_all([t_a_open, t_a_closed, t_b_open])
    db_session.commit()

    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["open_tasks"] == 1
    assert data["completed_tasks"] == 1


# --- 4. Discovery Tests ---

def test_discovery_fact_isolation(setup_tenants, db_session):
    f_a = DiscoveredFact(id="fa1", organization_id=setup_tenants["org_a"], fact_type="COMPANY", fact_value="Va", source_url="u", snippet="s", status="PENDING")
    f_b = DiscoveredFact(id="fb1", organization_id=setup_tenants["org_b"], fact_type="COMPANY", fact_value="Vb", source_url="u", snippet="s", status="PENDING")
    db_session.add_all([f_a, f_b])
    db_session.commit()

    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}
    
    # Status
    res = client.get("/api/v1/discovery/status", headers=headers)
    assert res.json()["pending_count"] == 1 # Only f_a
    
    # Edit cross-tenant
    res = client.put("/api/v1/discovery/facts/fb1/edit", json={"fact_value": "hack"}, headers=headers)
    assert res.status_code == 404

    # Confirm cross-tenant
    res = client.post("/api/v1/discovery/facts/fb1/confirm", headers=headers)
    assert res.status_code == 404

    # Bulk confirm
    res = client.post("/api/v1/discovery/facts/bulk-confirm", json={"min_confidence": 0.0}, headers=headers)
    
    db_session.refresh(f_a)
    db_session.refresh(f_b)
    assert f_a.status == "CONFIRMED"
    assert f_b.status == "PENDING" # Tenant B fact remains unchanged


# --- 5. Alerts Tests ---

def test_alerts_isolation(setup_tenants, db_session):
    al_a = ComplianceAlert(id="al_a", organization_id=setup_tenants["org_a"], alert_type="T", severity="HIGH", title="A", description="D", source_entity_type="T", source_entity_id="T")
    al_b = ComplianceAlert(id="al_b", organization_id=setup_tenants["org_b"], alert_type="T", severity="HIGH", title="B", description="D", source_entity_type="T", source_entity_id="T")
    db_session.add_all([al_a, al_b])
    db_session.commit()

    headers = {"Authorization": f"Bearer {setup_tenants['token_admin_a']}"}

    # Get A
    res = client.get("/api/v1/compliance/alerts/al_a", headers=headers)
    assert res.status_code == 200

    # Get B
    res = client.get("/api/v1/compliance/alerts/al_b", headers=headers)
    assert res.status_code == 404

    # Resolve B
    res = client.post("/api/v1/compliance/alerts/al_b/resolve", json={"resolution_notes": "hacked"}, headers=headers)
    assert res.status_code == 404
