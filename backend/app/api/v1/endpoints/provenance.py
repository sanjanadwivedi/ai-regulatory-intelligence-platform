import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ObligationControlMapping,
    InternalControl,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceAlert
)
from app.schemas.schemas import ProvenanceChainResponse, ProvenanceNodeResponse

logger = logging.getLogger("compliance_platform.api.provenance")
router = APIRouter()

@router.get("/{entity_type}/{entity_id}", response_model=ProvenanceChainResponse)
def get_provenance_chain(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    valid_types = ["REGULATION", "APPLICABILITY", "OBLIGATION", "CONTROL", "TASK", "ALERT"]
    if entity_type not in valid_types:
        raise HTTPException(status_code=422, detail="Unsupported entity_type for provenance.")

    org_id = current_profile.id
    nodes = []

    target_type = entity_type
    target_id = entity_id

    if target_type == "ALERT":
        alert = db.query(ComplianceAlert).filter(
            ComplianceAlert.id == target_id,
            ComplianceAlert.organization_id == org_id
        ).first()
        if not alert:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])
        
        target_type = alert.source_entity_type
        target_id = alert.source_entity_id

    # Translate target_type if it came from Alert's source_entity_type
    if target_type == "COMPLIANCE_TASK":
        target_type = "TASK"
    elif target_type == "REGULATORY_OBLIGATION":
        target_type = "OBLIGATION"
    elif target_type == "REGULATORY_APPLICABILITY_ASSESSMENT":
        target_type = "APPLICABILITY"

    regulation = None
    applicability = None
    obligation = None
    control = None
    task = None
    evidences = []

    if target_type == "TASK":
        task = db.query(ComplianceTask).filter(ComplianceTask.id == target_id, ComplianceTask.organization_id == org_id).first()
        if not task:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])
        control = db.query(InternalControl).filter(InternalControl.id == task.control_id, InternalControl.organization_id == org_id).first() if task.control_id else None
        evidences = db.query(ComplianceTaskEvidence).filter(ComplianceTaskEvidence.task_id == task.id, ComplianceTaskEvidence.organization_id == org_id).all()

    elif target_type == "CONTROL":
        control = db.query(InternalControl).filter(InternalControl.id == target_id, InternalControl.organization_id == org_id).first()
        if not control:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    elif target_type == "OBLIGATION":
        obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == target_id, RegulatoryObligation.organization_id == org_id).first()
        if not obligation:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    elif target_type == "APPLICABILITY":
        applicability = db.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.id == target_id, RegulatoryApplicabilityAssessment.organization_id == org_id).first()
        if not applicability:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    elif target_type == "REGULATION":
        regulation = db.query(Regulation).filter(Regulation.id == target_id).first()
        if not regulation:
            return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    else:
        return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    # Upward traversal
    if control and not obligation:
        mapping = db.query(ObligationControlMapping).filter(ObligationControlMapping.control_id == control.id, ObligationControlMapping.organization_id == org_id).first()
        if mapping:
            obligation = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == mapping.obligation_id, RegulatoryObligation.organization_id == org_id).first()

    if obligation and not applicability:
        if obligation.applicability_assessment_id:
            applicability = db.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.id == obligation.applicability_assessment_id, RegulatoryApplicabilityAssessment.organization_id == org_id).first()

    if applicability and not regulation:
        regulation = db.query(Regulation).filter(Regulation.id == applicability.regulation_id).first()

    if obligation and not applicability and not regulation:
        if obligation.regulation_id:
            regulation = db.query(Regulation).filter(Regulation.id == obligation.regulation_id).first()

    if regulation:
        nodes.append(ProvenanceNodeResponse(
            id=regulation.id,
            type="REGULATION",
            title=regulation.title,
            meta=f"{regulation.region} | {regulation.authority}",
            status="VERIFIED" if getattr(regulation, 'source_url_verified', 0) == 1 else "UNVERIFIED"
        ))

    if applicability:
        nodes.append(ProvenanceNodeResponse(
            id=applicability.id,
            type="APPLICABILITY",
            title=applicability.status,
            meta="Applicability Assessment",
            status=applicability.status
        ))

    if obligation:
        nodes.append(ProvenanceNodeResponse(
            id=obligation.id,
            type="OBLIGATION",
            title=obligation.title,
            meta=obligation.obligation_type,
            status=obligation.status
        ))
        
    if control:
        nodes.append(ProvenanceNodeResponse(
            id=control.id,
            type="CONTROL",
            title=control.name,
            meta=control.control_code,
            status=control.status
        ))

    if task:
        nodes.append(ProvenanceNodeResponse(
            id=task.id,
            type="TASK",
            title=task.title,
            meta=f"Assigned to: {task.assignee or 'Unassigned'}",
            status=task.status
        ))
        
    for ev in evidences:
        nodes.append(ProvenanceNodeResponse(
            id=ev.id,
            type="EVIDENCE",
            title=ev.file_name,
            meta=ev.evidence_type,
            status=ev.status
        ))

    if not nodes:
        return ProvenanceChainResponse(status="UNAVAILABLE", message="No verified provenance is available for this entity.", nodes=[])

    return ProvenanceChainResponse(nodes=nodes, status="AVAILABLE")
