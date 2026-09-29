import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.models.domain import EnterpriseProfile

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    EnterpriseUser
)
from app.schemas.schemas import (
    RegulatoryApplicabilityAssessmentOut,
    ApplicabilityReviewItemOut,
    ApplicabilityReviewResolutionRequest
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.review_service import ReviewService

logger = logging.getLogger("compliance_platform.api.applicability")
router = APIRouter()

def _format_assessment(a: RegulatoryApplicabilityAssessment, reg: Optional[Regulation] = None) -> Dict[str, Any]:
    return {
        "id": a.id,
        "organization_id": a.organization_id,
        "regulation_id": a.regulation_id,
        "regulation_title": reg.title if reg else (a.regulation.title if a.regulation else None),
        "regulation_authority": reg.authority if reg else (a.regulation.authority if a.regulation else None),
        "regulation_region": reg.region if reg else (a.regulation.region if a.regulation else None),
        "regulation_sector": reg.sector if reg else (a.regulation.sector if a.regulation else None),
        "status": a.status,
        "applicability_score": a.applicability_score,
        "rationale": a.rationale,
        "matched_criteria": a.matched_criteria or [],
        "unmet_criteria": a.unmet_criteria or [],
        "missing_information": a.missing_information or [],
        "organization_evidence_refs": a.organization_evidence_refs or [],
        "regulatory_evidence_refs": a.regulatory_evidence_refs or [],
        "regulatory_signal_refs": a.regulatory_signal_refs or [],
        "engine_version": a.engine_version,
        "evaluated_at": a.evaluated_at
    }

@router.post("/evaluate", response_model=List[RegulatoryApplicabilityAssessmentOut])
def evaluate_applicability(
    db: Session = Depends(get_db),
    current_profile: EnterpriseProfile = Depends(get_current_organization),
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """
    Deterministically evaluate regulatory applicability against the confirmed Enterprise Profile.
    Evaluates:
      - Confirmed Organization Context (Locations, Activities, Products, Departments)
      - Discovered Regulatory Signals (Supporting Context)
      - Authoritative Regulatory Sources & Criteria in the Repository
    Idempotently updates existing assessments and writes an audit event.
    """
    profile = current_profile

    user_name = getattr(current_user, "full_name", "Compliance Officer")
    assessments = ApplicabilityEngine.evaluate_organization(
        organization_id=profile.id,
        db=db,
        evaluated_by=user_name
    )
    db.commit()

    # Return formatted list with joined regulation fields
    results = []
    for a in assessments:
        reg = db.query(Regulation).filter(Regulation.id == a.regulation_id).first()
        results.append(_format_assessment(a, reg))

    return results

@router.get("", response_model=List[RegulatoryApplicabilityAssessmentOut])
def list_applicability_assessments(
    status: Optional[str] = Query(None, description="Filter by status: APPLICABLE, NOT_APPLICABLE, REQUIRES_REVIEW"),
    regulation_id: Optional[str] = Query(None, description="Filter by specific regulation_id"),
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve all persisted regulatory applicability assessments for the active enterprise profile.
    """
    profile = current_profile

    query = db.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == profile.id
    )

    if status:
        query = query.filter(RegulatoryApplicabilityAssessment.status == status.upper())
    if regulation_id:
        query = query.filter(RegulatoryApplicabilityAssessment.regulation_id == regulation_id)

    assessments = query.all()
    results = []
    for a in assessments:
        reg = db.query(Regulation).filter(Regulation.id == a.regulation_id).first()
        results.append(_format_assessment(a, reg))

    return results

@router.get("/reviews", response_model=List[ApplicabilityReviewItemOut])
def list_applicability_reviews(
    status: Optional[str] = Query(None, description="Filter by status: OPEN, UNDER_REVIEW, RESOLVED"),
    regulation_id: Optional[str] = Query(None, description="Filter by regulation"),
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve action-oriented applicability review items for the organization.
    """
    profile = current_profile

    from app.models.domain import ApplicabilityReviewItem
    query = db.query(ApplicabilityReviewItem).filter(
        ApplicabilityReviewItem.organization_id == profile.id
    )

    if status:
        query = query.filter(ApplicabilityReviewItem.status == status.upper())
    if regulation_id:
        query = query.filter(ApplicabilityReviewItem.regulation_id == regulation_id)

    return query.all()

@router.get("/{assessment_id}", response_model=RegulatoryApplicabilityAssessmentOut)
def get_applicability_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve a specific applicability assessment with full explainability and evidence traceability.
    """
    assessment = db.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.id == assessment_id,
        RegulatoryApplicabilityAssessment.organization_id == current_profile.id
    ).first()

    if not assessment:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found.")

    reg = db.query(Regulation).filter(Regulation.id == assessment.regulation_id).first()
    return _format_assessment(assessment, reg)

@router.post("/reviews/{review_item_id}/resolve")
def resolve_applicability_review(
    review_item_id: str,
    request: ApplicabilityReviewResolutionRequest,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Submit structured evidence to resolve a pending applicability review.
    Invokes deterministic re-evaluation and creates immutable audit trails.
    """
    profile = current_profile
    if not profile:
        raise HTTPException(status_code=404, detail="No Enterprise Profile found.")

    try:
        result = ReviewService.resolve_applicability_review(
            db=db,
            item_id=review_item_id,
            organization_id=profile.id,
            user_id=current_user.id,
            user_role=current_user.role,
            evidence_fact_value=request.evidence_fact_value,
            evidence_type=request.evidence_type.name if hasattr(request.evidence_type, "name") else request.evidence_type,
            evidence_strength=request.evidence_strength.name if hasattr(request.evidence_strength, "name") else request.evidence_strength,
            source_url=request.source_url,
            snippet=request.snippet or "",
            known_state=request.known_state or "TRUE"
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error resolving review")
        raise HTTPException(status_code=500, detail="Internal Server Error")
