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
    notifications,
    discovery,
    applicability,
    obligations,
    events,
    monitoring,
    intelligence
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication Domain"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications Domain"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["Organization Discovery"])
api_router.include_router(applicability.router, prefix="/regulatory/applicability", tags=["Regulatory Applicability Domain"])
api_router.include_router(obligations.router, prefix="/regulatory/obligations", tags=["Regulatory Obligation Domain"])
api_router.include_router(events.router, prefix="/compliance/events", tags=["Compliance Trigger Events Domain"])
api_router.include_router(monitoring.router, prefix="/compliance", tags=["Compliance Monitoring & Intelligence Domain"])
api_router.include_router(intelligence.router, prefix="/compliance", tags=["Compliance Intelligence & Defense Pack Domain"])
api_router.include_router(sources.router, prefix="/sources", tags=["Regulatory Intelligence Domain"])
api_router.include_router(regulations.router, prefix="/regulations", tags=["Regulatory Knowledge Domain"])
api_router.include_router(ai_intelligence.router, prefix="/ai", tags=["Compliance Decision Domain"])
api_router.include_router(impact.router, prefix="/impact", tags=["Knowledge Graph Domain"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Compliance Workflow Domain"])
api_router.include_router(tasks.router, prefix="/compliance/tasks", tags=["Compliance Workflow Domain"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["RAG Copilot Domain"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Reporting Domain"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Audit Trail Domain"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["Enterprise Settings"])

