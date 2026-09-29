import pytest
import datetime
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.domain import EnterpriseProfile, Regulation, KnowledgeGraphChain
from app.core.security import get_current_user

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./pytest_test_only.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Dummy user override
class DummyUser:
    id = "test-user-id"
    organization_id = "test-org-id"
    role = "compliance_officer"
    email = "test@example.com"
    full_name = "Test User"

def override_get_current_user():
    return DummyUser()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    # Set overrides inside fixture to avoid global pollution
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # We do NOT drop/create tables here because conftest.py's isolated_clean_db handles it!
    yield
    
    # Clean up overrides
    app.dependency_overrides.clear()

def test_discovery_no_fabricated_facts():
    # Attempt to start discovery on a domain that doesn't yield company facts
    response = client.post("/api/v1/discovery/start", json={"website_url": "https://example-unknown.com"})
    assert response.status_code == 200 or response.status_code == 422
    
    db = TestingSessionLocal()
    # If a profile was created, check that facts are empty/Unknown, not fabricated.
    # Note: EnterpriseProfile has no 'organization_id' column (its PK is 'id').
    # The test DB is isolated and clean, so simply fetch the most recently created profile.
    profile = db.query(EnterpriseProfile).order_by(EnterpriseProfile.created_at.desc()).first()
    if profile:
        assert profile.industry_sector == "Unknown", (
            f"industry_sector must be 'Unknown' for an unreachable host, got: {profile.industry_sector!r}"
        )
        assert profile.departments in (None, [], []), (
            f"departments must be empty or None for an unreachable host, got: {profile.departments!r}"
        )
        # country can be "" or None when no data was discovered
        assert profile.country in (None, ""), (
            f"country must be None or '' for an unreachable host, got: {profile.country!r}"
        )
    db.close()

def test_no_hardcoded_deadlines_in_ai_engine():
    from app.services.ai_engine import RecommendationAgent
    # Pass chains with no explicit deadline in ORM
    chains = [{"requirement_id": "req-1", "control_code": "CTRL-01"}]
    tasks = RecommendationAgent.generate_recommendations(chains=chains, persisted_requirements=[])
    
    assert len(tasks) == 1
    assert tasks[0]["due_date"] is None, "Fallback deadline should be None, not 30 days"

def test_regulations_no_automatic_analyzed_status():
    db = TestingSessionLocal()
    # Create test regulation directly
    reg_id = f"reg-{uuid.uuid4().hex[:8]}"
    reg = Regulation(
        id=reg_id,
        title="Test Reg",
        authority="Test Auth",
        publication_date=datetime.date.today(),
        sector="Finance",
        region="US",
        content_text="Test content",
        status="INGESTED"
    )
    db.add(reg)
    db.commit()

    # Call an endpoint that might process it, e.g., create_regulation which uses AI
    # Actually, we can just test if the create_regulation endpoint sets it to ANALYZED
    response = client.post("/api/v1/regulations", json={
        "title": "New Reg",
        "authority": "New Auth",
        "sector": "Tech",
        "content_text": "New content",
        "publication_date": "2026-09-16",
        "region": "Global"
    })
    
    assert response.status_code == 200
    reg_data = response.json()
    assert reg_data["status"] != "ANALYZED", "Regulation should not be automatically marked as ANALYZED by AI"
    db.close()
