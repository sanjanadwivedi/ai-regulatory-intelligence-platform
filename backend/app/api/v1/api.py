from fastapi import APIRouter
from app.api.v1.endpoints import (
    sources,
    regulations,
    ai_intelligence,
    impact,
    tasks,
    copilot,
    analytics,
    audit,
    enterprise,
    auth,
    notifications
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication Domain"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications Domain"])
api_router.include_router(sources.router, prefix="/sources", tags=["Regulatory Intelligence Domain"])
api_router.include_router(regulations.router, prefix="/regulations", tags=["Regulatory Knowledge Domain"])
api_router.include_router(ai_intelligence.router, prefix="/ai", tags=["Compliance Decision Domain"])
api_router.include_router(impact.router, prefix="/impact", tags=["Knowledge Graph Domain"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Compliance Workflow Domain"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["RAG Copilot Domain"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Reporting Domain"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Trail Domain"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["Enterprise Settings"])

