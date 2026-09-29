import pytest
from app.core.config import settings
from app.core.database import engine as app_engine
from app.models.domain import EnterpriseUser

def test_database_isolation_safety(db_session):
    # Verify the test engine is isolated
    sync_db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///")
    assert "pytest_test_only.db" in sync_db_url, "DATABASE_URL not overridden in settings"
    assert "pytest_test_only.db" in str(app_engine.url), "App engine URL not overridden"

    # Add a user to isolated db to ensure it works
    u = EnterpriseUser(id="test-iso", full_name="Test Iso", email="iso@test.com", role="USER")
    db_session.add(u)
    db_session.commit()
    
    assert db_session.query(EnterpriseUser).count() == 1
