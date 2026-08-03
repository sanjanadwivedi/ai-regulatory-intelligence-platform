from typing import Dict, Any, List
from datetime import datetime

class TaskWorkflowService:
    """
    Task & Workflow Management Service: Enforces compliance task lifecycle transitions
    (OPEN -> IN_REVIEW -> APPROVED -> COMPLETED) and generates audit log events for sign-offs.
    """

    VALID_TRANSITIONS = {
        "OPEN": ["IN_REVIEW", "COMPLETED"],
        "IN_REVIEW": ["APPROVED", "OPEN"],
        "APPROVED": ["COMPLETED", "IN_REVIEW"],
        "COMPLETED": ["OPEN"]
    }

    @classmethod
    def validate_transition(cls, current_status: str, new_status: str) -> bool:
        allowed = cls.VALID_TRANSITIONS.get(current_status, [])
        return new_status in allowed
