from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import CopilotQueryRequest, CopilotQueryResponse
from app.services.rag_copilot import RAGCopilotService
from app.models.domain import AuditLog
from app.core.limiter import limiter


router = APIRouter()

@router.post("/query", response_model=CopilotQueryResponse)
@limiter.limit("10/minute")
async def query_copilot(
    request: Request,
    req: CopilotQueryRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    res = await RAGCopilotService.query_copilot(req.query, req.regulation_id, db=db)
    
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    user_role = getattr(current_user, "role", "Compliance Officer")

    audit = AuditLog(
        user_name=user_name,
        user_role=user_role,
        action="COPILOT_RAG_QUERY",
        target_type="AI_COPILOT",
        target_id=req.regulation_id,
        details={"query": req.query, "confidence": res["confidence_score"]}
    )
    db.add(audit)
    db.commit()

    return res

