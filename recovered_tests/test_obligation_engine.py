import pytest
import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    DiscoveredFact,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    AuditLog
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.obligation_engine import ObligationEngine
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

@pytest.fixture(scope="function")
def setup_org_and_assessments(db_session: Session):
    profile = db_session.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="NEC India",
            country="India",
            locations=["India", "Mumbai", "Noida"],
            business_activities=["ICT & Digital Transformation Solutions", "Cloud & Technology Infrastructure", "Digital Identity & Biometrics"],
            discovery_status="CONFIRMED"
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)
    else:
        profile.organization_name = "NEC India"
        profile.country = "India"
        profile.locations = ["India", "Mumbai", "Noida"]
        profile.business_activities = ["ICT & Digital Transformation Solutions", "Cloud & Technology Infrastructure", "Digital Identity & Biometrics"]
        profile.discovery_status = "CONFIRMED"
        db_session.commit()

    # Run applicability evaluation first
    ApplicabilityEngine.evaluate_organization(profile.id, db_session)
    return profile

def test_applicable_assessment_generates_obligations(db_session: Session, setup_org_and_assessments):
    """
    TEST 1: APPLICABLE assessment (CERT-In) generates authoritative RegulatoryObligation records.
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    
    cert_in_obs = [o for o in obligations if o.regulation_id == "reg-cyber-2026"]
    assert len(cert_in_obs) == 4
    for ob in cert_in_obs:
        assert ob.status == "ACTIVE"
        assert ob.organization_id == profile.id
        assert ob.source_citation.startswith("Direction")
        assert "70B(6)" in ob.source_citation
        assert ob.authoritative_source_url is not None

def test_not_applicable_generates_zero_obligations(db_session: Session, setup_org_and_assessments):
    """
    TEST 2: NOT_APPLICABLE regulations (HIPAA, SEC Release) generate ZERO obligations.
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    
    hipaa_obs = [o for o in obligations if o.regulation_id == "reg-hipaa-2026"]
    assert len(hipaa_obs) == 0

    sec_obs = [o for o in obligations if o.regulation_id == "reg-sec-trading-2026"]
    assert len(sec_obs) == 0

def test_requires_review_generates_zero_active_obligations(db_session: Session, setup_org_and_assessments):
    """
    TEST 3: REQUIRES_REVIEW regulations (RBI KYC, SRVAs, Publications) generate ZERO ACTIVE obligations.
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    
    rbi_obs = [o for o in obligations if o.regulation_id == "reg-rbi-kyc-2026" and o.status == "ACTIVE"]
    assert len(rbi_obs) == 0

    srva_obs = [o for o in obligations if o.regulation_id == "reg-scan-rbi-2026" and o.status == "ACTIVE"]
    assert len(srva_obs) == 0

def test_regulatory_signal_cannot_create_obligation(db_session: Session, setup_org_and_assessments):
    """
    TEST 4: Discovered website regulatory signals MUST NEVER independently create an obligation.
    """
    profile = setup_org_and_assessments
    # Add a mock DPDP regulatory signal
    signal = DiscoveredFact(
        organization_id=profile.id,
        fact_type="REGULATORY_SIGNAL",
        fact_value="DPDP Act Compliance Platform",
        source_url="https://in.nec.com/privacy",
        snippet="We comply with DPDP frameworks.",
        status="CONFIRMED",
        confidence=0.90
    )
    db_session.add(signal)
    db_session.commit()

    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    # Ensure no obligation exists for DPDP purely from the signal
    dpdp_obs = [o for o in obligations if "dpdp" in o.title.lower()]
    assert len(dpdp_obs) == 0

def test_missing_authoritative_text_does_not_create_active_obligation(db_session: Session, setup_org_and_assessments):
    """
    TEST 5: If a hypothetical regulation is APPLICABLE but lacks structured statutory text,
    it MUST NOT create an ACTIVE obligation with hallucinated terms.
    """
    profile = setup_org_and_assessments
    # Create a generic applicable regulation with empty content
    dummy_reg = Regulation(
        id="reg-dummy-applicable",
        title="Generic Cyber Circular",
        authority="Telecom Authority",
        publication_date=datetime.date(2026, 1, 1),
        sector="Technology & Cloud Security",
        region="India",
        content_text="Generic circular without obligation text."
    )
    db_session.add(dummy_reg)
    db_session.commit()

    # Create an APPLICABLE assessment for it
    dummy_assess = RegulatoryApplicabilityAssessment(
        organization_id=profile.id,
        regulation_id=dummy_reg.id,
        status="APPLICABLE",
        applicability_score=0.90,
        rationale="Hypothetical applicable regulation"
    )
    db_session.add(dummy_assess)
    db_session.commit()

    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    dummy_obs = [o for o in obligations if o.regulation_id == dummy_reg.id]
    assert len(dummy_obs) == 1
    assert dummy_obs[0].status == "REQUIRES_REVIEW"
    assert dummy_obs[0].status != "ACTIVE"
    assert dummy_obs[0].missing_information is not None

def test_no_hallucinated_deadline_or_frequency(db_session: Session, setup_org_and_assessments):
    """
    TEST 6 & 7: Due rules and frequencies strictly mirror statutory text (e.g. 6 hours, 180 days).
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    incident_ob = next(o for o in obligations if o.obligation_code == "OBL-CERTIN-INCIDENT-6H")
    assert "6 hours" in incident_ob.due_rule
    assert incident_ob.frequency == "UPON_INCIDENT"

    log_ob = next(o for o in obligations if o.obligation_code == "OBL-CERTIN-LOGS-180D")
    assert "180 days" in log_ob.due_rule
    assert log_ob.frequency == "CONTINUOUS"

def test_authoritative_citation_and_source_required(db_session: Session, setup_org_and_assessments):
    """
    TEST 8 & 9: Every ACTIVE obligation contains authoritative citation and source URL.
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    for ob in obligations:
        if ob.status == "ACTIVE":
            assert ob.source_citation is not None
            assert len(ob.source_citation) > 5
            assert ob.authoritative_source_url is not None
            assert ob.authoritative_source_url.startswith("http")

def test_organization_and_regulatory_evidence_are_separate(db_session: Session, setup_org_and_assessments):
    """
    TEST 10: Organization evidence and regulatory evidence remain strictly segregated.
    """
    profile = setup_org_and_assessments
    obligations = ObligationEngine.generate_obligations(profile.id, db_session)
    for ob in obligations:
        assert isinstance(ob.organization_evidence_refs, list)
        assert isinstance(ob.regulatory_evidence_refs, list)
        assert ob.organization_evidence_refs != ob.regulatory_evidence_refs

def test_generation_is_idempotent_no_duplicates(db_session: Session, setup_org_and_assessments):
    """
    TEST 12, 13, 15: Calling generate_obligations multiple times produces identical counts without duplicates.
    """
    profile = setup_org_and_assessments
    obs_1 = ObligationEngine.generate_obligations(profile.id, db_session)
    count_1 = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == profile.id).count()

    obs_2 = ObligationEngine.generate_obligations(profile.id, db_session)
    count_2 = db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == profile.id).count()

    assert count_1 == count_2
    assert len(obs_1) == len(obs_2)

def test_audit_log_created_on_generation(db_session: Session, auth_headers: dict, setup_org_and_assessments):
    """
    TEST 14: POST /api/v1/regulatory/obligations/generate creates an immutable AuditLog entry.
    """
    resp = client.post("/api/v1/regulatory/obligations/generate", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0

    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "OBLIGATIONS_GENERATED"
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.target_type == "REGULATORY_OBLIGATION"
    assert "active_obligations_count" in audit.details
    assert "engine_version" in audit.details

def test_get_obligations_api_endpoints(auth_headers: dict, setup_org_and_assessments):
    """
    TEST: GET endpoints support listing with filters and detail lookup.
    """
    # Ensure obligations are generated first
    client.post("/api/v1/regulatory/obligations/generate", headers=auth_headers)

    resp = client.get("/api/v1/regulatory/obligations?status=ACTIVE", headers=auth_headers)
    assert resp.status_code == 200
    active_obs = resp.json()
    assert len(active_obs) >= 4

    first_id = active_obs[0]["id"]
    detail_resp = client.get(f"/api/v1/regulatory/obligations/{first_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == first_id
    assert "source_citation" in detail
    assert "due_rule" in detail
