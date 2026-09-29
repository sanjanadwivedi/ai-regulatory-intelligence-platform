import pytest
from sqlalchemy.orm import Session
from app.models.domain import (
    EnterpriseProfile, 
    Regulation, 
    RegulatoryApplicabilityAssessment, 
    RegulatoryObligation,
    DiscoveredFact,
    ApplicabilityReviewItem
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.obligation_engine import ObligationEngine
from app.services.review_service import ReviewService
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
    # Do not wipe the entire shared database. Only yield the session.
    # We will explicitly delete mock data at the end of tests.
    yield db_session
    
    # Teardown mock data created by this test file
    db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id.in_(["org-test-1", "org-test-2"])).delete(synchronize_session=False)
    db_session.query(ApplicabilityReviewItem).filter(ApplicabilityReviewItem.organization_id.in_(["org-test-1", "org-test-2"])).delete(synchronize_session=False)
    db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id.in_(["org-test-1", "org-test-2"])).delete(synchronize_session=False)
    db_session.query(RegulatoryApplicabilityCriterion).filter(RegulatoryApplicabilityCriterion.id.in_(["crit-1", "crit-2", "crit-3"])).delete(synchronize_session=False)
    db_session.query(Regulation).filter(Regulation.id.in_(["reg-applicable", "reg-not-applicable", "reg-review"])).delete(synchronize_session=False)
    db_session.query(DiscoveredFact).filter(DiscoveredFact.organization_id.in_(["org-test-1", "org-test-2"])).delete(synchronize_session=False)
    db_session.query(EnterpriseProfile).filter(EnterpriseProfile.id.in_(["org-test-1", "org-test-2"])).delete(synchronize_session=False)
    db_session.commit()

@pytest.fixture
def profile(clean_db: Session):
    p = EnterpriseProfile(
        id="org-test-1",
        organization_name="Test Org",
        country="India",
        industry_sector="Technology",
        business_activities=["intermediary"]
    )
    clean_db.add(p)
    clean_db.commit()
    return p

@pytest.fixture
def profile_other(clean_db: Session):
    p = EnterpriseProfile(
        id="org-test-2",
        organization_name="Other Org",
        country="USA",
        industry_sector="Finance"
    )
    clean_db.add(p)
    clean_db.commit()
    return p

from datetime import date
from app.models.domain import RegulatoryApplicabilityCriterion

@pytest.fixture
def regulation_applicable(clean_db: Session):
    r = Regulation(
        id="reg-applicable",
        title="Test APPLICABLE Regulation",
        authority="Test Authority",
        publication_date=date(2026, 1, 1),
        effective_date=date(2026, 2, 1),
        sector="Cross-Sector",
        region="Global",
        content_text="Mock regulation content",
        status="ACTIVE",
        applicability_criteria=[
            RegulatoryApplicabilityCriterion(
                id="crit-1",
                criterion_type="Location",
                description="Mock criteria",
                evidence_fact_type="LOCATION",
                expected_value="India",
                operator="EQUALS",
                is_mandatory=1
            )
        ]
    )
    clean_db.add(r)
    clean_db.commit()
    return r

@pytest.fixture
def regulation_not_applicable(clean_db: Session):
    r = Regulation(
        id="reg-not-applicable",
        title="Test NOT APPLICABLE Regulation",
        authority="Test Authority",
        publication_date=date(2026, 1, 1),
        effective_date=date(2026, 2, 1),
        sector="Cross-Sector",
        region="Global",
        content_text="Mock regulation content",
        status="ACTIVE",
        applicability_criteria=[
            RegulatoryApplicabilityCriterion(
                id="crit-2",
                criterion_type="Location",
                description="Mock criteria",
                evidence_fact_type="LOCATION",
                expected_value="UK",
                operator="EQUALS",
                is_mandatory=1
            )
        ]
    )
    clean_db.add(r)
    clean_db.commit()
    return r

@pytest.fixture
def regulation_requires_review(clean_db: Session):
    r = Regulation(
        id="reg-review",
        title="Test REQUIRES REVIEW Regulation",
        authority="Test Authority",
        publication_date=date(2026, 1, 1),
        effective_date=date(2026, 2, 1),
        sector="Cross-Sector",
        region="Global",
        content_text="Mock regulation content",
        status="ACTIVE",
        applicability_criteria=[
            RegulatoryApplicabilityCriterion(
                id="crit-3",
                criterion_type="Missing Info",
                description="Mock criteria",
                evidence_fact_type="EMPLOYEE_COUNT",
                expected_value="500",
                operator=">=",
                is_mandatory=1
            )
        ]
    )
    clean_db.add(r)
    clean_db.commit()
    return r

def test_applicable_generates_obligations(clean_db: Session, profile: EnterpriseProfile, regulation_applicable: Regulation):
    assessments = ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    
    obs = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id).all()
    assert len(obs) > 0
    for ob in obs:
        assert ob.organization_id == profile.id
        assert ob.status in ["ACTIVE", "REQUIRES_REVIEW"]

def test_repeated_evaluation_no_duplicates(clean_db: Session, profile: EnterpriseProfile, regulation_applicable: Regulation):
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    count_1 = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id).count()
    
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    count_2 = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id).count()
    
    assert count_1 > 0
    assert count_1 == count_2

def test_not_applicable_no_obligations(clean_db: Session, profile: EnterpriseProfile, regulation_not_applicable: Regulation):
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    count = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id, regulation_id=regulation_not_applicable.id).count()
    assert count == 0

def test_requires_review_no_active_obligations(clean_db: Session, profile: EnterpriseProfile, regulation_requires_review: Regulation):
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    count = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id, regulation_id=regulation_requires_review.id, status="ACTIVE").count()
    assert count == 0

def test_requires_review_resolved_as_applicable(clean_db: Session, profile: EnterpriseProfile, regulation_requires_review: Regulation):
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile.id, clean_db)
    
    # Assert no active obligations yet
    obs = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id, regulation_id=regulation_requires_review.id, status="ACTIVE").count()
    assert obs == 0
    
    # Resolve the review
    item = clean_db.query(ApplicabilityReviewItem).filter_by(organization_id=profile.id, regulation_id=regulation_requires_review.id).first()
    assert item is not None
    
    ReviewService.resolve_applicability_review(
        db=clean_db,
        item_id=item.id,
        organization_id=profile.id,
        user_id="user1",
        user_role="COMPLIANCE_OFFICER",
        evidence_fact_value="1000",
        evidence_type="USER_ATTESTATION",
        evidence_strength="AUTHORITATIVE",
        source_url="http://test.com"
    )
    
    ObligationEngine.generate_obligations(profile.id, clean_db)
    
    total_obs = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id, regulation_id=regulation_requires_review.id).count()
    assert total_obs > 0

def test_tenant_isolation_obligations(clean_db: Session, profile: EnterpriseProfile, profile_other: EnterpriseProfile, regulation_applicable: Regulation):
    # Both evaluate
    ApplicabilityEngine.evaluate_organization(profile.id, clean_db)
    ApplicabilityEngine.evaluate_organization(profile_other.id, clean_db)
    
    ObligationEngine.generate_obligations(profile.id, clean_db)
    ObligationEngine.generate_obligations(profile_other.id, clean_db)
    
    obs_1 = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile.id).all()
    obs_2 = clean_db.query(RegulatoryObligation).filter_by(organization_id=profile_other.id).all()
    
    assert len(obs_1) > 0
    # Profile other is USA, regulation requires India. So it's NOT APPLICABLE
    assert len(obs_2) == 0
    
    for ob in obs_1:
        assert ob.organization_id == profile.id
