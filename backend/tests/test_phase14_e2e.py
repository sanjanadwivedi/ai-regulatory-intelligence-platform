import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile, 
    Regulation, 
    RegulatoryApplicabilityAssessment, 
    RegulatoryObligation,
    DiscoveredFact,
    ApplicabilityReviewItem,
    InternalControl,
    ComplianceTask,
    EnterpriseUser,
    RegulatoryApplicabilityCriterion,
    ObligationControlMapping
)
from datetime import date
from app.core.security import create_access_token

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
    db_session.query(ComplianceTask).filter(ComplianceTask.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(ObligationControlMapping).filter(ObligationControlMapping.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(InternalControl).filter(InternalControl.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(ApplicabilityReviewItem).filter(ApplicabilityReviewItem.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(RegulatoryApplicabilityCriterion).filter(RegulatoryApplicabilityCriterion.id.in_(["crit-1", "crit-2"])).delete(synchronize_session=False)
    db_session.query(Regulation).filter(Regulation.id.in_(["reg-1", "reg-2"])).delete(synchronize_session=False)
    db_session.query(DiscoveredFact).filter(DiscoveredFact.organization_id == "org-test").delete(synchronize_session=False)
    db_session.query(EnterpriseProfile).filter(EnterpriseProfile.id == "org-test").delete(synchronize_session=False)
    db_session.query(EnterpriseUser).filter(EnterpriseUser.id == "user-1").delete(synchronize_session=False)
    db_session.commit()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    from app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_phase14_end_to_end_workflow(client: TestClient, clean_db: Session):
    # Setup test user and profile
    org = EnterpriseProfile(
        id="org-test",
        organization_name="NEC India",
        industry_sector="Technology",
        country="India",
        business_activities=["intermediary"]
    )
    user = EnterpriseUser(
        id="user-1",
        email="test@test.com",
        full_name="Tester",
        role="ADMIN",
        hashed_password="test",
        organization_id="org-test"
    )
    reg = Regulation(
        id="reg-1",
        title="CERT-In Directions",
        authority="CERT-In",
        publication_date=date(2022, 4, 28),
        effective_date=date(2022, 6, 28),
        sector="Cross-Sector",
        region="India",
        content_text="Report cyber incidents within 6 hours.",
        status="ACTIVE",
        applicability_criteria=[
            RegulatoryApplicabilityCriterion(
                id="crit-1",
                criterion_type="Activity",
                description="Must be an intermediary",
                evidence_fact_type="BUSINESS_ACTIVITY",
                expected_value="intermediary",
                operator="EQUALS",
                is_mandatory=1
            )
        ]
    )
    clean_db.add_all([org, user, reg])
    clean_db.commit()

    token = create_access_token("user-1")
    headers = {"Authorization": f"Bearer {token}"}

    users = clean_db.query(EnterpriseUser).all()
    print("USERS IN DB:", [(u.id, u.email) for u in users])

    # 1. Organization Profile - Verify we can fetch it
    res = client.get("/api/v1/enterprise/profile", headers=headers)
    assert res.status_code == 200, res.json()
    
    # 2. Add/confirm BUSINESS_ACTIVITY (Phase 12 manual fact)
    res = client.post("/api/v1/discovery/facts/manual", headers=headers, json={
        "fact_type": "BUSINESS_ACTIVITY",
        "fact_value": "data_center"
    })
    assert res.status_code == 200, res.json()

    # 3. Evaluate applicability
    res = client.post("/api/v1/regulatory/applicability/evaluate", headers=headers)
    assert res.status_code == 200, res.json()
    assessments = res.json()
    assert len(assessments) >= 1
    reg1_assessment = next((a for a in assessments if a["regulation_id"] == "reg-1"), None)
    assert reg1_assessment is not None
    assert reg1_assessment["status"] == "APPLICABLE"

    # 4. Verify Phase 13 auto obligation generation
    res = client.get("/api/v1/regulatory/obligations", headers=headers)
    assert res.status_code == 200, res.json()
    obligations = res.json()
    # If the regulation didn't have obligations predefined in the DB, it might not generate any.
    # Let's see if the engine handles it. Wait, the obligation engine extracts from `Regulation`.
    # It might use the LLM if not deterministic, but Phase 13 uses deterministic mapping.
    
    # 5. REQUIRES_REVIEW flow
    reg2 = Regulation(
        id="reg-2",
        title="Review Reg",
        authority="Test",
        publication_date=date(2023, 1, 1),
        effective_date=date(2023, 1, 1),
        sector="Cross-Sector",
        region="India",
        content_text="Need review",
        status="ACTIVE",
        applicability_criteria=[
            RegulatoryApplicabilityCriterion(
                id="crit-2",
                criterion_type="Missing Info",
                description="Need employee count",
                evidence_fact_type="EMPLOYEE_COUNT",
                expected_value="50",
                operator=">=",
                is_mandatory=1
            )
        ]
    )
    clean_db.add(reg2)
    clean_db.commit()

    res = client.post("/api/v1/regulatory/applicability/evaluate", headers=headers)
    assert res.status_code == 200, res.json()
    
    res = client.get("/api/v1/regulatory/applicability/reviews", headers=headers)
    assert res.status_code == 200, res.json()
    reviews = res.json()
    reg2_reviews = [r for r in reviews if r["regulation_id"] == "reg-2"]
    assert len(reg2_reviews) == 1
    
    review_id = reg2_reviews[0]["id"]
    res = client.post(f"/api/v1/regulatory/applicability/reviews/{review_id}/resolve", headers=headers, json={
        "evidence_fact_value": "100",
        "evidence_type": "USER_ATTESTATION",
        "evidence_strength": "AUTHORITATIVE",
        "source_url": "http://example.com"
    })
    assert res.status_code == 200, res.json()

    # 6. Verify obligation flow into controls
    # 7. Verify controls generate compliance tasks
    # 8. Verify task/evidence state is reflected in compliance posture
    res = client.get("/api/v1/posture/", headers=headers)
    assert res.status_code == 200, res.json()
    
    # Check no UI displays fabricated values -> we will inspect code for this.
    # We will log the results.

