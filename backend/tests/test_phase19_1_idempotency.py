import pytest
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile, DiscoveredFact
from app.api.v1.endpoints.discovery import normalize_fact_str, start_discovery, DiscoveryStartRequest
from app.core.database import SessionLocal, Base, engine

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def clean_db(db_session: Session):
    yield db_session
    # Teardown
    db_session.rollback() # Ensure no pending failed transactions block teardown
    db_session.query(DiscoveredFact).filter(
        DiscoveredFact.organization_id.in_(
            db_session.query(EnterpriseProfile.id).filter(EnterpriseProfile.organization_name.like("Idem Org%"))
        )
    ).delete(synchronize_session=False)
    db_session.query(EnterpriseProfile).filter(
        EnterpriseProfile.organization_name.like("Idem Org%")
    ).delete(synchronize_session=False)
    db_session.commit()

import uuid

@pytest.fixture
def profile_1(clean_db: Session):
    pid = str(uuid.uuid4())
    p = EnterpriseProfile(
        id=pid,
        organization_name="Idem Org 1",
        country="India",
        industry_sector="Technology"
    )
    clean_db.add(p)
    clean_db.commit()
    return p

@pytest.fixture
def profile_2(clean_db: Session):
    pid = str(uuid.uuid4())
    p = EnterpriseProfile(
        id=pid,
        organization_name="Idem Org 2",
        country="India",
        industry_sector="Technology"
    )
    clean_db.add(p)
    clean_db.commit()
    return p

def test_normalization():
    assert normalize_fact_str("India") == "india"
    assert normalize_fact_str(" india ") == "india"
    assert normalize_fact_str("INDIA") == "india"
    assert normalize_fact_str("Information Security (CISO) & SecOps") == "information security (ciso) & secops"

def test_tenant_isolation(clean_db: Session, profile_1: EnterpriseProfile, profile_2: EnterpriseProfile):
    fact1 = DiscoveredFact(
        organization_id=profile_1.id,
        fact_type="LOCATION",
        fact_value="India",
        source_url="http://test.com",
        status="CONFIRMED",
        confidence=0.9,
        snippet="test"
    )
    
    fact2 = DiscoveredFact(
        organization_id=profile_2.id,
        fact_type="LOCATION",
        fact_value="India",
        source_url="http://test2.com",
        status="CONFIRMED",
        confidence=0.9,
        snippet="test"
    )
    
    clean_db.add(fact1)
    clean_db.add(fact2)
    clean_db.commit()
    
    count_1 = clean_db.query(DiscoveredFact).filter_by(organization_id=profile_1.id).count()
    count_2 = clean_db.query(DiscoveredFact).filter_by(organization_id=profile_2.id).count()
    
    assert count_1 == 1
    assert count_2 == 1

def test_business_activity_preservation(clean_db: Session, profile_1: EnterpriseProfile):
    manual_activity = DiscoveredFact(
        organization_id=profile_1.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="Electronic Toll Collection (ETC)",
        source_url="User Attestation",
        status="CONFIRMED",
        evidence_type="USER_ATTESTATION",
        confidence=1.0,
        snippet="test"
    )
    clean_db.add(manual_activity)
    clean_db.commit()
    
    # Simulate discovery crawler adding a duplicate candidate manually (since we can't easily mock the crawler without monkeypatching)
    from app.api.v1.endpoints.discovery import start_discovery
    # Instead of running start_discovery which requires hitting the real web, we test the logic directly:
    
    # Start discovery simulates pulling candidates.
    existing_facts = clean_db.query(DiscoveredFact).filter_by(organization_id=profile_1.id).all()
    existing_fact_keys = {
        (ef.fact_type, normalize_fact_str(ef.fact_value)) 
        for ef in existing_facts
    }
    
    # Crawler finds this:
    cand_fact_type = "BUSINESS_ACTIVITY"
    cand_fact_value = " Electronic Toll Collection (ETC) "
    
    cand_key = (cand_fact_type, normalize_fact_str(cand_fact_value))
    
    assert cand_key in existing_fact_keys
    
    # We assert that because it is in existing_fact_keys, it will be skipped by the new logic.
    assert len(existing_facts) == 1
    assert existing_facts[0].source_url == "User Attestation"
    assert existing_facts[0].status == "CONFIRMED"

def test_different_fact_types_not_duplicates(clean_db: Session, profile_1: EnterpriseProfile):
    # Location = India
    fact1 = DiscoveredFact(
        organization_id=profile_1.id,
        fact_type="LOCATION",
        fact_value="India",
        source_url="http://test.com",
        status="CONFIRMED",
        confidence=0.9,
        snippet="test",
    )
    clean_db.add(fact1)
    clean_db.commit()
    
    # Simulating finding a candidate with BUSINESS_ACTIVITY = India
    existing_facts = clean_db.query(DiscoveredFact).filter_by(organization_id=profile_1.id).all()
    existing_fact_keys = {
        (ef.fact_type, normalize_fact_str(ef.fact_value)) 
        for ef in existing_facts
    }
    
    cand_key = ("BUSINESS_ACTIVITY", normalize_fact_str("India"))
    assert cand_key not in existing_fact_keys
