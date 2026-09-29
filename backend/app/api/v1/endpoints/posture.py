import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import datetime

from app.core.database import get_db
from app.core.security import get_current_organization
from app.models.domain import (
    EnterpriseProfile,
    ObligationPosture,
    RegulationPosture,
    OrganizationCompliancePosture,
    ControlAssessment,
    RegulatoryObligation,
    Regulation
)

logger = logging.getLogger("compliance_platform.api.posture")
router = APIRouter()

# ----------------- Schemas -----------------
class ObligationPostureResponse(BaseModel):
    obligation_id: str
    posture_status: str
    control_count: int
    effective_control_count: int
    control_gap_count: int
    review_required_count: int
    missing_information: Optional[dict] = None
    evaluated_at: datetime.datetime
    engine_version: str
    
    class Config:
        orm_mode = True

class RegulationPostureResponse(BaseModel):
    regulation_id: str
    regulation_title: Optional[str] = None
    posture_status: str
    applicable_obligation_count: int
    satisfied_obligation_count: int
    control_gap_count: int
    review_required_count: int
    missing_information: Optional[dict] = None
    evaluated_at: datetime.datetime
    engine_version: str

    class Config:
        orm_mode = True

class OrganizationPostureResponse(BaseModel):
    posture_status: str
    compliance_percentage: Optional[float] = None
    applicable_regulation_count: int
    satisfied_regulation_count: int
    control_gap_regulation_count: int
    review_required_regulation_count: int
    total_applicable_obligations: int
    satisfied_obligations: int
    control_gap_obligations: int
    review_required_obligations: int
    effective_controls: int
    ineffective_controls: int
    controls_requiring_review: int
    missing_information: Optional[dict] = None
    evaluated_at: datetime.datetime
    engine_version: str

    class Config:
        orm_mode = True

# ----------------- Endpoints -----------------

@router.get("", response_model=OrganizationPostureResponse)
def get_organization_posture(
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get the current compliance posture of the authenticated organization."""
    posture = db.query(OrganizationCompliancePosture).filter(
        OrganizationCompliancePosture.organization_id == org.id
    ).order_by(OrganizationCompliancePosture.evaluated_at.desc()).first()
    
    if not posture:
        # Evaluate dynamically if none exists
        from app.services.posture_engine import PostureEngine
        posture = PostureEngine.evaluate_organization_posture(org.id, db)
        
    if not posture:
        raise HTTPException(status_code=404, detail="Organization posture not found and could not be evaluated.")
        
    return posture


@router.get("/history", response_model=List[OrganizationPostureResponse])
def get_organization_posture_history(
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get immutable organization posture history."""
    return db.query(OrganizationCompliancePosture).filter(
        OrganizationCompliancePosture.organization_id == org.id
    ).order_by(OrganizationCompliancePosture.evaluated_at.desc()).all()


@router.get("/regulations", response_model=List[RegulationPostureResponse])
def get_regulations_posture(
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get current regulation-level posture for all regulations."""
    # Find latest posture per regulation. Easiest way in SQLite is subqueries or python processing.
    # Since we don't have distinct ON, we can query all and group.
    postures = db.query(RegulationPosture).filter(
        RegulationPosture.organization_id == org.id
    ).order_by(RegulationPosture.evaluated_at.desc()).all()
    
    seen_reg_ids = set()
    latest_postures = []
    
    for p in postures:
        if p.regulation_id not in seen_reg_ids:
            seen_reg_ids.add(p.regulation_id)
            
            # Fetch regulation title
            reg = db.query(Regulation).filter(Regulation.id == p.regulation_id).first()
            p.regulation_title = reg.title if reg else None
            
            latest_postures.append(p)
            
    return latest_postures


@router.get("/regulations/{regulation_id}", response_model=RegulationPostureResponse)
def get_regulation_posture(
    regulation_id: str,
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get the current posture for a specific regulation."""
    posture = db.query(RegulationPosture).filter(
        RegulationPosture.organization_id == org.id,
        RegulationPosture.regulation_id == regulation_id
    ).order_by(RegulationPosture.evaluated_at.desc()).first()
    
    if not posture:
        from app.services.posture_engine import PostureEngine
        posture = PostureEngine.evaluate_regulation_posture(regulation_id, org.id, db)
        
    if not posture:
        raise HTTPException(status_code=404, detail="Regulation posture not found.")
        
    reg = db.query(Regulation).filter(Regulation.id == posture.regulation_id).first()
    posture.regulation_title = reg.title if reg else None
    
    return posture


@router.get("/obligations/{obligation_id}", response_model=ObligationPostureResponse)
def get_obligation_posture(
    obligation_id: str,
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get current posture for one obligation."""
    posture = db.query(ObligationPosture).filter(
        ObligationPosture.organization_id == org.id,
        ObligationPosture.obligation_id == obligation_id
    ).order_by(ObligationPosture.evaluated_at.desc()).first()
    
    if not posture:
        from app.services.posture_engine import PostureEngine
        posture = PostureEngine.evaluate_obligation_posture(obligation_id, org.id, db)
        
    if not posture:
        raise HTTPException(status_code=404, detail="Obligation posture not found.")
        
    return posture


@router.get("/obligations/{obligation_id}/history", response_model=List[ObligationPostureResponse])
def get_obligation_posture_history(
    obligation_id: str,
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Get immutable obligation posture history."""
    # Ensure ownership implicitly via organization_id
    ob = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.id == obligation_id,
        RegulatoryObligation.organization_id == org.id
    ).first()
    if not ob:
        raise HTTPException(status_code=404, detail="Obligation not found")
        
    return db.query(ObligationPosture).filter(
        ObligationPosture.organization_id == org.id,
        ObligationPosture.obligation_id == obligation_id
    ).order_by(ObligationPosture.evaluated_at.desc()).all()


# Note: We must redefine ControlAssessmentResponse locally or import it.
# We'll import it from schemas to avoid duplication, but we can't because of circular imports sometimes.
# It's better to just import it.
from app.schemas.schemas import ControlAssessmentResponse

@router.get("/controls/{control_id}", response_model=ControlAssessmentResponse)
def get_control_assessment(
    control_id: str,
    db: Session = Depends(get_db),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    """Returns the latest ControlAssessment used by the posture."""
    assessment = db.query(ControlAssessment).filter(
        ControlAssessment.organization_id == org.id,
        ControlAssessment.control_id == control_id
    ).order_by(ControlAssessment.evaluated_at.desc()).first()
    
    if not assessment:
        raise HTTPException(status_code=404, detail="Control assessment not found.")
        
    return assessment
