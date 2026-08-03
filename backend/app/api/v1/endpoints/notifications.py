from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.notification_service import NotificationService
from app.core.security import get_current_user
from app.models.domain import EnterpriseUser

router = APIRouter()

class NotificationReadRequest(BaseModel):
    notification_id: str

@router.get("", response_model=List[Any])
def get_notifications(current_user: EnterpriseUser = Depends(get_current_user)):
    """
    Get active notifications for the current authenticated user.
    """
    return NotificationService.get_user_notifications()

@router.post("/mark-read")
def mark_notification_read(
    payload: NotificationReadRequest,
    current_user: EnterpriseUser = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    """
    success = NotificationService.mark_as_read(payload.notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success", "message": "Notification marked as read"}
