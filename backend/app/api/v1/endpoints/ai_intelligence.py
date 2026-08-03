from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.domain import Regulation
from app.services.ai_engine import MultiAgentAIOrchestrator
from app.core.limiter import limiter


router = APIRouter()

@router.get("/{reg_id}/summary")
@limiter.limit("10/minute")
def get_ai_summary(
    request: Request,
    reg_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    reg = db.query(Regulation).filter(Regulation.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Regulation document not found")
    
    return MultiAgentAIOrchestrator.process_regulation(
        reg.title, reg.authority, reg.sector, reg.content_text
    )

