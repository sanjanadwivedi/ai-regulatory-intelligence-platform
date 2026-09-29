import pytest
import datetime
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.domain import (
    Base,
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    ApplicabilityReviewItem,
    RegulatoryApplicabilityCriterion,
    RegulatoryObligation
)
from app.services.applicability_engine import ApplicabilityEngine

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

def test_regulation_with_structured_criteria_missing_fact(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org", industry_sector="Tech", departments=[])
    reg = Regulation(id=str(uuid.uuid4()), title="Reg A", authority="Auth", status="PUBLISHED", publication_date=datetime.date.today(), sector="Tech", region="US", content_text="Content", source_url="http://test.com")
    
    crit = RegulatoryApplicabilityCriterion(
        id=str(uuid.uuid4()),
        regulation_id=reg.id,
        criterion_type="ACTIVITY",
        description="Do you do X?",
        operator="EQUALS",
        expected_value="TRUE",
        evidence_fact_type="DOES_X",
        is_mandatory=1
    )
    
    db_session.add(org)
    db_session.add(reg)
    db_session.add(crit)
    db_session.commit()
    
    assessments = ApplicabilityEngine.evaluate_organization(org.id, db_session)
    assert len(assessments) == 1
    assert assessments[0].status == "REQUIRES_REVIEW"
    
    items = db_session.query(ApplicabilityReviewItem).filter_by(assessment_id=assessments[0].id).all()
    assert len(items) == 1
    assert items[0].criterion_id == crit.id
    assert items[0].status == "OPEN"

def test_regulation_with_no_structured_criteria(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org", industry_sector="Tech", departments=[])
    reg = Regulation(id=str(uuid.uuid4()), title="SRVA Equivalent", authority="Auth", status="PUBLISHED", publication_date=datetime.date.today(), sector="Tech", region="US", content_text="Content", source_url="http://test.com")
    
    db_session.add(org)
    db_session.add(reg)
    db_session.commit()
    
    assessments = ApplicabilityEngine.evaluate_organization(org.id, db_session)
    assert len(assessments) == 1
    assert assessments[0].status == "REQUIRES_REVIEW"
    
    items = db_session.query(ApplicabilityReviewItem).filter_by(assessment_id=assessments[0].id).all()
    assert len(items) == 1
    assert items[0].criterion_id == "missing"
    assert items[0].status == "OPEN"
    assert items[0].required_fact == "N/A"
    
    obs = db_session.query(RegulatoryObligation).filter_by(organization_id=org.id).all()
    assert len(obs) == 0

def test_rerunning_assessment_is_idempotent(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org", industry_sector="Tech", departments=[])
    reg = Regulation(id=str(uuid.uuid4()), title="SRVA Equivalent", authority="Auth", status="PUBLISHED", publication_date=datetime.date.today(), sector="Tech", region="US", content_text="Content", source_url="http://test.com")
    
    db_session.add(org)
    db_session.add(reg)
    db_session.commit()
    
    ApplicabilityEngine.evaluate_organization(org.id, db_session)
    items1 = db_session.query(ApplicabilityReviewItem).all()
    assert len(items1) == 1
    
    ApplicabilityEngine.evaluate_organization(org.id, db_session)
    items2 = db_session.query(ApplicabilityReviewItem).all()
    assert len(items2) == 1
    assert items1[0].id == items2[0].id

def test_tenant_isolation(db_session: Session):
    org1 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org 1", industry_sector="Tech", departments=[])
    org2 = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org 2", industry_sector="Tech", departments=[])
    reg = Regulation(id=str(uuid.uuid4()), title="SRVA Equivalent", authority="Auth", status="PUBLISHED", publication_date=datetime.date.today(), sector="Tech", region="US", content_text="Content", source_url="http://test.com")
    
    db_session.add(org1)
    db_session.add(org2)
    db_session.add(reg)
    db_session.commit()
    
    ApplicabilityEngine.evaluate_organization(org1.id, db_session)
    ApplicabilityEngine.evaluate_organization(org2.id, db_session)
    
    items = db_session.query(ApplicabilityReviewItem).all()
    assert len(items) == 2
    assert items[0].organization_id != items[1].organization_id
