import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.domain import (
    Base,
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    ApplicabilityReviewItem,
    RegulatoryApplicabilityCriterion
)
from app.services.applicability_engine import ApplicabilityEngine
import uuid

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def setup_isolation_data(db_session: Session):
    # Create two tenants
    org1 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Tenant 1", industry_sector="Technology", departments=[])
    org2 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Tenant 2", industry_sector="Finance", departments=[])
    db_session.add(org1)
    db_session.add(org2)
    
    reg_id = "test-reg-cardinality"
    import datetime
    reg = Regulation(id=reg_id, title="Test Reg", authority="Authority", status="PUBLISHED", publication_date=datetime.date.today(), sector="Technology", region="US", content_text="Test content", source_url="http://test.com")
    db_session.add(reg)
    
    # Add multiple criteria with same required_fact to ensure they spawn multiple items, but only 1 assessment
    crit1 = RegulatoryApplicabilityCriterion(
        id=str(uuid.uuid4()),
        regulation_id=reg_id,
        criterion_type="Test Criterion 1",
        description="desc",
        evidence_fact_type="BUSINESS_ACTIVITY",
        operator="CONTAINS",
        expected_value="cloud provider",
        is_mandatory=True,
        criterion_group="GROUP_1",
        group_operator="OR"
    )
    crit2 = RegulatoryApplicabilityCriterion(
        id=str(uuid.uuid4()),
        regulation_id=reg_id,
        criterion_type="Test Criterion 2",
        description="desc",
        evidence_fact_type="BUSINESS_ACTIVITY",
        operator="CONTAINS",
        expected_value="data center",
        is_mandatory=True,
        criterion_group="GROUP_1",
        group_operator="OR"
    )
    db_session.add(crit1)
    db_session.add(crit2)
    db_session.commit()
    
    return org1, org2, reg_id

def test_applicability_cardinality_and_isolation(db_session: Session, setup_isolation_data):
    org1, org2, reg_id = setup_isolation_data
    
    # Run evaluation for org1
    assessments1 = ApplicabilityEngine.evaluate_organization(org1.id, db_session)
    
    # Ensure only 1 assessment is created per regulation for org1
    assert len(assessments1) == 1
    assmt1 = assessments1[0]
    assert assmt1.status == "REQUIRES_REVIEW"
    assert assmt1.organization_id == org1.id
    
    # Ensure 2 review items are created, one for each missing criterion in the group
    items1 = db_session.query(ApplicabilityReviewItem).filter_by(organization_id=org1.id, assessment_id=assmt1.id).all()
    assert len(items1) == 2
    for i in items1:
        assert i.required_fact == "BUSINESS_ACTIVITY"
        assert i.status == "OPEN"
        assert i.organization_id == org1.id

    # Run evaluation for org2
    assessments2 = ApplicabilityEngine.evaluate_organization(org2.id, db_session)
    assert len(assessments2) == 1
    assmt2 = assessments2[0]
    assert assmt2.status == "REQUIRES_REVIEW"
    assert assmt2.organization_id == org2.id
    
    items2 = db_session.query(ApplicabilityReviewItem).filter_by(organization_id=org2.id, assessment_id=assmt2.id).all()
    assert len(items2) == 2
    for i in items2:
        assert i.required_fact == "BUSINESS_ACTIVITY"
        assert i.status == "OPEN"
        assert i.organization_id == org2.id
        
    # Isolation check: assessment IDs and review items should not cross over
    assert assmt1.id != assmt2.id
    item1_ids = {i.id for i in items1}
    item2_ids = {i.id for i in items2}
    assert item1_ids.isdisjoint(item2_ids)
    
    # Re-evaluate org1, idempotency check
    assessments1_re = ApplicabilityEngine.evaluate_organization(org1.id, db_session)
    assert len(assessments1_re) == 1
    # Assessment ID should remain same or old assessment should be replaced, but total count of assessments for this org+reg must be 1
    total_assessments_org1 = db_session.query(RegulatoryApplicabilityAssessment).filter_by(organization_id=org1.id, regulation_id=reg_id).count()
    assert total_assessments_org1 == 1

    total_items_org1 = db_session.query(ApplicabilityReviewItem).filter_by(organization_id=org1.id, regulation_id=reg_id).count()
    assert total_items_org1 == 2
