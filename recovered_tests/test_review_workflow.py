import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile, EnterpriseUser, Regulation, DiscoveredFact, 
    RegulatoryApplicabilityAssessment, RegulatoryApplicabilityCriterion, ApplicabilityReviewItem
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.review_service import ReviewService

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    from seed_data import seed_database_data
    seed_database_data()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def setup_test_data(db: Session):
    profile = db.query(EnterpriseProfile).first()
    reg = db.query(Regulation).first()
    user = db.query(EnterpriseUser).filter_by(role="Compliance Officer").first()
    if not user:
        user = EnterpriseUser(full_name="Tester", role="COMPLIANCE_OFFICER", email="test@example.com")
        db.add(user)
        db.flush()

    # Clear facts to ensure REQUIRES_REVIEW
    db.query(DiscoveredFact).filter_by(organization_id=profile.id).delete()
    db.commit()

    # Add a mock criterion requiring AUTHORITATIVE evidence
    crit = RegulatoryApplicabilityCriterion(
        regulation_id=reg.id,
        criterion_type="TEST_CRITERION",
        description="Requires test fact",
        is_mandatory=1,
        operator="EQUALS",
        expected_value="yes",
        evidence_fact_type="TEST_FACT",
        minimum_evidence_strength="AUTHORITATIVE"
    )
    db.add(crit)
    db.commit()

    return profile, reg, user, crit

def test_1_review_item_creation(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    assert len(assessments) > 0
    assessment = next(a for a in assessments if a.regulation_id == reg.id)
    assert assessment.status == "REQUIRES_REVIEW"
    
    items = db_session.query(ApplicabilityReviewItem).filter_by(organization_id=profile.id, criterion_id=crit.id).all()
    assert len(items) == 1
    assert items[0].status == "OPEN"

def test_2_review_item_idempotency(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    items1 = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).all()
    assert len(items1) == 1
    
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    items2 = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).all()
    assert len(items2) == 1
    assert items1[0].id == items2[0].id

def test_6_authoritative_evidence_accepted_and_11_resolution(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    
    res = ReviewService.resolve_applicability_review(
        db=db_session,
        item_id=item.id,
        organization_id=profile.id,
        user_id=user.id,
        user_role="COMPLIANCE_OFFICER",
        evidence_fact_value="yes",
        evidence_type="REGULATORY_REGISTRATION",
        evidence_strength="AUTHORITATIVE",
        source_url="http://test.com/evidence"
    )
    assert res["status"] == "RESOLVED"
    
    db_session.refresh(item)
    assert item.status == "RESOLVED"
    assert item.resolved_by == user.id

def test_8_inferred_evidence_insufficient(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    
    res = ReviewService.resolve_applicability_review(
        db=db_session,
        item_id=item.id,
        organization_id=profile.id,
        user_id=user.id,
        user_role="COMPLIANCE_OFFICER",
        evidence_fact_value="yes",
        evidence_type="OTHER",
        evidence_strength="INFERRED",
        source_url="http://test.com/inferred"
    )
    assert res["status"] == "UNDER_REVIEW"
    db_session.refresh(item)
    assert item.status == "UNDER_REVIEW"

def test_9_false_evidence(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    
    res = ReviewService.resolve_applicability_review(
        db=db_session,
        item_id=item.id,
        organization_id=profile.id,
        user_id=user.id,
        user_role="COMPLIANCE_OFFICER",
        evidence_fact_value="no",
        evidence_type="REGULATORY_REGISTRATION",
        evidence_strength="AUTHORITATIVE",
        source_url="http://test.com/false_evidence",
        known_state="FALSE"
    )
    assert res["status"] == "RESOLVED"
    
    # Verify assessment status is NOT_APPLICABLE because the mandatory criterion failed
    new_assessment = db_session.query(RegulatoryApplicabilityAssessment).filter_by(id=res["assessment_id"]).first()
    assert new_assessment.status == "NOT_APPLICABLE"

def test_13_tenant_isolation(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    
    with pytest.raises(PermissionError, match="Tenant isolation violation"):
        ReviewService.resolve_applicability_review(
            db=db_session,
            item_id=item.id,
            organization_id="wrong_tenant_id",
            user_id=user.id,
            user_role="COMPLIANCE_OFFICER",
            evidence_fact_value="yes",
            evidence_type="REGULATORY_REGISTRATION",
            evidence_strength="AUTHORITATIVE",
            source_url="http://test.com/evidence"
        )

def test_14_rbac(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    
    with pytest.raises(PermissionError, match="not authorized"):
        ReviewService.resolve_applicability_review(
            db=db_session,
            item_id=item.id,
            organization_id=profile.id,
            user_id=user.id,
            user_role="VIEWER",
            evidence_fact_value="yes",
            evidence_type="REGULATORY_REGISTRATION",
            evidence_strength="AUTHORITATIVE",
            source_url="http://test.com/evidence"
        )

def test_16_historical_snapshot_immutability(db_session: Session):
    profile, reg, user, crit = setup_test_data(db_session)
    assessments_first = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    old_id = next(a.id for a in assessments_first if a.regulation_id == reg.id)
    
    item = db_session.query(ApplicabilityReviewItem).filter_by(criterion_id=crit.id).first()
    ReviewService.resolve_applicability_review(
        db=db_session,
        item_id=item.id,
        organization_id=profile.id,
        user_id=user.id,
        user_role="COMPLIANCE_OFFICER",
        evidence_fact_value="yes",
        evidence_type="REGULATORY_REGISTRATION",
        evidence_strength="AUTHORITATIVE",
        source_url="http://test.com/evidence"
    )
    
    old_assessment = db_session.query(RegulatoryApplicabilityAssessment).filter_by(id=old_id).first()
    assert old_assessment.status == "REQUIRES_REVIEW"
    
    db_session.refresh(item)
    assert item.assessment_id != old_id
    
    new_assessment = db_session.query(RegulatoryApplicabilityAssessment).filter_by(id=item.assessment_id).first()
    assert new_assessment.status == "APPLICABLE" or new_assessment.status == "REQUIRES_REVIEW"
