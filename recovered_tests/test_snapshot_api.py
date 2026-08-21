import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models.domain import EnterpriseUser, EnterpriseProfile
from app.core.security import create_access_token

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_headers(db: Session, email: str, role: str) -> dict:
    user = db.query(EnterpriseUser).filter(EnterpriseUser.email == email).first()
    if not user:
        org = db.query(EnterpriseProfile).first()
        org_id = org.id if org else "test-org-id"
        user = EnterpriseUser(
            id=f"user-{email}",
            email=email,
            hashed_password="fake",
            role=role,
            organization_id=org_id
        )
        db.add(user)
        db.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}

def test_generate_snapshot_admin(db_session: Session):
    headers = get_auth_headers(db_session, "admin_test@aegis.com", "ADMIN")
    resp = client.post("/api/v1/compliance/intelligence/snapshot", json={}, headers=headers)
    assert resp.status_code == 201
    assert "id" in resp.json()

def test_generate_snapshot_compliance_officer(db_session: Session):
    headers = get_auth_headers(db_session, "co_test@aegis.com", "Compliance Officer")
    resp = client.post("/api/v1/compliance/intelligence/snapshot", json={}, headers=headers)
    assert resp.status_code == 201

def test_generate_snapshot_unauthorized_role(db_session: Session):
    headers = get_auth_headers(db_session, "guest_test@aegis.com", "Guest Reader")
    resp = client.post("/api/v1/compliance/intelligence/snapshot", json={}, headers=headers)
    assert resp.status_code == 403

def test_generate_snapshot_unauthenticated():
    resp = client.post("/api/v1/compliance/intelligence/snapshot", json={})
    assert resp.status_code == 401

def test_generate_snapshot_schema_validation(db_session: Session):
    headers = get_auth_headers(db_session, "admin_test@aegis.com", "ADMIN")
    # Sending without JSON body should fail schema validation (422) in FastAPI
    resp = client.post("/api/v1/compliance/intelligence/snapshot", headers=headers)
    assert resp.status_code == 422
