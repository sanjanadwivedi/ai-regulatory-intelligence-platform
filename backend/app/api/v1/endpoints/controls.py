import logging
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    InternalControl,
    RegulatoryObligation,
    ObligationControlMapping,
    ControlAssessment,
    AuditLog
)
from app.schemas.schemas import (
    InternalControlCreate,
    InternalControlUpdate,
    InternalControlResponse,
    ObligationControlMappingCreate,
    ObligationControlMappingResponse,
    ControlAssessmentResponse
)

logger = logging.getLogger("compliance_platform.api.controls")
router = APIRouter()

def _log_audit(db: Session, organization_id: str, current_user: EnterpriseUser, action: str, target_type: str, target_id: str, details: dict):
    audit = AuditLog(
        organization_id=organization_id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )
    db.add(audit)

@router.get("/", response_model=List[InternalControlResponse])
def list_controls(
    db: Session = Depends(get_db),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    controls = db.query(InternalControl).filter(
        InternalControl.organization_id == current_org.id
    ).all()
    return controls

@router.post("/", response_model=InternalControlResponse)
def create_control(
    payload: InternalControlCreate,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    # Check duplicate control_code in organization
    existing = db.query(InternalControl).filter(
        InternalControl.organization_id == current_org.id,
        InternalControl.control_code == payload.control_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Control code already exists in this organization")

    control = InternalControl(
        organization_id=current_org.id,
        control_code=payload.control_code,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        owner_department=payload.owner_department,
        status=payload.status,
        implementation_notes=payload.implementation_notes
    )
    db.add(control)
    try:
        db.commit()
        db.refresh(control)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error creating control")

    _log_audit(db, current_org.id, current_user, "CONTROL_CREATED", "INTERNAL_CONTROL", control.id, {"control_code": control.control_code})
    db.commit()

    return control

@router.get("/{control_id}", response_model=InternalControlResponse)
def get_control(
    control_id: str,
    db: Session = Depends(get_db),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    return control

@router.patch("/{control_id}", response_model=InternalControlResponse)
def update_control(
    control_id: str,
    payload: InternalControlUpdate,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    update_data = payload.model_dump(exclude_unset=True) if hasattr(payload, 'model_dump') else payload.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(control, k, v)
    
    control.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(control)

    _log_audit(db, current_org.id, current_user, "CONTROL_UPDATED", "INTERNAL_CONTROL", control.id, {"updated_fields": list(update_data.keys())})
    db.commit()

    return control

@router.delete("/{control_id}")
def delete_control(
    control_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    code = control.control_code
    db.delete(control)
    db.commit()

    _log_audit(db, current_org.id, current_user, "CONTROL_DELETED", "INTERNAL_CONTROL", control_id, {"control_code": code})
    db.commit()

    return {"status": "DELETED", "id": control_id}

@router.get("/{control_id}/assessment", response_model=ControlAssessmentResponse)
def get_control_assessment(
    control_id: str,
    db: Session = Depends(get_db),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
        
    assessment = db.query(ControlAssessment).filter(
        ControlAssessment.organization_id == current_org.id,
        ControlAssessment.control_id == control_id
    ).order_by(ControlAssessment.evaluated_at.desc()).first()
    
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this control")
    return assessment

@router.post("/{control_id}/reassess", response_model=ControlAssessmentResponse)
def reassess_control(
    control_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    from app.services.control_engine import ControlEngine
    from app.services.task_engine import TaskEngine
    
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    assessment = ControlEngine.evaluate_control(
        control_id=control_id,
        organization_id=current_org.id,
        db=db,
        evaluated_by=current_user.full_name
    )
    if assessment and assessment.id:
        TaskEngine.generate_tasks(current_org.id, db)
    
    if not assessment:
        raise HTTPException(status_code=500, detail="Failed to evaluate control")
        
    return assessment

@router.post("/evaluate", response_model=List[ControlAssessmentResponse])
def evaluate_controls(
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    from app.services.control_engine import ControlEngine
    assessments = ControlEngine.evaluate_organization_controls(
        organization_id=current_org.id,
        db=db,
        evaluated_by=current_user.full_name
    )
    return assessments

@router.get("/{control_id}/obligations", response_model=List[ObligationControlMappingResponse])
def list_mapped_obligations(
    control_id: str,
    db: Session = Depends(get_db),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    # Verify control exists and is owned by tenant
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    mappings = db.query(ObligationControlMapping).filter(
        ObligationControlMapping.control_id == control_id,
        ObligationControlMapping.organization_id == current_org.id
    ).all()
    
    return mappings

@router.post("/{control_id}/obligations/{obligation_id}", response_model=ObligationControlMappingResponse)
def map_obligation(
    control_id: str,
    obligation_id: str,
    payload: ObligationControlMappingCreate,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    control = db.query(InternalControl).filter(
        InternalControl.id == control_id,
        InternalControl.organization_id == current_org.id
    ).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    obligation = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.id == obligation_id,
        RegulatoryObligation.organization_id == current_org.id
    ).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")
        
    # Phase 1C: APPLICABILITY SAFETY
    if obligation.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Obligation is not active. Only active obligations can be mapped.")

    existing = db.query(ObligationControlMapping).filter(
        ObligationControlMapping.organization_id == current_org.id,
        ObligationControlMapping.control_id == control_id,
        ObligationControlMapping.obligation_id == obligation_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mapping already exists")

    mapping = ObligationControlMapping(
        organization_id=current_org.id,
        obligation_id=obligation_id,
        control_id=control_id,
        rationale=payload.rationale,
        mapping_source=payload.mapping_source,
        created_by=current_user.full_name
    )
    db.add(mapping)
    try:
        db.commit()
        db.refresh(mapping)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Integrity error creating mapping")

    _log_audit(db, current_org.id, current_user, "CONTROL_OBLIGATION_MAPPED", "OBLIGATION_CONTROL_MAPPING", mapping.id, {
        "control_id": control_id,
        "obligation_id": obligation_id
    })
    db.commit()
    
    return mapping

@router.delete("/{control_id}/obligations/{obligation_id}")
def unmap_obligation(
    control_id: str,
    obligation_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_org: EnterpriseProfile = Depends(get_current_organization)
):
    mapping = db.query(ObligationControlMapping).filter(
        ObligationControlMapping.organization_id == current_org.id,
        ObligationControlMapping.control_id == control_id,
        ObligationControlMapping.obligation_id == obligation_id
    ).first()
    
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
        
    m_id = mapping.id
    db.delete(mapping)
    db.commit()
    
    _log_audit(db, current_org.id, current_user, "CONTROL_OBLIGATION_UNMAPPED", "OBLIGATION_CONTROL_MAPPING", m_id, {
        "control_id": control_id,
        "obligation_id": obligation_id
    })
    db.commit()
    
    return {"status": "DELETED", "mapping_id": m_id}


