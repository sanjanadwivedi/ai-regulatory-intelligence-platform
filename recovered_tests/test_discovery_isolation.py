import pytest
import datetime
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, Base, engine
from app.models.domain import EnterpriseProfile, EnterpriseUser, DiscoveryRun, DiscoveredFact
from app.core.security import create_access_token
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def auth_headers(db_session: Session):
    user = db_session.query(EnterpriseUser).first()
    if not user:
        user = EnterpriseUser(
            full_name="Sarah Jenkins",
            role="Compliance Officer",
            email="sarah.jenkins@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}

def test_discovery_run_isolation_and_review(db_session: Session, auth_headers: dict):
    """
    Test A & B:
    - Create HDFC discovery run with HDFC facts.
    - Create NEC discovery run with NEC facts.
    - GET facts for NEC returns ONLY NEC facts.
    - HDFC facts remain unchanged.
    """
    profile = db_session.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="Enterprise Bank",
            industry_sector="Banking",
            discovery_status="CONFIRMED"
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    # 1. Seed Run A (HDFC)
    run_hdfc = DiscoveryRun(
        organization_id=profile.id,
        website_url="https://www.hdfcbank.com",
        root_domain="hdfcbank.com",
        status="CONFIRMED",
        started_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
        completed_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    )
    db_session.add(run_hdfc)
    db_session.commit()

    fact_hdfc = DiscoveredFact(
        organization_id=profile.id,
        discovery_run_id=run_hdfc.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="Retail Banking",
        source_url="https://www.hdfcbank.com/about",
        snippet="We offer retail banking services across India.",
        status="CONFIRMED",
        confidence=0.95
    )
    db_session.add(fact_hdfc)
    db_session.commit()

    # 2. Seed Run B (NEC)
    run_nec = DiscoveryRun(
        organization_id=profile.id,
        website_url="https://in.nec.com",
        root_domain="in.nec.com",
        status="REVIEW_PENDING",
        started_at=datetime.datetime.utcnow()
    )
    db_session.add(run_nec)
    db_session.commit()

    fact_nec_1 = DiscoveredFact(
        organization_id=profile.id,
        discovery_run_id=run_nec.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="ICT & Digital Transformation Solutions",
        source_url="https://in.nec.com/solutions",
        snippet="NEC India provides AI and IoT solutions.",
        status="PENDING",
        confidence=0.92
    )
    fact_nec_2 = DiscoveredFact(
        organization_id=profile.id,
        discovery_run_id=run_nec.id,
        fact_type="PRODUCT_SERVICE",
        fact_value="AI Video Analytics & Urban Monitoring",
        source_url="https://in.nec.com/products",
        snippet="NEC Mi-Eye video analytics for urban spaces.",
        status="PENDING",
        confidence=0.88
    )
    db_session.add_all([fact_nec_1, fact_nec_2])
    db_session.commit()

    # Query GET /api/v1/discovery/facts (default gets latest run = NEC)
    resp = client.get("/api/v1/discovery/facts?status=ALL", headers=auth_headers)
    assert resp.status_code == 200
    nec_facts = resp.json()

    # Test A Assertions: ONLY NEC facts returned
    assert len(nec_facts) == 2
    for f in nec_facts:
        assert "nec.com" in f["source_url"]
        assert f["discovery_run_id"] == run_nec.id
        assert "Retail Banking" not in f["fact_value"]

    # Test B Assertion: HDFC fact is still in DB and unchanged
    hdfc_fact_in_db = db_session.query(DiscoveredFact).filter(DiscoveredFact.id == fact_hdfc.id).first()
    assert hdfc_fact_in_db.status == "CONFIRMED"
    assert hdfc_fact_in_db.discovery_run_id == run_hdfc.id

    # Test C: Confirm ONE NEC candidate
    confirm_resp = client.post(f"/api/v1/discovery/facts/{fact_nec_1.id}/confirm", headers=auth_headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "CONFIRMED"

    # Verify other NEC fact remains PENDING
    nec_2_in_db = db_session.query(DiscoveredFact).filter(DiscoveredFact.id == fact_nec_2.id).first()
    assert nec_2_in_db.status == "PENDING"

    # Test D: Reject NEC candidate 2
    reject_resp = client.post(f"/api/v1/discovery/facts/{fact_nec_2.id}/reject", headers=auth_headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    # Test E: Finalize NEC discovery
    final_resp = client.post("/api/v1/discovery/finalize", headers=auth_headers)
    assert final_resp.status_code == 200
    profile_data = final_resp.json()["profile"]

    # Confirmed profile should now contain the confirmed NEC activity
    assert "ICT & Digital Transformation Solutions" in profile_data["business_activities"]
    assert profile_data["discovery_status"] == "CONFIRMED"

    # Test F: Cross-organization/run unauthorized rejection
    # Try modifying a nonexistent fact
    fake_resp = client.post("/api/v1/discovery/facts/nonexistent-id/confirm", headers=auth_headers)
    assert fake_resp.status_code == 404
