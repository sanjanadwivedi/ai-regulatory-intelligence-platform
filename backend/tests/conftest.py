import os
import pytest

# 1. HARD OVERRIDE BEFORE APPLICATION MODULES ARE IMPORTED
# This ensures that when app.core.config and app.core.database are imported,
# they see the test database URL.
TEST_DATABASE_URL_ENV = "sqlite+aiosqlite:///./pytest_test_only.db"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL_ENV

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Now it is safe to import application modules
from app.core.config import settings
from app.core.database import Base, engine as app_engine, SessionLocal, get_db
from app.main import app

# 2. HARD SAFETY GUARD
sync_db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///")
if "pytest_test_only.db" not in sync_db_url:
    raise RuntimeError(f"FATAL: DATABASE_URL is not set to pytest_test_only.db (got {sync_db_url}). Aborting to protect application database.")

app_sync_db_url = str(app_engine.url)
if "pytest_test_only.db" not in app_sync_db_url:
    raise RuntimeError(f"FATAL: Application engine connected to {app_sync_db_url}. Aborting to protect application database.")

# 3. Dedicated test engine
from sqlalchemy.pool import NullPool
TEST_SYNC_DATABASE_URL = "sqlite:///./pytest_test_only.db"
test_engine = create_engine(TEST_SYNC_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 4. Dependency Override for FastAPI Routes
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# 5. Centralized Test Fixtures
@pytest.fixture(scope="function", autouse=True)
def isolated_clean_db():
    """Ensure a clean database state for each test using isolated test engine."""
    # Absolute safety check before dropping tables
    if "pytest_test_only.db" not in str(test_engine.url):
        raise RuntimeError("Test engine is not isolated! Aborting drop_all.")
    
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    """Provides an isolated database session for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
