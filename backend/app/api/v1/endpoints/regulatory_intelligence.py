import logging
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    EnterpriseUser,
    EnterpriseProfile,
    Regulation,
    RegulatoryChange,
    DocumentVersion,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    RegulatoryChangeTenantReview,
    AuditLog
)
from app.schemas.schemas import (
    RegulatoryIntelligenceSummaryResponse,
    RegulatoryChangeFeedItem,
    RegulatoryChangeFeedResponse,
    RegulatoryChangeDetailResponse,
    RegulatoryChangeReviewRequest,
    RegulatoryChangeReviewResponse,
    ImpactPropagationResponse,
    RegulatoryObligationImpactOut
)
from app.services.regulatory_impact_service import propagate_change_impact

logger = logging.getLogger("compliance_platform.api.regulatory_intelligence")
router = APIRouter()

def _get_tenant_review_status(db: Session, change_id: str, org_id: str) -> RegulatoryChangeTenantReview:
    review = db.query(RegulatoryChangeTenantReview).filter(
        RegulatoryChangeTenantReview.change_id == change_id,
        RegulatoryChangeTenantReview.organization_id == org_id
    ).first()
    return review

def _create_audit_log(db: Session, org_id: str, user: EnterpriseUser, change_id: str, old_status: str, new_status: str, decision: str):
    user_name = getattr(user, "full_name", None) or getattr(user, "email", "System User")
    user_role = getattr(user, "role", "USER")
    
    audit = AuditLog(
        organization_id=org_id,
        user_name=user_name,
        user_role=user_role,
        action="REGULATORY_CHANGE_REVIEW",
        target_type="REGULATORY_CHANGE",
        target_id=change_id,
        details={
            "change_id": change_id,
            "decision": decision,
            "previous_status": old_status,
            "new_status": new_status,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    )
    db.add(audit)

@router.get("/summary", response_model=RegulatoryIntelligenceSummaryResponse)
def get_regulatory_intelligence_summary(
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    total_regs = db.query(Regulation).count()
    
    # We define new/updated based on RegulatoryChange records. 
    # For simplicity, we just count changes that are "NEW" vs "UPDATED" 
    # and restrict them to the current tenant's affected pool.
    # To properly count tenant-affected changes, we join with assessments.
    
    affected_changes = db.query(RegulatoryChange).join(
        RegulatoryApplicabilityAssessment,
        RegulatoryChange.regulation_id == RegulatoryApplicabilityAssessment.regulation_id
    ).filter(
        RegulatoryApplicabilityAssessment.organization_id == org.id,
        RegulatoryApplicabilityAssessment.status == "APPLICABLE"
    ).all()
    
    affected_change_ids = [c.id for c in affected_changes]
    
    new_regulations = sum(1 for c in affected_changes if c.change_type == "NEW")
    updated_regulations = sum(1 for c in affected_changes if c.change_type != "NEW")
    
    # Count how many of these affected changes are REQUIRES_REVIEW for this tenant
    # A change is REQUIRES_REVIEW if no tenant review row exists, or if one exists with REQUIRES_REVIEW.
    changes_requiring_review = 0
    if affected_change_ids:
        reviewed_ids = {
            r.change_id for r in db.query(RegulatoryChangeTenantReview).filter(
                RegulatoryChangeTenantReview.organization_id == org.id,
                RegulatoryChangeTenantReview.change_id.in_(affected_change_ids),
                RegulatoryChangeTenantReview.review_status != "REQUIRES_REVIEW"
            ).all()
        }
        changes_requiring_review = len(affected_change_ids) - len(reviewed_ids)
        
    # Get total affected entities across all active changes? Or just total for the org?
    # The requirement: affected assessments, obligations, tasks.
    # We will simply return the count of these items for the organization.
    affected_assessments = db.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == org.id,
        RegulatoryApplicabilityAssessment.status == "APPLICABLE"
    ).count()
    
    affected_obligations = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.organization_id == org.id
    ).count()
    
    affected_tasks = db.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org.id
    ).count()
    
    return RegulatoryIntelligenceSummaryResponse(
        total_regulations=total_regs,
        new_regulations=new_regulations,
        updated_regulations=updated_regulations,
        changes_requiring_review=changes_requiring_review,
        affected_assessments=affected_assessments,
        affected_obligations=affected_obligations,
        affected_tasks=affected_tasks
    )

@router.get("/changes", response_model=RegulatoryChangeFeedResponse)
def list_regulatory_changes(
    change_type: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    regulation_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    query = db.query(RegulatoryChange).join(
        Regulation, RegulatoryChange.regulation_id == Regulation.id
    ).join(
        RegulatoryApplicabilityAssessment, RegulatoryChange.regulation_id == RegulatoryApplicabilityAssessment.regulation_id
    ).filter(
        RegulatoryApplicabilityAssessment.organization_id == org.id,
        RegulatoryApplicabilityAssessment.status == "APPLICABLE"
    )
    
    if change_type:
        query = query.filter(RegulatoryChange.change_type == change_type)
        
    if regulation_id:
        query = query.filter(RegulatoryChange.regulation_id == regulation_id)
        
    changes = query.order_by(desc(RegulatoryChange.detected_at)).all()
    
    # We process review status in Python since it could be missing from DB
    filtered_changes = []
    
    for change in changes:
        review = _get_tenant_review_status(db, change.id, org.id)
        current_status = review.review_status if review else "REQUIRES_REVIEW"
        
        if review_status and current_status != review_status:
            continue
            
        filtered_changes.append((change, current_status))
        
    total = len(filtered_changes)
    start = (page - 1) * size
    end = start + size
    paginated = filtered_changes[start:end]
    
    items = []
    for change, r_status in paginated:
        reg = change.regulation
        
        # Scoped counts
        a_count = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.organization_id == org.id,
            RegulatoryApplicabilityAssessment.regulation_id == reg.id,
            RegulatoryApplicabilityAssessment.status == "APPLICABLE"
        ).count()
        
        o_count = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == org.id,
            RegulatoryObligation.regulation_id == reg.id
        ).count()
        
        t_count = db.query(ComplianceTask).filter(
            ComplianceTask.organization_id == org.id,
            ComplianceTask.regulation_id == reg.id
        ).count()
        
        prev_v = change.previous_version
        new_v = change.new_version
        
        items.append(RegulatoryChangeFeedItem(
            change_id=change.id,
            regulation_id=reg.id,
            regulation_name=reg.title,
            previous_version=str(prev_v.version_no) if prev_v else None,
            new_version=str(new_v.version_no),
            change_type=change.change_type,
            detected_timestamp=change.detected_at,
            effective_date=new_v.effective_date,
            source=change.source_url or reg.source_url,
            review_status=r_status,
            affected_assessment_count=a_count,
            affected_obligation_count=o_count,
            affected_task_count=t_count
        ))
        
    return RegulatoryChangeFeedResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )

@router.get("/changes/{change_id}", response_model=RegulatoryChangeDetailResponse)
def get_regulatory_change_detail(
    change_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
        
    reg = change.regulation
    
    # Check if org is affected (for security)
    is_affected = db.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.organization_id == org.id,
        RegulatoryApplicabilityAssessment.regulation_id == reg.id
    ).first()
    
    if not is_affected:
        # DO NOT return 404, they can view it, but scoped counts are 0
        pass
        
    review = _get_tenant_review_status(db, change.id, org.id)
    r_status = review.review_status if review else "REQUIRES_REVIEW"
    
    assessments = db.query(RegulatoryApplicabilityAssessment.id).filter(
        RegulatoryApplicabilityAssessment.organization_id == org.id,
        RegulatoryApplicabilityAssessment.regulation_id == reg.id
    ).all()
    
    obligations = db.query(RegulatoryObligation.id).filter(
        RegulatoryObligation.organization_id == org.id,
        RegulatoryObligation.regulation_id == reg.id
    ).all()
    
    tasks = db.query(ComplianceTask.id).filter(
        ComplianceTask.organization_id == org.id,
        ComplianceTask.regulation_id == reg.id
    ).all()
    
    prev_v = change.previous_version
    new_v = change.new_version
    
    return RegulatoryChangeDetailResponse(
        change_id=change.id,
        regulation_id=reg.id,
        regulation_name=reg.title,
        previous_version=str(prev_v.version_no) if prev_v else None,
        new_version=str(new_v.version_no),
        change_type=change.change_type,
        detected_timestamp=change.detected_at,
        effective_date=new_v.effective_date,
        source=change.source_url or reg.source_url,
        review_status=r_status,
        review_notes=review.review_notes if review else None,
        reviewed_at=review.reviewed_at if review else None,
        reviewed_by=review.reviewed_by if review else None,
        diff_hunks=change.diff_hunks,
        changed_sections=change.changed_sections,
        affected_assessments=[str(a.id) for a in assessments],
        affected_obligations=[str(o.id) for o in obligations],
        affected_tasks=[str(t.id) for t in tasks]
    )

@router.post("/changes/{change_id}/review", response_model=RegulatoryChangeReviewResponse)
def review_regulatory_change(
    change_id: str,
    request: RegulatoryChangeReviewRequest,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
        
    review = _get_tenant_review_status(db, change.id, org.id)
    old_status = review.review_status if review else "REQUIRES_REVIEW"
    
    new_status = None
    if request.decision == "ACKNOWLEDGE":
        new_status = "REVIEWED"
    elif request.decision == "RESOLVE":
        new_status = "RESOLVED"
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")
        
    # Idempotency
    if old_status == new_status and review is not None:
        return RegulatoryChangeReviewResponse(
            status="SUCCESS",
            change_id=change.id,
            review_status=new_status
        )
        
    if not review:
        review = RegulatoryChangeTenantReview(
            organization_id=org.id,
            change_id=change.id,
            review_status=new_status
        )
        db.add(review)
    else:
        review.review_status = new_status
        
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "email", "System User")
    review.reviewed_at = datetime.datetime.utcnow()
    review.reviewed_by = user_name
    if request.review_notes:
        review.review_notes = request.review_notes
        
    # Audit log
    _create_audit_log(db, org.id, current_user, change.id, old_status, new_status, request.decision)
    
    db.commit()
    
    return RegulatoryChangeReviewResponse(
        status="SUCCESS",
        change_id=change.id,
        review_status=new_status
    )


@router.post("/changes/{change_id}/propagate-impact", response_model=ImpactPropagationResponse)
def trigger_impact_propagation(
    change_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "email", "System User")
    try:
        result = propagate_change_impact(db, change_id, org.id, user_name)
        return ImpactPropagationResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/changes/{change_id}/impact", response_model=List[RegulatoryObligationImpactOut])
def get_change_impact(
    change_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user),
    org: EnterpriseProfile = Depends(get_current_organization)
):
    from app.models.domain import RegulatoryObligationImpact
    impacts = db.query(RegulatoryObligationImpact).filter(
        RegulatoryObligationImpact.regulatory_change_id == change_id,
        RegulatoryObligationImpact.organization_id == org.id
    ).all()
    return impacts
