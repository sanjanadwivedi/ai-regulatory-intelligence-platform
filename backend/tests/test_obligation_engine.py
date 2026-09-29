import pytest
import uuid
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.domain import (
    Base,
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    AuditLog
)
from app.services.obligation_engine import ObligationEngine


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
def test_org(db_session: Session):
    org = EnterpriseProfile(
        id=str(uuid.uuid4()),
        organization_name="FinTech Solutions Pvt Ltd",
        country="India",
        industry_sector="Financial Services",
        business_activities=["intermediary", "payment_aggregator"]
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def certin_regulation(db_session: Session):
    reg = Regulation(
        id="reg-cyber-2026",
        title="CERT-In Cybersecurity Directions 2022",
        authority="CERT-In",
        doc_number="Direction No. 20(3)/2022-CERT-In",
        status="ACTIVE",
        publication_date=datetime.date(2022, 4, 28),
        effective_date=datetime.date(2022, 6, 27),
        sector="Cross-Sector",
        region="India",
        content_text="Directions under sub-section (6) of section 70B of the IT Act, 2000.",
        source_url="https://www.cert-in.org.in/Directions70B.jsp"
    )
    db_session.add(reg)
    db_session.commit()
    return reg


@pytest.fixture
def generic_regulation(db_session: Session):
    reg = Regulation(
        id="reg-dpdp-2026",
        title="Digital Personal Data Protection Act Rules",
        authority="Data Protection Board",
        doc_number="DPDP-2023-SEC8",
        status="ACTIVE",
        publication_date=datetime.date(2026, 1, 1),
        effective_date=datetime.date(2026, 6, 1),
        sector="Cross-Sector",
        region="India",
        content_text="Processing of digital personal data within the territory of India.",
        source_url="https://dpb.gov.in/rules"
    )
    db_session.add(reg)
    db_session.commit()
    return reg


def test_certin_extracts_authoritative_structured_obligations(db_session: Session, test_org, certin_regulation):
    # Setup APPLICABLE assessment for CERT-In
    assessment = RegulatoryApplicabilityAssessment(
        id=str(uuid.uuid4()),
        organization_id=test_org.id,
        regulation_id=certin_regulation.id,
        status="APPLICABLE",
        applicability_score=0.95,
        rationale="Operating as intermediary in India."
    )
    db_session.add(assessment)
    db_session.commit()

    obs = ObligationEngine.generate_obligations(test_org.id, db_session)
    assert len(obs) == 4

    codes = {o.obligation_code for o in obs}
    assert "OBL-CERTIN-INCIDENT-6H" in codes
    assert "OBL-CERTIN-LOGS-180D" in codes
    assert "OBL-CERTIN-NTP-SYNC" in codes
    assert "OBL-CERTIN-POC-DESIGNATION" in codes

    # All CERT-In obligations must be ACTIVE and have statutory citations without fake dates
    for o in obs:
        assert o.status == "ACTIVE"
        assert o.source_citation is not None
        assert "70B(6)" in o.source_citation
        assert o.organization_id == test_org.id
        assert o.regulation_id == certin_regulation.id

    # 6-hour incident reporting must have the exact deterministic trigger
    incident_ob = next(o for o in obs if o.obligation_code == "OBL-CERTIN-INCIDENT-6H")
    assert incident_ob.trigger_type == "INCIDENT_DETECTED"
    assert incident_ob.trigger_offset_value == 6
    assert incident_ob.trigger_offset_unit == "HOURS"

    # Audit log was created
    audit = db_session.query(AuditLog).filter_by(target_id=test_org.id, action="OBLIGATIONS_GENERATED").first()
    assert audit is not None
    assert audit.details["active_obligations_count"] == 4


def test_unstructured_applicable_regulation_produces_review_obligation_no_fake_deadline(db_session: Session, test_org, generic_regulation):
    # For an applicable regulation without structured text, create a REQUIRES_REVIEW placeholder
    assessment = RegulatoryApplicabilityAssessment(
        id=str(uuid.uuid4()),
        organization_id=test_org.id,
        regulation_id=generic_regulation.id,
        status="APPLICABLE",
        applicability_score=0.95,
        rationale="Data fiduciary operating in India."
    )
    db_session.add(assessment)
    db_session.commit()

    obs = ObligationEngine.generate_obligations(test_org.id, db_session)
    assert len(obs) == 1
    ob = obs[0]

    assert ob.status == "REQUIRES_REVIEW"
    assert ob.due_rule is None
    assert ob.trigger_type is None
    assert ob.trigger_offset_value is None
    assert ob.missing_information is not None

    # Must NOT leak CERT-In URLs or references
    assert "cert-in" not in (ob.authoritative_source_url or "").lower()
    assert "cert-in" not in (ob.source_citation or "").lower()


def test_not_applicable_assessment_produces_no_active_obligations(db_session: Session, test_org, certin_regulation):
    # An assessment marked NOT_APPLICABLE must not generate active obligations
    assessment = RegulatoryApplicabilityAssessment(
        id=str(uuid.uuid4()),
        organization_id=test_org.id,
        regulation_id=certin_regulation.id,
        status="NOT_APPLICABLE",
        applicability_score=0.0,
        rationale="Exempted foreign entity without Indian nexus."
    )
    db_session.add(assessment)
    db_session.commit()

    obs = ObligationEngine.generate_obligations(test_org.id, db_session)
    assert len(obs) == 0

    active_count = db_session.query(RegulatoryObligation).filter_by(
        organization_id=test_org.id,
        status="ACTIVE"
    ).count()
    assert active_count == 0


def test_superseded_obligations_when_applicability_transitions_away(db_session: Session, test_org, certin_regulation):
    # Transitioning an assessment from APPLICABLE to NOT_APPLICABLE must supersede existing obligations
    assessment = RegulatoryApplicabilityAssessment(
        id=str(uuid.uuid4()),
        organization_id=test_org.id,
        regulation_id=certin_regulation.id,
        status="APPLICABLE",
        applicability_score=0.95,
        rationale="Intermediary in India."
    )
    db_session.add(assessment)
    db_session.commit()

    obs = ObligationEngine.generate_obligations(test_org.id, db_session)
    assert len(obs) == 4
    assert all(o.status == "ACTIVE" for o in obs)

    # Now change assessment to NOT_APPLICABLE
    assessment.status = "NOT_APPLICABLE"
    db_session.commit()

    obs_after = ObligationEngine.generate_obligations(test_org.id, db_session)
    assert len(obs_after) == 0

    superseded = db_session.query(RegulatoryObligation).filter_by(
        organization_id=test_org.id,
        status="SUPERSEDED"
    ).all()
    assert len(superseded) == 4


def test_idempotent_obligation_extraction(db_session: Session, test_org, certin_regulation):
    # Repeated calls must not duplicate obligations
    assessment = RegulatoryApplicabilityAssessment(
        id=str(uuid.uuid4()),
        organization_id=test_org.id,
        regulation_id=certin_regulation.id,
        status="APPLICABLE",
        applicability_score=0.95,
        rationale="Intermediary in India."
    )
    db_session.add(assessment)
    db_session.commit()

    run1 = ObligationEngine.generate_obligations(test_org.id, db_session)
    run2 = ObligationEngine.generate_obligations(test_org.id, db_session)

    assert len(run1) == len(run2) == 4
    total_in_db = db_session.query(RegulatoryObligation).filter_by(organization_id=test_org.id).count()
    assert total_in_db == 4
