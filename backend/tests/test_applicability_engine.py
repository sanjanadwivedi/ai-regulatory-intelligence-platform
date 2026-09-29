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
    RegulatoryApplicabilityCriterion,
    ApplicabilityReviewItem,
    DiscoveredFact
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


@pytest.fixture
def base_org(db_session: Session):
    org = EnterpriseProfile(
        id=str(uuid.uuid4()),
        organization_name="Test Enterprise Corp",
        country="India",
        industry_sector="Technology",
        business_activities=[]
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def published_regulation(db_session: Session):
    reg = Regulation(
        id="reg-cloud-safety-2026",
        title="Cloud Safety and Data Hosting Mandate",
        authority="Regulatory Commission",
        status="PUBLISHED",
        publication_date=datetime.date(2026, 1, 1),
        sector="Technology",
        region="India",
        content_text="All cloud hosting providers operating in the jurisdiction must comply.",
        source_url="https://regulator.gov.in/cloud-safety"
    )
    crit = RegulatoryApplicabilityCriterion(
        id=str(uuid.uuid4()),
        regulation_id=reg.id,
        criterion_type="Business Activity Requirement",
        description="Must be a cloud provider",
        evidence_fact_type="BUSINESS_ACTIVITY",
        operator="EQUALS",
        expected_value="cloud provider",
        is_mandatory=True,
        minimum_evidence_strength="DOCUMENTED"
    )
    db_session.add(reg)
    db_session.add(crit)
    db_session.commit()
    return reg


def test_confirmed_true_satisfies_criterion(db_session: Session, base_org, published_regulation):
    # Confirmed TRUE fact satisfies the statutory criterion
    fact = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="TRUE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://testcorp.com/services",
        snippet="TestCorp operates as an enterprise cloud provider."
    )
    db_session.add(fact)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    assert len(assessments) == 1
    ass = assessments[0]
    assert ass.status == "APPLICABLE"
    assert ass.applicability_score >= 0.90
    assert len(ass.matched_criteria) == 1
    assert ass.matched_criteria[0]["result"] == "MATCH"


def test_confirmed_false_does_not_satisfy_criterion(db_session: Session, base_org, published_regulation):
    # Confirmed FALSE fact explicitly excludes the organization from applicability
    fact = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="FALSE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://testcorp.com/about",
        snippet="TestCorp is purely an on-premise consultancy and not a cloud provider."
    )
    db_session.add(fact)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    assert len(assessments) == 1
    ass = assessments[0]
    assert ass.status == "NOT_APPLICABLE"
    assert ass.applicability_score == 0.0
    assert len(ass.unmet_criteria) == 1
    assert ass.unmet_criteria[0]["result"] == "NO_MATCH"


def test_rejected_fact_excluded(db_session: Session, base_org, published_regulation):
    # Human-rejected fact must be completely excluded from applicability evaluation
    fact = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="TRUE",
        status="REJECTED",
        evidence_strength="DOCUMENTED",
        source_url="https://crawler.com/unverified",
        snippet="Unverified claim of cloud operations."
    )
    db_session.add(fact)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    assert len(assessments) == 1
    ass = assessments[0]
    # Since the only fact was rejected, there is no authoritative fact -> REQUIRES_REVIEW
    assert ass.status == "REQUIRES_REVIEW"
    assert len(ass.missing_information) == 1
    assert ass.missing_information[0]["status"] == "MISSING_EVIDENCE"

    # Verifies an open review item is created for the missing evidence
    items = db_session.query(ApplicabilityReviewItem).filter_by(organization_id=base_org.id).all()
    assert len(items) == 1
    assert items[0].status == "OPEN"


def test_pending_fact_cannot_silently_establish_applicability(db_session: Session, base_org, published_regulation):
    # Unverified / PENDING crawler fact must not silently make a regulation APPLICABLE
    fact = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="TRUE",
        status="PENDING",
        evidence_strength="DOCUMENTED",
        source_url="https://crawler.com/candidate",
        snippet="Candidate scraper observation."
    )
    db_session.add(fact)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    assert len(assessments) == 1
    ass = assessments[0]
    assert ass.status == "REQUIRES_REVIEW"
    assert ass.status != "APPLICABLE"


def test_true_false_conflict_produces_conflicting_evidence_and_review(db_session: Session, base_org, published_regulation):
    # Contradictory TRUE and FALSE evidence of sufficient strength must flag CONFLICTING_EVIDENCE
    fact_true = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="TRUE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://source-a.com",
        snippet="Source A confirms cloud provider status."
    )
    fact_false = DiscoveredFact(
        id=str(uuid.uuid4()),
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="FALSE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://source-b.com",
        snippet="Source B refutes cloud provider status."
    )
    db_session.add(fact_true)
    db_session.add(fact_false)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    assert len(assessments) == 1
    ass = assessments[0]
    assert ass.status == "REQUIRES_REVIEW"
    assert len(ass.missing_information) == 1
    assert ass.missing_information[0]["status"] == "CONFLICTING_EVIDENCE"
    assert "conflicting evidence" in ass.missing_information[0]["question"].lower()


def test_repeated_evaluation_determinism(db_session: Session, base_org, published_regulation):
    # Repeated evaluations with contradictory facts must yield deterministic, identical outcomes
    fact1 = DiscoveredFact(
        id="fact-1",
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="FALSE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://source-1.com",
        snippet="Snippet 1"
    )
    fact2 = DiscoveredFact(
        id="fact-2",
        organization_id=base_org.id,
        fact_type="BUSINESS_ACTIVITY",
        fact_value="cloud provider",
        known_state="TRUE",
        status="CONFIRMED",
        evidence_strength="DOCUMENTED",
        source_url="https://source-2.com",
        snippet="Snippet 2"
    )
    db_session.add(fact1)
    db_session.add(fact2)
    db_session.commit()

    run1 = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    run2 = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)

    assert run1[0].status == run2[0].status == "REQUIRES_REVIEW"
    assert run1[0].applicability_score == run2[0].applicability_score
    assert len(run1[0].missing_information) == len(run2[0].missing_information) == 1
    assert run1[0].missing_information[0]["status"] == run2[0].missing_information[0]["status"] == "CONFLICTING_EVIDENCE"


def test_inactive_and_draft_regulations_excluded(db_session: Session, base_org):
    # Inactive, draft, or archived regulations must be excluded from evaluation
    draft_reg = Regulation(
        id="reg-draft-1",
        title="Draft Regulation",
        authority="Authority",
        status="DRAFT",
        publication_date=datetime.date(2026, 1, 1),
        sector="Technology",
        region="India",
        content_text="Draft content"
    )
    archived_reg = Regulation(
        id="reg-archived-1",
        title="Archived Regulation",
        authority="Authority",
        status="ARCHIVED",
        publication_date=datetime.date(2020, 1, 1),
        sector="Technology",
        region="India",
        content_text="Archived content"
    )
    db_session.add(draft_reg)
    db_session.add(archived_reg)
    db_session.commit()

    assessments = ApplicabilityEngine.evaluate_organization(base_org.id, db_session)
    evaluated_reg_ids = [a.regulation_id for a in assessments]
    assert "reg-draft-1" not in evaluated_reg_ids
    assert "reg-archived-1" not in evaluated_reg_ids
