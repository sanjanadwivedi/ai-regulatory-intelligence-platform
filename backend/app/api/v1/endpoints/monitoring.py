from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import EnterpriseProfile, ComplianceAlert
from app.schemas.schemas import (
    CompliancePostureResponse,
    ComplianceAlertResponse,
    AlertResolveRequest
)
from app.services.compliance_posture_service import CompliancePostureService
from app.services.compliance_alert_service import ComplianceAlertService
from app.services.task_execution_service import (
    _verify_authorization,
    _verify_organization_access
)

router = APIRouter()

@router.get("/posture", response_model=CompliancePostureResponse)
def get_compliance_posture(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Deterministically calculate and return the unified compliance posture.
    Read-only aggregation across authoritative legal determinations, obligations, tasks, and evidence.
    """
    user_org_id = getattr(current_user, "organization_id", None)
    if user_org_id:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == user_org_id).first()
    else:
        profile = current_profile

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Enterprise Profile found. Please complete organization discovery first."
        )

    _verify_organization_access(current_user, profile.id)
    posture = CompliancePostureService.calculate_posture(profile.id, db)
    return posture

@router.get("/alerts", response_model=List[ComplianceAlertResponse])
def list_compliance_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    alert_type: Optional[str] = Query(None, description="Filter by alert_type"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, RESOLVED"),
    regulation_id: Optional[str] = Query(None, description="Filter by regulation_id"),
    obligation_id: Optional[str] = Query(None, description="Filter by obligation_id"),
    task_id: Optional[str] = Query(None, description="Filter by task_id"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    List deterministic compliance alerts with multi-dimensional filtering.
    Synchronizes candidate alerts from authoritative upstream state before returning.
    """
    user_org_id = getattr(current_user, "organization_id", None)
    if user_org_id:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == user_org_id).first()
    else:
        profile = current_profile

    if not profile:
        return []

    _verify_organization_access(current_user, profile.id)

    # Sync candidate alerts from current state
    ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db)

    query = db.query(ComplianceAlert).filter(ComplianceAlert.organization_id == profile.id)

    if severity:
        query = query.filter(ComplianceAlert.severity == severity.upper())
    if alert_type:
        query = query.filter(ComplianceAlert.alert_type == alert_type.upper())
    if status:
        query = query.filter(ComplianceAlert.status == status.upper())
    if regulation_id:
        query = query.filter(ComplianceAlert.regulation_id == regulation_id)
    if obligation_id:
        query = query.filter(ComplianceAlert.obligation_id == obligation_id)
    if task_id:
        query = query.filter(ComplianceAlert.task_id == task_id)

    alerts = query.order_by(ComplianceAlert.created_at.desc()).all()
    return alerts

@router.get("/alerts/{alert_id}", response_model=ComplianceAlertResponse)
def get_compliance_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Retrieve single compliance alert details.
    """
    alert = db.query(ComplianceAlert).filter(ComplianceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Compliance alert {alert_id} not found")

    _verify_organization_access(current_user, alert.organization_id)
    return alert

@router.post("/alerts/{alert_id}/resolve", response_model=ComplianceAlertResponse)
def resolve_compliance_alert(
    alert_id: str,
    resolve_in: AlertResolveRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Operationally resolve a compliance alert.
    GUARANTEE: Modifies ONLY alert operational status and creates an immutable audit trail.
    Leaves all upstream regulations, obligations, and assessments 100% untouched.
    """
    resolved_alert = ComplianceAlertService.resolve_alert(
        alert_id=alert_id,
        current_user=current_user,
        resolution_notes=resolve_in.resolution_notes,
        db=db
    )
    return resolved_alert
