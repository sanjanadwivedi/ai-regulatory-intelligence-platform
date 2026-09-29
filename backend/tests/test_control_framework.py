import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.domain import EnterpriseProfile, EnterpriseUser, InternalControl, ObligationControlMapping, RegulatoryObligation, Regulation, RegulatoryApplicabilityAssessment
from app.core.security import get_current_user
import uuid
import datetime

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
        db.rollback()
        db.close()

@pytest.fixture(scope="function")
def org_a(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org A Controls", industry_sector="Tech")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture(scope="function")
def org_b(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org B Controls", industry_sector="Tech")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture(scope="function")
def user_a(org_a):
    user = EnterpriseUser(id=str(uuid.uuid4()), organization_id=org_a.id, full_name="User A", role="ADMIN")
    return user

@pytest.fixture(scope="function")
def user_b(org_b):
    user = EnterpriseUser(id=str(uuid.uuid4()), organization_id=org_b.id, full_name="User B", role="ADMIN")
    return user

@pytest.fixture(scope="function")
def reg(db_session: Session):
    r = Regulation(id=str(uuid.uuid4()), title="Test Reg", authority="Test", publication_date=datetime.date.today(), sector="Test", region="Test", content_text="Test")
    db_session.add(r)
    db_session.commit()
    return r

@pytest.fixture(scope="function")
def app_assess_a(db_session: Session, org_a, reg):
    a = RegulatoryApplicabilityAssessment(id=str(uuid.uuid4()), organization_id=org_a.id, regulation_id=reg.id, status="APPLICABLE", rationale="Test")
    db_session.add(a)
    db_session.commit()
    return a

@pytest.fixture(scope="function")
def ob_a(db_session: Session, org_a, reg, app_assess_a):
    o = RegulatoryObligation(
        id=str(uuid.uuid4()), 
        regulation_id=reg.id, 
        organization_id=org_a.id, 
        applicability_assessment_id=app_assess_a.id, 
        obligation_code="OB-A-01", 
        title="Obligation A", 
        description="Test", 
        obligation_type="SECURITY_CONTROL", 
        source_citation="Test", 
        status="ACTIVE"
    )
    db_session.add(o)
    db_session.commit()
    return o

@pytest.fixture(scope="function")
def app_assess_b(db_session: Session, org_b, reg):
    a = RegulatoryApplicabilityAssessment(id=str(uuid.uuid4()), organization_id=org_b.id, regulation_id=reg.id, status="APPLICABLE", rationale="Test")
    db_session.add(a)
    db_session.commit()
    return a

@pytest.fixture(scope="function")
def ob_b(db_session: Session, org_b, reg, app_assess_b):
    o = RegulatoryObligation(
        id=str(uuid.uuid4()), 
        regulation_id=reg.id, 
        organization_id=org_b.id, 
        applicability_assessment_id=app_assess_b.id, 
        obligation_code="OB-B-01", 
        title="Obligation B", 
        description="Test", 
        obligation_type="SECURITY_CONTROL", 
        source_citation="Test", 
        status="ACTIVE"
    )
    db_session.add(o)
    db_session.commit()
    return o

def test_1_create_control(client, db_session, user_a):
    app.dependency_overrides[get_current_user] = lambda: user_a
    payload = {
        "control_code": "AC-01",
        "name": "Access Control",
        "description": "Test",
        "category": "Security",
        "owner_department": "IT"
    }
    resp = client.post("/api/v1/controls/", json=payload)
    assert resp.status_code == 200
    assert resp.json()["control_code"] == "AC-01"
    app.dependency_overrides.clear()

def test_2_read_own_control(client, db_session, org_a, user_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-02", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.get(f"/api/v1/controls/{c.id}")
    assert resp.status_code == 200
    app.dependency_overrides.clear()

def test_3_update_own_control(client, db_session, org_a, user_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-03", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.patch(f"/api/v1/controls/{c.id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    app.dependency_overrides.clear()

def test_4_delete_own_control(client, db_session, org_a, user_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-04", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.delete(f"/api/v1/controls/{c.id}")
    assert resp.status_code == 200
    app.dependency_overrides.clear()

def test_5_org_b_cannot_read_org_a_control(client, db_session, org_a, user_b):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-05", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_b
    resp = client.get(f"/api/v1/controls/{c.id}")
    assert resp.status_code == 404
    app.dependency_overrides.clear()

def test_6_org_b_cannot_modify_org_a_control(client, db_session, org_a, user_b):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-06", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_b
    resp = client.patch(f"/api/v1/controls/{c.id}", json={"name": "Hacked"})
    assert resp.status_code == 404
    app.dependency_overrides.clear()

def test_7_org_b_cannot_delete_org_a_control(client, db_session, org_a, user_b):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="TEST-07", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_b
    resp = client.delete(f"/api/v1/controls/{c.id}")
    assert resp.status_code == 404
    app.dependency_overrides.clear()

def test_8_duplicate_control_code_within_same_org_rejected(client, db_session, org_a, user_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="DUP-01", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    payload = {
        "control_code": "DUP-01",
        "name": "Access Control",
        "description": "Test",
        "category": "Security",
        "owner_department": "IT"
    }
    resp = client.post("/api/v1/controls/", json=payload)
    assert resp.status_code == 400
    app.dependency_overrides.clear()

def test_9_same_control_code_across_different_orgs_allowed(client, db_session, org_a, org_b, user_b):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="SHARE-01", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_b
    payload = {
        "control_code": "SHARE-01",
        "name": "Access Control",
        "description": "Test",
        "category": "Security",
        "owner_department": "IT"
    }
    resp = client.post("/api/v1/controls/", json=payload)
    assert resp.status_code == 200
    app.dependency_overrides.clear()

def test_10_map_valid_obligation(client, db_session, org_a, user_a, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-10", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={"rationale": "Test"})
    assert resp.status_code == 200
    app.dependency_overrides.clear()

def test_11_one_control_mapped_to_multiple_obligations(client, db_session, org_a, user_a, reg, app_assess_a, ob_a):
    ob_a2 = RegulatoryObligation(id=str(uuid.uuid4()), regulation_id=reg.id, organization_id=org_a.id, applicability_assessment_id=app_assess_a.id, obligation_code="OB-A-02", title="Obligation A2", description="Test", obligation_type="SECURITY_CONTROL", source_citation="Test", status="ACTIVE")
    db_session.add(ob_a2)
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-11", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp1 = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    resp2 = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a2.id}", json={})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    
    resp_get = client.get(f"/api/v1/controls/{c.id}/obligations")
    assert len(resp_get.json()) == 2
    app.dependency_overrides.clear()

def test_12_one_obligation_mapped_to_multiple_controls(client, db_session, org_a, user_a, ob_a):
    c1 = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-12A", name="T", description="T", category="T", owner_department="T")
    c2 = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-12B", name="T", description="T", category="T", owner_department="T")
    db_session.add_all([c1, c2])
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp1 = client.post(f"/api/v1/controls/{c1.id}/obligations/{ob_a.id}", json={})
    resp2 = client.post(f"/api/v1/controls/{c2.id}/obligations/{ob_a.id}", json={})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    app.dependency_overrides.clear()

def test_13_duplicate_mapping_rejected(client, db_session, org_a, user_a, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-13", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    assert resp.status_code == 400
    app.dependency_overrides.clear()

def test_14_cross_tenant_mapping_rejected(client, db_session, org_a, org_b, user_b, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_b.id, control_code="MAP-14", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_b
    # Try to map org A's obligation to org B's control as user B
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    assert resp.status_code == 404
    app.dependency_overrides.clear()

def test_15_not_applicable_obligation_cannot_be_mapped(client, db_session, org_a, user_a, reg, app_assess_a):
    ob_na = RegulatoryObligation(id=str(uuid.uuid4()), regulation_id=reg.id, organization_id=org_a.id, applicability_assessment_id=app_assess_a.id, obligation_code="OB-NA", title="NA", description="T", obligation_type="OTHER", source_citation="T", status="NOT_APPLICABLE")
    db_session.add(ob_na)
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-15", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_na.id}", json={})
    assert resp.status_code == 400
    app.dependency_overrides.clear()

def test_16_requires_review_obligation_cannot_be_mapped(client, db_session, org_a, user_a, reg, app_assess_a):
    ob_rr = RegulatoryObligation(id=str(uuid.uuid4()), regulation_id=reg.id, organization_id=org_a.id, applicability_assessment_id=app_assess_a.id, obligation_code="OB-RR", title="RR", description="T", obligation_type="OTHER", source_citation="T", status="REQUIRES_REVIEW")
    db_session.add(ob_rr)
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-16", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_rr.id}", json={})
    assert resp.status_code == 400
    app.dependency_overrides.clear()

def test_17_missing_obligation_rejected(client, db_session, org_a, user_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-17", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{str(uuid.uuid4())}", json={})
    assert resp.status_code == 404
    app.dependency_overrides.clear()

def test_18_missing_control_rejected(client, db_session, org_a, user_a, ob_a):
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{str(uuid.uuid4())}/obligations/{ob_a.id}", json={})
    assert resp.status_code == 404
    app.dependency_overrides.clear()

from app.models.domain import AuditLog

def test_19_control_creation_generates_audit(client, db_session, org_a, user_a):
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post("/api/v1/controls/", json={"control_code": "AUD-01", "name": "T", "description": "T", "category": "T", "owner_department": "T"})
    assert resp.status_code == 200
    c_id = resp.json()["id"]
    
    audit = db_session.query(AuditLog).filter_by(organization_id=org_a.id, target_id=c_id, action="CONTROL_CREATED").first()
    assert audit is not None
    app.dependency_overrides.clear()

def test_20_mapping_generates_audit(client, db_session, org_a, user_a, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-20", name="T", description="T", category="T", owner_department="T")
    db_session.add(c)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    assert resp.status_code == 200
    m_id = resp.json()["id"]
    
    audit = db_session.query(AuditLog).filter_by(organization_id=org_a.id, target_id=m_id, action="CONTROL_OBLIGATION_MAPPED").first()
    assert audit is not None
    app.dependency_overrides.clear()

def test_21_unmapping_generates_audit(client, db_session, org_a, user_a, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-21", name="T", description="T", category="T", owner_department="T")
    m = ObligationControlMapping(id=str(uuid.uuid4()), organization_id=org_a.id, obligation_id=ob_a.id, control_id=c.id)
    db_session.add_all([c, m])
    db_session.commit()
    m_id = m.id
    
    app.dependency_overrides[get_current_user] = lambda: user_a
    resp = client.delete(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}")
    assert resp.status_code == 200
    
    audit = db_session.query(AuditLog).filter_by(organization_id=org_a.id, target_id=m_id, action="CONTROL_OBLIGATION_UNMAPPED").first()
    assert audit is not None
    app.dependency_overrides.clear()

def test_22_org_id_from_request_cannot_override_auth_org(client, db_session, org_a, org_b, user_b):
    app.dependency_overrides[get_current_user] = lambda: user_b
    payload = {
        "organization_id": org_a.id,
        "control_code": "SNEAKY-01",
        "name": "Access Control",
        "description": "Test",
        "category": "Security",
        "owner_department": "IT"
    }
    resp = client.post("/api/v1/controls/", json=payload)
    # the endpoint takes current_org from Depends(get_current_organization). It ignores body.
    assert resp.status_code == 200
    # ensure the control was created in org_b, not org_a
    assert resp.json()["organization_id"] == org_b.id
    app.dependency_overrides.clear()

def test_23_user_without_org_fails_closed(client, db_session):
    user_no_org = EnterpriseUser(id="user_no_org", organization_id=None, full_name="User No Org", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user_no_org
    resp = client.get("/api/v1/controls/")
    assert resp.status_code == 403
    app.dependency_overrides.clear()

def test_24_historical_mappings_not_mutated(client, db_session, org_a, user_a, ob_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="MAP-24", name="T", description="T", category="T", owner_department="T")
    m = ObligationControlMapping(id=str(uuid.uuid4()), organization_id=org_a.id, obligation_id=ob_a.id, control_id=c.id)
    db_session.add_all([c, m])
    db_session.commit()
    m_id = m.id
    
    app.dependency_overrides[get_current_user] = lambda: user_a
    # Delete mapping
    client.delete(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}")
    
    # recreate mapping
    resp = client.post(f"/api/v1/controls/{c.id}/obligations/{ob_a.id}", json={})
    assert resp.json()["id"] != m_id # A new mapping record should be created
    app.dependency_overrides.clear()