from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import ComplianceTriggerEvent, EnterpriseProfile
from app.schemas.schemas import TriggerEventCreate, TriggerEventResponse
from app.services.task_execution_service import TaskExecutionService

router = APIRouter()

@router.post("", response_model=TriggerEventResponse)
def record_trigger_event(
    event_in: TriggerEventCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Record a real-world compliance trigger event (e.g. INCIDENT_DETECTED) and deterministically
    calculate statutory deadlines for matching tasks within the same organization.
    """
    event, affected_tasks = TaskExecutionService.process_trigger_event(
        event_in=event_in,
        current_user=current_user,
        db=db
    )
    res_dict = TriggerEventResponse.model_validate(event).model_dump()
    res_dict["affected_tasks_count"] = len(affected_tasks)
    return res_dict

@router.get("", response_model=List[TriggerEventResponse])
def list_trigger_events(
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    profile = current_profile

    query = db.query(ComplianceTriggerEvent).filter(ComplianceTriggerEvent.organization_id == profile.id)
    if event_type:
        query = query.filter(ComplianceTriggerEvent.event_type == event_type.upper())

    events = query.order_by(ComplianceTriggerEvent.event_timestamp.desc()).all()
    return [TriggerEventResponse.model_validate(e).model_dump() for e in events]
