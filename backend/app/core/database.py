import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("sqlite+aiosqlite:///"):
    sync_db_url = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
elif db_url.startswith("postgresql+asyncpg://"):
    sync_db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
else:
    sync_db_url = db_url

connect_args = {"check_same_thread": False, "timeout": 30} if "sqlite" in sync_db_url else {}

try:
    engine = create_engine(sync_db_url, echo=False, connect_args=connect_args)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as exc:
    if settings.ENVIRONMENT.lower() in ("production", "prod"):
        raise RuntimeError(
            f"CRITICAL: Failed to connect to primary production database. "
            f"Silent SQLite fallback is prohibited in production: {exc}"
        ) from exc
    # Development/test fallback to local SQLite if primary database connection fails
    sync_db_url = "sqlite:///./compliance_platform_test6.db"
    engine = create_engine(sync_db_url, echo=False, connect_args={"check_same_thread": False, "timeout": 30})

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
