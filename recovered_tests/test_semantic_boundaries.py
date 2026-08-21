import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.domain import EnterpriseProfile, EnterpriseUser, DiscoveryRun, DiscoveredFact
from app.services.discovery_crawler import DiscoveredPage
from app.services.fact_extractor import FactExtractor
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
            full_name="Compliance Auditor",
            role="Compliance Officer",
            email="auditor@enterprise.com"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}

def test_organization_fact_vs_regulatory_signal_classification():
    """
    TEST 1 & 2: Direct organization facts are classified as DIRECT_ORGANIZATION_FACT,
    while regulatory mentions are classified as REGULATORY_SIGNAL.
    """
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/solutions",
            title="AI & IoT Solutions | NEC India",
            text_content="NEC India provides AI and Video Analytics solutions across India. Our PII de-identification platform supports Digital Personal Data Protection (DPDP) Act compliance.",
            paragraphs=[
                "NEC India provides AI and Video Analytics solutions across India.",
                "Our PII de-identification platform supports Digital Personal Data Protection (DPDP) Act compliance."
            ]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    
    # Organization Fact
    ai_fact = next(c for c in candidates if c.fact_value == "AI & Video Analytics Solutions")
    assert ai_fact.fact_type == "BUSINESS_ACTIVITY"
    assert ai_fact.fact_relevance == "DIRECT_ORGANIZATION_FACT"

    # Regulatory Signal
    dpdp_signal = next(c for c in candidates if c.fact_value == "Digital Personal Data Protection (DPDP) Act")
    assert dpdp_signal.fact_type == "REGULATORY_SIGNAL"
    assert dpdp_signal.fact_relevance == "REGULATORY_SIGNAL"
    assert dpdp_signal.fact_relevance != "DIRECT_ORGANIZATION_FACT"

def test_regulatory_signal_does_not_create_statutory_applicability(db_session: Session, auth_headers: dict):
    """
    TEST 3, 4, 5, 6, 7: Finalization of a run with DPDP and GDPR signals preserves them as verified signals,
    but does NOT promote them to applicable regulations or corrupt profile capabilities.
    """
    profile = db_session.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="Pending Setup",
            industry_sector="Enterprise Technology",
            country="India",
            discovery_status="UNINITIALIZED"
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    run = DiscoveryRun(
        organization_id=profile.id,
        website_url="https://in.nec.com/",
        root_domain="in.nec.com",
        status="REVIEW_PENDING"
    )
    db_session.add(run)
    db_session.commit()

    # Create candidate facts: 1 business activity, 1 regulatory signal
    f_activity = DiscoveredFact(
        organization_id=profile.id,
        discovery_run_id=run.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="AI & Video Analytics Solutions",
        source_url="https://in.nec.com/solutions",
        snippet="NEC India provides AI and Video Analytics solutions.",
        status="CONFIRMED",
        confidence=0.90
    )
    f_signal = DiscoveredFact(
        organization_id=profile.id,
        discovery_run_id=run.id,
        fact_type="REGULATORY_SIGNAL",
        fact_value="Digital Personal Data Protection (DPDP) Act",
        source_url="https://in.nec.com/privacy",
        snippet="Our platform supports DPDP guidelines.",
        status="CONFIRMED",
        confidence=0.84
    )
    db_session.add_all([f_activity, f_signal])
    db_session.commit()

    # Finalize discovery
    finalize_resp = client.post("/api/v1/discovery/finalize", headers=auth_headers)
    assert finalize_resp.status_code == 200

    db_session.refresh(profile)
    # Business activity is in authoritative profile
    assert "AI & Video Analytics Solutions" in profile.business_activities
    # Regulatory signal is NOT in profile business activities or licenses
    assert "Digital Personal Data Protection (DPDP) Act" not in (profile.business_activities or [])
    assert "Digital Personal Data Protection (DPDP) Act" not in (profile.licenses or [])

    # The regulatory signal remains in DiscoveredFact table with full provenance for the future applicability engine
    fact_in_db = db_session.query(DiscoveredFact).filter(
        DiscoveredFact.discovery_run_id == run.id,
        DiscoveredFact.fact_type == "REGULATORY_SIGNAL"
    ).first()
    assert fact_in_db is not None
    assert fact_in_db.status == "CONFIRMED"
    assert fact_in_db.fact_value == "Digital Personal Data Protection (DPDP) Act"
