import os
import logging
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        from pydantic.v1 import BaseSettings

logger = logging.getLogger("compliance_platform.config")

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Regulatory Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./compliance_platform.db")
    SECONDARY_LLM_PROVIDER: str = os.getenv("SECONDARY_LLM_PROVIDER", "")
    SECONDARY_LLM_API_KEY: str = os.getenv("SECONDARY_LLM_API_KEY", "")
    SOURCE_REVERIFY_INTERVAL_DAYS: int = int(os.getenv("SOURCE_REVERIFY_INTERVAL_DAYS", "30"))
    FINRA_MANUAL_UPLOAD_PATH: str = os.getenv("FINRA_MANUAL_UPLOAD_PATH", "./data/finra_manual")

    class Config:

        case_sensitive = True

settings = Settings()

if settings.SECRET_KEY == "super-secret-key-change-in-production":
    logger.warning("SECURITY WARNING: Using default insecure SECRET_KEY. Set SECRET_KEY in .env for production!")
