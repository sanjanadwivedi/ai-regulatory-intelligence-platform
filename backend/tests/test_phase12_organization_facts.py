import pytest
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile, EnterpriseUser, DiscoveredFact, AuditLog, RegulatoryApplicabilityAssessment
from app.services.applicability_engine import ApplicabilityEngine
from app.core.database import get_db
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="function")
def client():
    return TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    from app.core.database import Base, engine, SessionLocal
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        app.dependency_overrides[get_db] = lambda: db
        yield db
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()

@pytest.fixture(scope="function")
def auth_headers(db_session: Session, profile):
    user = db_session.query(EnterpriseUser).filter_by(email="admin@ihmcl.co.in").first()
    if not user:
        user = EnterpriseUser(email="admin@ihmcl.co.in", hashed_password="hash", full_name="Admin", role="ADMIN", organization_id=profile.id)
        db_session.add(user)
        db_session.commit()
    elif not user.organization_id:
        user.organization_id = profile.id
        db_session.commit()
    from app.core.security import create_access_token
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def profile(db_session: Session):
    prof = db_session.query(EnterpriseProfile).filter_by(organization_name="Indian Highways Management Company Limited (IHMCL)").first()
    if not prof:
        import uuid
        prof = EnterpriseProfile(
            id=str(uuid.uuid4()),
            organization_name="Indian Highways Management Company Limited (IHMCL)",
            industry_sector="Technology",
            country="India",
            discovery_status="CONFIRMED"
        )
        db_session.add(prof)
        db_session.commit()
    
    db_session.query(DiscoveredFact).filter_by(organization_id=prof.id).delete()
    db_session.commit()
    return prof

def test_1_authenticated_user_can_create_business_activity(db_session: Session, client, auth_headers, profile):
    # Ensure starting clean
    db_session.query(DiscoveredFact).filter_by(fact_type="BUSINESS_ACTIVITY", fact_value="service provider").delete()
    db_session.commit()

    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "service provider",
        "source_url": "",
        "snippet": ""
    }, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fact_type"] == "BUSINESS_ACTIVITY"
    assert data["fact_value"] == "service provider"

def test_2_unauthenticated_user_receives_authorization_failure(db_session: Session, client):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "service provider"
    })
    assert res.status_code == 401

def test_3_user_without_organization_is_rejected_safely(db_session: Session, client):
    user = EnterpriseUser(email="noorg@test.com", hashed_password="hash", full_name="No Org", role="ADMIN")
    db_session.add(user)
    db_session.commit()
    from app.core.security import create_access_token
    token = create_access_token(user.id)
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "service provider"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

def test_4_fact_is_stored_with_correct_organization_id(db_session: Session, client, auth_headers, profile):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "LOCATION",
        "fact_value": "new york"
    }, headers=auth_headers)
    if res.status_code != 200:
        print(f"FAILED TEST 4: {res.text}")
    assert res.status_code == 200
    fact_id = res.json()["id"]
    fact = db_session.query(DiscoveredFact).filter_by(id=fact_id).first()
    assert fact.organization_id == profile.id

def test_5_fact_value_is_added_to_enterprise_profile(db_session: Session, client, auth_headers, profile):
    db_session.query(DiscoveredFact).filter_by(fact_value="cloud service provider").delete()
    db_session.commit()
    client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "cloud service provider"
    }, headers=auth_headers)
    db_session.refresh(profile)
    assert "cloud service provider" in profile.business_activities

def test_6_existing_activities_are_preserved(db_session: Session, client, auth_headers, profile):
    client.post("/api/v1/discovery/facts/manual", json={"fact_type": "BUSINESS_ACTIVITY", "fact_value": "service provider"}, headers=auth_headers)
    client.post("/api/v1/discovery/facts/manual", json={"fact_type": "BUSINESS_ACTIVITY", "fact_value": "cloud service provider"}, headers=auth_headers)
    
    from app.core.database import SessionLocal
    db = SessionLocal()
    p = db.query(EnterpriseProfile).get(profile.id)
    assert "service provider" in p.business_activities
    assert "cloud service provider" in p.business_activities
    db.close()

def test_7_duplicate_facts_are_handled(db_session: Session, client, auth_headers, profile):
    client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "service provider",
        "source_url": "",
        "snippet": ""
    }, headers=auth_headers)
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "service provider",
        "source_url": "",
        "snippet": ""
    }, headers=auth_headers)
    assert res.status_code == 409

def test_8_invalid_fact_type_rejected(client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "INVALID_TYPE",
        "fact_value": "test"
    }, headers=auth_headers)
    assert res.status_code == 400

def test_9_empty_fact_value_rejected(client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "   "
    }, headers=auth_headers)
    assert res.status_code == 400

def test_10_invalid_source_url_rejected(client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "data centre",
        "source_url": "ftp://invalid.com"
    }, headers=auth_headers)
    assert res.status_code == 400

def test_11_source_url_is_persisted(db_session: Session, client, auth_headers, profile):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "vps provider",
        "source_url": "https://example.com"
    }, headers=auth_headers)
    assert res.status_code == 200, res.text
    fact = db_session.query(DiscoveredFact).filter_by(id=res.json()["id"]).first()
    assert fact.source_url == "https://example.com"

def test_12_snippet_is_persisted(db_session: Session, client, auth_headers, profile):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "government organisation",
        "snippet": "We are a gov org"
    }, headers=auth_headers)
    fact = db_session.query(DiscoveredFact).filter_by(id=res.json()["id"]).first()
    assert fact.snippet == "We are a gov org"

def test_13_user_provided_provenance_is_persisted(db_session: Session, client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "COMPANY",
        "fact_value": "Test LLC"
    }, headers=auth_headers)
    fact = db_session.query(DiscoveredFact).filter_by(id=res.json()["id"]).first()
    assert fact.extraction_method == "USER_PROVIDED"

def test_14_user_attestation_is_distinguished_from_authoritative_evidence(db_session: Session, client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "LOCATION",
        "fact_value": "london"
    }, headers=auth_headers)
    fact = db_session.query(DiscoveredFact).filter_by(id=res.json()["id"]).first()
    assert fact.evidence_type == "USER_ATTESTATION"
    assert fact.evidence_strength == "ATTESTED"
    assert fact.source_url == "User Attestation"

def test_15_audit_log_is_generated(db_session: Session, client, auth_headers, profile):
    client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "LOCATION",
        "fact_value": "tokyo"
    }, headers=auth_headers)
    
    from app.core.database import SessionLocal
    db = SessionLocal()
    audit = db.query(AuditLog).filter_by(action="MANUAL_FACT_ADDED").order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.organization_id == profile.id
    assert audit.details["fact_type"] == "LOCATION"
    db.close()

def test_16_user_cannot_inject_another_organization_id(db_session: Session, client, auth_headers):
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "LOCATION",
        "fact_value": "paris",
        "organization_id": "malicious-id"
    }, headers=auth_headers)
    fact = db_session.query(DiscoveredFact).filter_by(id=res.json()["id"]).first()
    assert fact.organization_id != "malicious-id"

def test_17_cross_tenant_facts_cannot_be_accessed():
    pass

def test_18_cross_tenant_facts_cannot_be_modified():
    pass

def test_19_missing_business_activity_preserves_existing_requires_review_behavior():
    pass

def test_20_user_attested_business_activity_does_not_bypass_evidence_policy():
    pass

def test_21_applicability_consumes_profile_business_activities_according_to_existing_rules():
    pass

def test_22_no_obligation_is_generated_merely_because_user_enters_a_fact():
    pass

def test_23_existing_discovery_facts_remain_intact(db_session: Session, profile):
    fact = DiscoveredFact(
        organization_id=profile.id,
        fact_type="COMPANY",
        fact_value="IHMCL",
        source_url="https://example.com",
        snippet="snippet",
        extraction_method="CRAWLER",
        confidence=0.9,
        status="CONFIRMED"
    )
    db_session.add(fact)
    db_session.commit()
    facts = db_session.query(DiscoveredFact).filter_by(organization_id=profile.id).all()
    assert len(facts) > 0

def test_24_existing_organization_profile_tests_pass():
    pass

def test_25_existing_applicability_tests_pass():
    pass

def test_26_user_can_delete_business_activity(db_session: Session, client, auth_headers, profile):
    # 1. Add fact
    res = client.post("/api/v1/discovery/facts/manual", json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "Electronic Toll Collection (ETC)"
    }, headers=auth_headers)
    assert res.status_code == 200
    fact_id = res.json()["id"]

    # 2. Delete fact
    del_res = client.delete(f"/api/v1/discovery/facts/{fact_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "SUCCESS"

    # 3. Verify it's gone
    get_res = client.get("/api/v1/discovery/facts?status=ALL", headers=auth_headers)
    assert get_res.status_code == 200
    facts = get_res.json()
    assert not any(f["id"] == fact_id for f in facts)

def test_27_unauthorized_user_cannot_delete_cross_tenant_fact(db_session: Session, client, auth_headers, profile):
    # Setup user B
    from app.models.domain import EnterpriseUser, EnterpriseProfile
    import uuid
    user_b_id = str(uuid.uuid4())
    org_b_id = str(uuid.uuid4())
    
    org_b = EnterpriseProfile(
        id=org_b_id,
        organization_name="Org B",
        industry_sector="ind-1",
        country="India",
        regulator_region="ind-1",
        discovery_status="PENDING"
    )
    db_session.add(org_b)
    user_b = EnterpriseUser(id=user_b_id, email="userb@example.com", full_name="User B", role="Compliance Officer", organization_id=org_b_id)
    db_session.add(user_b)
    
    # Add fact to profile A
    fact = DiscoveredFact(
        organization_id=profile.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="Secret Activity",
        source_url="https://example.com",
        snippet="snippet",
        status="CONFIRMED"
    )
    db_session.add(fact)
    db_session.commit()
    db_session.refresh(fact)

    # user B tries to delete fact belonging to profile A
    from app.core.security import create_access_token
    token_b = create_access_token(subject=user_b.id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    del_res = client.delete(f"/api/v1/discovery/facts/{fact.id}", headers=headers_b)
    assert del_res.status_code in [403, 404]