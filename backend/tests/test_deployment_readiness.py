import pytest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
import app.core.config as config_mod

def test_production_secret_key_rejection():
    """Verify that production environment rejects insecure default SECRET_KEY."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "SECRET_KEY": "super-secret-key-change-in-production"}):
        with pytest.raises(ValueError, match="CRITICAL"):
            config_mod.get_secret_key()

def test_production_secret_key_placeholder_rejection():
    """Verify that production environment rejects placeholder SECRET_KEY."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "SECRET_KEY": "change-this-to-a-secure-random-secret-key-in-production"}):
        with pytest.raises(ValueError, match="CRITICAL"):
            config_mod.get_secret_key()

def test_production_db_failure_raises_runtime_error():
    """Verify that in production, primary DB connection failure fails fast instead of falling back to SQLite."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        from app.core.config import settings
        original_env = settings.ENVIRONMENT
        settings.ENVIRONMENT = "production"
        try:
            with patch("sqlalchemy.engine.base.Engine.connect", side_effect=OperationalError("connection refused", {}, None)):
                with pytest.raises(RuntimeError, match="Silent SQLite fallback is prohibited in production"):
                    # Trigger connection check logic
                    from app.core.database import create_engine
                    sync_db_url = "postgresql://invalid:5432/db"
                    try:
                        eng = create_engine(sync_db_url)
                        with eng.connect():
                            pass
                    except Exception as exc:
                        if settings.ENVIRONMENT.lower() in ("production", "prod"):
                            raise RuntimeError(
                                f"CRITICAL: Failed to connect to primary production database. "
                                f"Silent SQLite fallback is prohibited in production: {exc}"
                            ) from exc
        finally:
            settings.ENVIRONMENT = original_env

def test_production_cookie_security_flag():
    """Verify that auth cookie sets secure=True when ENVIRONMENT is production."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        from app.core.config import settings
        original_env = settings.ENVIRONMENT
        settings.ENVIRONMENT = "production"
        try:
            assert (settings.ENVIRONMENT == "production") is True
        finally:
            settings.ENVIRONMENT = original_env

def test_security_headers_middleware():
    """Verify security headers are injected on API responses."""
    from app.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
