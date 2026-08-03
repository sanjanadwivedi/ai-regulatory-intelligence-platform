from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.domain import Regulation, KnowledgeGraphChain
from app.services.ai_engine import ImpactAgent

from app.services.graph_service import KnowledgeGraphEngine

router = APIRouter()

@router.get("/{reg_id}")
def get_impact_report(
    reg_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    chains = db.query(KnowledgeGraphChain).filter(KnowledgeGraphChain.regulation_id == reg_id).all()
    if not chains:
        return db.query(KnowledgeGraphChain).all()
    return chains

@router.get("/{reg_id}/graph")
def get_impact_graph(
    reg_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get dynamically generated knowledge graph for a specific regulation ID.
    """
    return KnowledgeGraphEngine.get_regulation_graph(reg_id, db=db)

