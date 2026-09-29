import os
import secrets
import logging
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        from pydantic.v1 import BaseSettings

logger = logging.getLogger("compliance_platform.config")

def get_secret_key() -> str:
    """Get or generate a secure SECRET_KEY."""
    env_key = os.getenv("SECRET_KEY")
    insecure_defaults = {
        "change-this-to-a-secure-random-secret-key-in-production",
        "super-secret-key-change-in-production"
    }
    if env_key and env_key not in insecure_defaults:
        return env_key
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("❌ CRITICAL: SECRET_KEY must be set to a secure secret in production environment!")
    # Development fallback
    return env_key or "super-secret-key-change-in-production"

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Regulatory Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = get_secret_key()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./compliance_platform_test6.db")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    SECONDARY_LLM_PROVIDER: str = os.getenv("SECONDARY_LLM_PROVIDER", "")
    SECONDARY_LLM_API_KEY: str = os.getenv("SECONDARY_LLM_API_KEY", "")
    SOURCE_REVERIFY_INTERVAL_DAYS: int = int(os.getenv("SOURCE_REVERIFY_INTERVAL_DAYS", "30"))
    FINRA_MANUAL_UPLOAD_PATH: str = os.getenv("FINRA_MANUAL_UPLOAD_PATH", "./data/finra_manual")

    class Config:
        case_sensitive = True

settings = Settings()

if settings.ENVIRONMENT == "production" and settings.SECRET_KEY == "super-secret-key-change-in-production":
    raise ValueError("❌ CRITICAL: Change SECRET_KEY before production deployment!")
elif settings.SECRET_KEY == "super-secret-key-change-in-production":
    logger.warning("SECURITY WARNING: Using default insecure SECRET_KEY. Set SECRET_KEY in .env for production!")

if settings.ENVIRONMENT == "production" and ("localhost" in settings.FRONTEND_URL or "127.0.0.1" in settings.FRONTEND_URL):
    logger.warning("SECURITY WARNING: FRONTEND_URL points to localhost in production mode (%s). Set FRONTEND_URL to your public domain!", settings.FRONTEND_URL)

