from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import AuditLog
from app.schemas.schemas import AuditLogResponse

router = APIRouter()

@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()

