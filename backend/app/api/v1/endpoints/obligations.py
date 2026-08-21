import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryObligation,
    EnterpriseUser
)
from app.schemas.schemas import RegulatoryObligationOut
from app.services.obligation_engine import ObligationEngine

logger = logging.getLogger("compliance_platform.api.obligations")
router = APIRouter()

def _format_obligation(o: RegulatoryObligation) -> Dict[str, Any]:
    return {
        "id": o.id,
        "regulation_id": o.regulation_id,
        "organization_id": o.organization_id,
        "applicability_assessment_id": o.applicability_assessment_id,
        "obligation_code": o.obligation_code,
        "title": o.title,
        "description": o.description,
        "obligation_type": o.obligation_type,
        "responsible_function": o.responsible_function,
        "frequency": o.frequency,
        "due_rule": o.due_rule,
        "effective_date": o.effective_date,
        "source_citation": o.source_citation,
        "authoritative_source_url": o.authoritative_source_url,
        "regulatory_evidence_refs": o.regulatory_evidence_refs or [],
        "organization_evidence_refs": o.organization_evidence_refs or [],
        "missing_information": o.missing_information or [],
        "status": o.status,
        "priority": o.priority,
        "engine_version": o.engine_version,
        "created_at": o.created_at,
        "updated_at": o.updated_at
    }

@router.post("/generate", response_model=List[RegulatoryObligationOut])
def generate_regulatory_obligations(
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Generate authoritative regulatory obligations strictly for APPLICABLE assessments.
    Idempotently updates existing obligations and logs an immutable audit event.
    """
    profile = current_profile

    user_name = getattr(current_user, "full_name", "Compliance Officer")
    obligations = ObligationEngine.generate_obligations(
        organization_id=profile.id,
        db=db,
        evaluated_by=user_name
    )

    return [_format_obligation(o) for o in obligations]

@router.get("", response_model=List[RegulatoryObligationOut])
def list_regulatory_obligations(
    regulation_id: Optional[str] = Query(None, description="Filter by regulation_id"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, SUPERSEDED, REQUIRES_REVIEW"),
    obligation_type: Optional[str] = Query(None, description="Filter by obligation_type"),
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, HIGH, MEDIUM, LOW"),
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve all persisted regulatory obligations for the active enterprise profile.
    """
    profile = current_profile

    query = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.organization_id == profile.id
    )

    if regulation_id:
        query = query.filter(RegulatoryObligation.regulation_id == regulation_id)
    if status:
        query = query.filter(RegulatoryObligation.status == status.upper())
    if obligation_type:
        query = query.filter(RegulatoryObligation.obligation_type == obligation_type.upper())
    if priority:
        query = query.filter(RegulatoryObligation.priority == priority.upper())

    obligations = query.all()
    return [_format_obligation(o) for o in obligations]

@router.get("/{obligation_id}", response_model=RegulatoryObligationOut)
def get_regulatory_obligation(
    obligation_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve a specific regulatory obligation with complete statutory provenance.
    """
    obligation = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.id == obligation_id
    ).first()

    if not obligation:
        raise HTTPException(status_code=404, detail=f"Regulatory obligation {obligation_id} not found.")

    return _format_obligation(obligation)
