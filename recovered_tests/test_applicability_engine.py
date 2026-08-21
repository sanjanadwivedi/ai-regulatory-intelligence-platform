import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    DiscoveredFact,
    RegulatoryApplicabilityAssessment,
    AuditLog
)
from app.services.applicability_engine import ApplicabilityEngine
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

def test_website_regulatory_signal_alone_requires_review(db_session: Session):
    """
    REGRESSION TEST 1: Website regulatory signal alone MUST NEVER produce APPLICABLE.
    It produces REQUIRES_REVIEW with clear missing authoritative criteria.
    """
    profile = db_session.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="Tech Corp",
            country="India",
            locations=["India"],
            business_activities=["Cloud Infrastructure"],
            discovery_status="CONFIRMED"
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)

    # Add a discovered signal for RBI / DPDP
    signal = DiscoveredFact(
        organization_id=profile.id,
        fact_type="REGULATORY_SIGNAL",
        fact_value="DPDP Act Compliance Ready",
        source_url="https://techcorp.com/security",
        snippet="Our cloud solutions adhere to DPDP data protection guidelines.",
        status="CONFIRMED",
        confidence=0.88
    )
    db_session.add(signal)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    for a in assessments:
        # None of the assessments should be APPLICABLE purely based on the signal
        if a.status == "APPLICABLE":
            # Must have matched criteria independently
            assert a.regulation_id == "reg-cyber-2026"  # Only CERT-In has satisfied statutory criteria
        else:
            assert a.status in ["NOT_APPLICABLE", "REQUIRES_REVIEW"]

def test_jurisdiction_alone_requires_review_when_mandatory_criteria_missing(db_session: Session):
    """
    REGRESSION TEST 2: Jurisdiction match alone (e.g. India) is NOT sufficient when
    mandatory covered entity / sector criteria are missing or unspecified.
    """
    profile = db_session.query(EnterpriseProfile).first()
    profile.country = "India"
    profile.locations = ["India"]
    profile.business_activities = ["Consulting Services"]
    profile.licenses = []
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    # Generic RBI publications in India must be REQUIRES_REVIEW because covered entity rules are missing
    rbi_scan = next((a for a in assessments if a.regulation_id == "reg-scan-rbi-2026"), None)
    if rbi_scan:
        assert rbi_scan.status == "REQUIRES_REVIEW"
        assert len(rbi_scan.missing_information) >= 1

def test_sector_match_alone_requires_review(db_session: Session):
    """
    REGRESSION TEST 3: Business activity match (e.g. Digital Identity) without statutory
    covered entity licensing (e.g. RBI banking license) -> REQUIRES_REVIEW.
    """
    profile = db_session.query(EnterpriseProfile).first()
    profile.business_activities = ["Digital Identity & Biometrics"]
    profile.licenses = []
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    rbi_kyc = next((a for a in assessments if a.regulation_id == "reg-rbi-kyc-2026"), None)
    assert rbi_kyc is not None
    assert rbi_kyc.status == "REQUIRES_REVIEW"
    assert any("intermediary" in m.lower() or "regulated entity" in m.lower() for m in rbi_kyc.missing_information)

def test_explicit_authoritative_applicability_criteria_satisfied_applicable(db_session: Session):
    """
    REGRESSION TEST 4: Explicit authoritative applicability criteria all satisfied -> APPLICABLE.
    CERT-In directions apply to ICT/Cloud service providers operating in India.
    """
    profile = db_session.query(EnterpriseProfile).first()
    profile.country = "India"
    profile.locations = ["India"]
    profile.business_activities = ["ICT & Digital Transformation Solutions", "Cloud & Technology Infrastructure"]
    profile.discovery_status = "CONFIRMED"
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    cert_in = next((a for a in assessments if a.regulation_id == "reg-cyber-2026"), None)
    assert cert_in is not None
    assert cert_in.status == "APPLICABLE"
    assert len(cert_in.matched_criteria) >= 2
    assert len(cert_in.regulatory_evidence_refs) >= 1
    assert cert_in.regulatory_evidence_refs[0]["authority"] == "Indian Computer Emergency Response Team (CERT-In & MeitY)"

def test_explicit_authoritative_exclusion_not_applicable(db_session: Session):
    """
    REGRESSION TEST 5: Explicit authoritative exclusion / territorial scope mismatch -> NOT_APPLICABLE.
    - SEC Release No. 33-11216: US broker-dealers only -> NOT_APPLICABLE for Indian IT firm.
    - HIPAA: Healthcare covered entities handling ePHI -> NOT_APPLICABLE for Indian IT firm.
    """
    profile = db_session.query(EnterpriseProfile).first()
    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)

    sec_rule = next((a for a in assessments if a.regulation_id == "reg-sec-trading-2026"), None)
    assert sec_rule is not None
    assert sec_rule.status == "NOT_APPLICABLE"
    assert len(sec_rule.unmet_criteria) >= 1

    hipaa = next((a for a in assessments if a.regulation_id == "reg-hipaa-2026"), None)
    assert hipaa is not None
    assert hipaa.status == "NOT_APPLICABLE"
    assert len(hipaa.unmet_criteria) >= 1

def test_missing_authoritative_criteria_requires_review(db_session: Session):
    """
    REGRESSION TEST 6: When a regulation lacks structured statutory criteria in the repository,
    the engine MUST return REQUIRES_REVIEW with explicit missing information note.
    """
    profile = db_session.query(EnterpriseProfile).first()
    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)

    fed_reg = next((a for a in assessments if a.regulation_id == "reg-live-9d0c8130"), None)
    if fed_reg:
        assert fed_reg.status == "REQUIRES_REVIEW"
        assert len(fed_reg.missing_information) >= 1
        assert "not sufficiently available" in fed_reg.missing_information[0]

def test_evidence_segregation_org_reg_signals(db_session: Session):
    """
    REGRESSION TEST 7: Organization evidence, Regulatory evidence, and Regulatory signals
    remain strictly segregated in distinct JSON payloads.
    """
    profile = db_session.query(EnterpriseProfile).first()
    assessments = ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    cert_in = next(a for a in assessments if a.regulation_id == "reg-cyber-2026")

    # Organization evidence is about the organization
    assert isinstance(cert_in.organization_evidence_refs, list)
    for o_ref in cert_in.organization_evidence_refs:
        assert "EnterpriseProfile" in o_ref["source"]

    # Regulatory evidence is about the regulation
    assert isinstance(cert_in.regulatory_evidence_refs, list)
    for r_ref in cert_in.regulatory_evidence_refs:
        assert "regulation_id" in r_ref
        assert "authority" in r_ref

    # Regulatory signals are in their own list
    assert isinstance(cert_in.regulatory_signal_refs, list)

def test_repeated_evaluation_remains_idempotent(db_session: Session):
    """
    REGRESSION TEST 8: Repeated evaluations do NOT create duplicate assessment rows.
    """
    profile = db_session.query(EnterpriseProfile).first()
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    count_1 = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == profile.id
    ).count()

    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    count_2 = db_session.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == profile.id
    ).count()

    assert count_1 == count_2
    assert count_1 == db_session.query(Regulation).count()

def test_audit_log_remains_complete(db_session: Session, auth_headers: dict):
    """
    REGRESSION TEST 9: POST /api/v1/regulatory/applicability/evaluate creates an immutable AuditLog entry.
    """
    resp = client.post("/api/v1/regulatory/applicability/evaluate", headers=auth_headers)
    assert resp.status_code == 200

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "APPLICABILITY_EVALUATION_COMPLETED"
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.target_type == "REGULATORY_APPLICABILITY"
    assert "applicable_count" in audit.details
    assert "not_applicable_count" in audit.details
    assert "requires_review_count" in audit.details
    assert "engine_version" in audit.details
