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
    evals
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Access Control"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications & Alerts"])
api_router.include_router(sources.router, prefix="/sources", tags=["Regulatory Sources"])
api_router.include_router(regulations.router, prefix="/regulations", tags=["Document Repository"])
api_router.include_router(ai_intelligence.router, prefix="/ai", tags=["AI Document Intelligence"])
api_router.include_router(impact.router, prefix="/impact", tags=["Impact Analysis"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks & Workflows"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["RAG Search & Copilot"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Dashboard Analytics"])
api_router.include_router(audit.router, prefix="/audit-logs", tags=["Security & Audit Logs"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["Enterprise Settings"])
api_router.include_router(evals.router, prefix="/evals", tags=["Golden Evaluation Benchmark"])


