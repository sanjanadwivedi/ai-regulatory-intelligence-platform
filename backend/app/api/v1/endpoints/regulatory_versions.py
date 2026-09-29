from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.domain import (
    Regulation,
    DocumentVersion,
    RegulatoryChange,
    EnterpriseUser
)

router = APIRouter()

@router.get("/regulations/{regulation_id}/versions")
def get_regulation_versions(
    regulation_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """Get all versions for a regulation, sorted by version number descending."""
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.regulation_id == regulation_id)
        .order_by(DocumentVersion.version_no.desc())
        .all()
    )
    if not versions:
        # Check if regulation exists
        reg = db.query(Regulation).filter(Regulation.id == regulation_id).first()
        if not reg:
            raise HTTPException(status_code=404, detail="Regulation not found")
        return []
    
    return [
        {
            "id": v.id,
            "version_no": v.version_no,
            "content_hash": v.content_hash,
            "effective_date": v.effective_date,
            "source_url": v.source_url,
            "ingested_at": v.ingested_at,
            "ingestion_method": v.ingestion_method,
            "diff_summary": v.diff_summary,
            "created_at": v.created_at,
        }
        for v in versions
    ]


@router.get("/regulations/{regulation_id}/changes")
def get_regulation_changes(
    regulation_id: str,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """Get all change records for a regulation."""
    changes = (
        db.query(RegulatoryChange)
        .filter(RegulatoryChange.regulation_id == regulation_id)
        .order_by(RegulatoryChange.detected_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "change_type": c.change_type,
            "detected_at": c.detected_at,
            "detected_by": c.detected_by,
            "drift_percentage": c.drift_percentage,
            "content_hash_before": c.content_hash_before,
            "content_hash_after": c.content_hash_after,
            "diff_hunks": c.diff_hunks,
            "changed_sections": c.changed_sections,
            "source_url": c.source_url,
            "review_status": c.review_status,
            "previous_version_id": c.previous_version_id,
            "new_version_id": c.new_version_id,
        }
        for c in changes
    ]


@router.get("/regulatory-changes")
def list_all_regulatory_changes(
    status: Optional[str] = Query(None, description="Filter by review_status"),
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """Global inbox of all regulatory changes across the system."""
    query = db.query(RegulatoryChange, Regulation).join(Regulation).order_by(RegulatoryChange.detected_at.desc())
    
    if status:
        query = query.filter(RegulatoryChange.review_status == status.upper())
        
    results = query.all()
    response = []
    for change, reg in results:
        response.append({
            "id": change.id,
            "regulation_id": reg.id,
            "regulation_title": reg.title,
            "authority": reg.authority,
            "change_type": change.change_type,
            "detected_at": change.detected_at,
            "detected_by": change.detected_by,
            "drift_percentage": change.drift_percentage,
            "review_status": change.review_status,
            "source_url": change.source_url,
        })
    return response


@router.post("/regulatory-changes/{change_id}/review")
def review_regulatory_change(
    change_id: str,
    action: str = Query(..., description="Action to take: ACKNOWLEDGE, DISMISS, REQUIRE_ACTION"),
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """Update the review status of a regulatory change."""
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
        
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "email", "System User")
    
    if action == "ACKNOWLEDGE":
        change.review_status = "REVIEWED"
    elif action == "DISMISS":
        change.review_status = "DISMISSED"
    elif action == "REQUIRE_ACTION":
        change.review_status = "PENDING_REVIEW"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    import datetime
    change.reviewed_at = datetime.datetime.utcnow()
    change.reviewed_by = user_name
    if notes:
        change.review_notes = notes
        
    db.commit()
    return {"status": "SUCCESS", "review_status": change.review_status}