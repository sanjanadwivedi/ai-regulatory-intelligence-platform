import pytest
import uuid
import datetime
from sqlalchemy.orm import Session
from app.core.database import Base, engine, SessionLocal
from app.models.domain import (
    EnterpriseProfile, InternalControl, RegulatoryObligation, 
    ObligationControlMapping, ControlAssessment, DiscoveredFact, AuditLog,
    Regulation, RegulatoryApplicabilityAssessment
)
from app.services.control_engine import ControlEngine

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # clear testing tables to prevent pollution
    db.query(ControlAssessment).delete()
    db.query(ObligationControlMapping).delete()
    db.query(RegulatoryObligation).delete()
    db.query(InternalControl).delete()
    db.query(DiscoveredFact).delete()
    db.query(AuditLog).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

@pytest.fixture(scope="function")
def org_a(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org A Engine", industry_sector="Tech")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture(scope="function")
def org_b(db_session: Session):
    org = EnterpriseProfile(id=str(uuid.uuid4()), organization_name="Org B Engine", industry_sector="Finance")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture(scope="function")
def reg(db_session: Session):
    r = Regulation(id=str(uuid.uuid4()), title="Test Reg Engine", authority="Test", publication_date=datetime.date.today(), sector="Test", region="Test", content_text="Test")
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
def control_a(db_session: Session, org_a):
    c = InternalControl(id=str(uuid.uuid4()), organization_id=org_a.id, control_code="CTRL-A", name="Control A", description="Test", category="Test", owner_department="IT", status="IMPLEMENTED")
    db_session.add(c)
    db_session.commit()
    return c

@pytest.fixture(scope="function")
def map_a(db_session: Session, org_a, ob_a, control_a):
    m = ObligationControlMapping(id=str(uuid.uuid4()), organization_id=org_a.id, obligation_id=ob_a.id, control_id=control_a.id, active=1)
    db_session.add(m)
    db_session.commit()
    return m

def test_applicable_obligation_with_effective_control(db_session: Session, org_a, control_a, map_a):
    control_a.status = "EFFECTIVE"
    db_session.commit()
    
    fact = DiscoveredFact(id=str(uuid.uuid4()), organization_id=org_a.id, fact_type="CONTROL_IMPLEMENTATION", fact_value=control_a.control_code, evidence_strength="AUTHORITATIVE", source_url="test", snippet="test", known_state="TRUE")
    db_session.add(fact)
    db_session.commit()

    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments) == 1
    assert assessments[0].assessment_status == "EFFECTIVE"
    
    posture = ControlEngine.get_obligation_posture(map_a.obligation_id, org_a.id, db_session)
    assert posture == "SATISFIED"

def test_applicable_obligation_without_control(db_session: Session, org_a, ob_a):
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments) == 0
    posture = ControlEngine.get_obligation_posture(ob_a.id, org_a.id, db_session)
    assert posture == "CONTROL_GAP"

def test_mapped_draft_control(db_session: Session, org_a, control_a, map_a):
    control_a.status = "DRAFT"
    db_session.commit()
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].assessment_status == "CONTROL_GAP"

def test_mapped_ineffective_control(db_session: Session, org_a, control_a, map_a):
    control_a.status = "INEFFECTIVE"
    db_session.commit()
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].assessment_status == "INEFFECTIVE"

def test_insufficient_evidence(db_session: Session, org_a, control_a, map_a):
    control_a.status = "EFFECTIVE"
    db_session.commit()
    
    fact = DiscoveredFact(id=str(uuid.uuid4()), organization_id=org_a.id, fact_type="CONTROL_IMPLEMENTATION", fact_value=control_a.control_code, evidence_strength="INFERRED", source_url="test", snippet="test", known_state="TRUE")
    db_session.add(fact)
    db_session.commit()

    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].assessment_status == "CONTROL_REVIEW_REQUIRED"
    assert assessments[0].evidence_summary == "EVIDENCE_INSUFFICIENT"

def test_authoritative_evidence(db_session: Session, org_a, control_a, map_a):
    control_a.status = "EFFECTIVE"
    db_session.commit()
    
    fact = DiscoveredFact(id=str(uuid.uuid4()), organization_id=org_a.id, fact_type="CONTROL_IMPLEMENTATION", fact_value=control_a.control_code, evidence_strength="AUTHORITATIVE", source_url="test", snippet="test", known_state="TRUE")
    db_session.add(fact)
    db_session.commit()

    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].assessment_status == "EFFECTIVE"
    assert assessments[0].evidence_summary == "EVIDENCE_AUTHORITATIVE"

def test_repeated_evaluation_idempotency(db_session: Session, org_a, control_a, map_a):
    assessments1 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments1) == 1
    
    assessments2 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments1[0].id == assessments2[0].id
    
    count = db_session.query(ControlAssessment).filter(ControlAssessment.control_id == control_a.id).count()
    assert count == 1

def test_historical_assessment_immutability(db_session: Session, org_a, control_a, map_a):
    control_a.status = "DRAFT"
    db_session.commit()
    a1 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)[0]
    
    control_a.status = "EFFECTIVE"
    fact = DiscoveredFact(id=str(uuid.uuid4()), organization_id=org_a.id, fact_type="CONTROL_IMPLEMENTATION", fact_value=control_a.control_code, evidence_strength="AUTHORITATIVE", source_url="test", snippet="test", known_state="TRUE")
    db_session.add(fact)
    db_session.commit()
    
    a2 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)[0]
    assert a1.id != a2.id
    assert a1.assessment_status == "CONTROL_GAP"
    assert a2.assessment_status == "EFFECTIVE"
    
    a1_fresh = db_session.query(ControlAssessment).get(a1.id)
    assert a1_fresh.assessment_status == "CONTROL_GAP"

def test_multiple_obligations_sharing_one_control(db_session: Session, org_a, ob_a, control_a, map_a, reg, app_assess_a):
    ob_a2 = RegulatoryObligation(id=str(uuid.uuid4()), regulation_id=reg.id, organization_id=org_a.id, applicability_assessment_id=app_assess_a.id, obligation_code="OB-A-02", title="Obligation A2", description="Test", obligation_type="SECURITY_CONTROL", source_citation="Test", status="ACTIVE")
    db_session.add(ob_a2)
    m2 = ObligationControlMapping(id=str(uuid.uuid4()), organization_id=org_a.id, obligation_id=ob_a2.id, control_id=control_a.id, active=1)
    db_session.add(m2)
    db_session.commit()

    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments) == 1 

def test_cross_tenant_control_isolation(db_session: Session, org_a, org_b, control_a, map_a):
    assessments_b = ControlEngine.evaluate_organization_controls(org_b.id, db_session)
    assert len(assessments_b) == 0

def test_cross_tenant_evidence_isolation(db_session: Session, org_a, org_b, control_a, map_a):
    control_a.status = "EFFECTIVE"
    
    fact = DiscoveredFact(id=str(uuid.uuid4()), organization_id=org_b.id, fact_type="CONTROL_IMPLEMENTATION", fact_value=control_a.control_code, evidence_strength="AUTHORITATIVE", source_url="test", snippet="test", known_state="TRUE")
    db_session.add(fact)
    db_session.commit()

    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].evidence_summary == "NO_EVIDENCE"
    assert assessments[0].assessment_status == "CONTROL_REVIEW_REQUIRED"

def test_requires_review_obligation_ignored(db_session: Session, org_a, ob_a, control_a, map_a):
    ob_a.status = "REQUIRES_REVIEW"
    db_session.commit()
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments) == 0

def test_not_applicable_obligation_ignored(db_session: Session, org_a, ob_a, control_a, map_a):
    ob_a.status = "SUPERSEDED"
    db_session.commit()
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert len(assessments) == 0

def test_audit_log_creation(db_session: Session, org_a, control_a, map_a):
    count_before = db_session.query(AuditLog).filter(AuditLog.organization_id == org_a.id, AuditLog.action == "CONTROL_EVALUATED").count()
    ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    count_after = db_session.query(AuditLog).filter(AuditLog.organization_id == org_a.id, AuditLog.action == "CONTROL_EVALUATED").count()
    assert count_after == count_before + 1

def test_no_duplicate_assessments_when_state_unchanged(db_session: Session, org_a, control_a, map_a):
    a1 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)[0]
    a2 = ControlEngine.evaluate_organization_controls(org_a.id, db_session)[0]
    assert a1.id == a2.id

def test_retired_control_handling(db_session: Session, org_a, control_a, map_a):
    control_a.status = "RETIRED"
    db_session.commit()
    assessments = ControlEngine.evaluate_organization_controls(org_a.id, db_session)
    assert assessments[0].assessment_status == "CONTROL_GAP"
