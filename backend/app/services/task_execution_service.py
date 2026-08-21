import logging
import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.domain import (
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTaskActivity,
    ComplianceTriggerEvent,
    RegulatoryObligation,
    Regulation,
    EnterpriseProfile,
    EnterpriseUser,
    AuditLog
)
from app.schemas.schemas import (
    TaskAssignRequest,
    TaskStatusTransitionRequest,
    TaskCompleteRequest,
    TaskReopenRequest,
    EvidenceCreate,
    TriggerEventCreate
)

logger = logging.getLogger("compliance_platform.task_execution")

AUTHORIZED_ROLES = {
    "Compliance Officer",
    "Compliance Manager",
    "Compliance Auditor",
    "Legal Counsel",
    "CISO",
    "Information Security",
    "Admin",
    "Auditor"
}

# Deterministic Task State Machine Transitions
VALID_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"},
    "IN_PROGRESS": {"BLOCKED", "COMPLETED", "OPEN", "CANCELLED"},
    "BLOCKED": {"IN_PROGRESS", "OPEN", "CANCELLED"},
    "COMPLETED": {"REOPENED"},
    "REOPENED": {"IN_PROGRESS", "OPEN", "COMPLETED", "BLOCKED"},
    # Legacy / Compatibility Statuses
    "NEW": {"OPEN", "IN_PROGRESS", "WAITING_APPROVAL", "NEEDS_REVIEW"},
    "NEEDS_REVIEW": {"OPEN", "IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED"},
    "MY_TASKS": {"IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED", "OPEN"},
    "DUE_TODAY": {"IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED", "OPEN"},
    "WAITING_APPROVAL": {"COMPLETED", "IN_PROGRESS", "OPEN", "BLOCKED"},
    "CANCELLED": set(),
    "SUPERSEDED": set()
}

def _verify_authorization(user: Any, required_action: str = "modify compliance tasks"):
    role = getattr(user, "role", None) or "Compliance Officer"
    if role not in AUTHORIZED_ROLES and "Compliance" not in role and "Legal" not in role and "Admin" not in role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role '{role}' is not authorized to {required_action}."
        )

def _verify_organization_access(user: Any, target_org_id: Optional[str]):
    user_org_id = getattr(user, "organization_id", None)
    if user_org_id and target_org_id and user_org_id != target_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-organization resource access is forbidden. User org: '{user_org_id}', Target org: '{target_org_id}'."
        )

def _get_user_info(user: Any) -> Tuple[str, str, Optional[str]]:
    name = getattr(user, "full_name", None) or getattr(user, "user_name", None) or getattr(user, "email", "Compliance Officer")
    role = getattr(user, "role", "Compliance Officer")
    user_id = str(getattr(user, "id", "")) if hasattr(user, "id") else None
    return name, role, user_id

class TaskExecutionService:
    """
    Operational Compliance Execution & Monitoring Service.
    Handles assignments, status transitions, operational evidence, activity tracking,
    and deterministic structured event trigger deadlines.
    """

    @classmethod
    def transition_status(
        cls,
        task_id: str,
        target_status: str,
        current_user: Any,
        db: Session,
        reason: Optional[str] = None
    ) -> ComplianceTask:
        _verify_authorization(current_user, f"transition task status to {target_status}")
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

        _verify_organization_access(current_user, task.organization_id)

        old_status = task.status
        if old_status == target_status:
            return task

        # Deterministic State Machine Validation
        allowed_targets = VALID_TRANSITIONS.get(old_status, set())
        if target_status not in allowed_targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state transition from '{old_status}' to '{target_status}'. Allowed transitions: {sorted(list(allowed_targets)) if allowed_targets else 'None (Terminal state)'}"
            )

        user_name, user_role, user_id = _get_user_info(current_user)

        # Apply transition
        task.status = target_status
        task.updated_at = datetime.datetime.utcnow()

        if target_status == "COMPLETED":
            task.completed_at = datetime.datetime.utcnow()
            task.completed_by = user_name
        elif target_status == "REOPENED":
            task.reopened_at = datetime.datetime.utcnow()
            task.reopened_by = user_name

        # Create Activity Record
        activity = ComplianceTaskActivity(
            task_id=task.id,
            organization_id=task.organization_id,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            activity_type="STATUS_CHANGED",
            message=f"Status transitioned from {old_status} to {target_status}." + (f" Reason: {reason}" if reason else ""),
            activity_metadata={"old_status": old_status, "new_status": target_status, "reason": reason}
        )
        db.add(activity)

        # Create Immutable Audit Log
        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action=f"TASK_STATUS_{old_status}_TO_{target_status}",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"previous_status": old_status, "new_status": target_status, "reason": reason}
        )
        db.add(audit)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def assign_task(
        cls,
        task_id: str,
        assign_in: TaskAssignRequest,
        current_user: Any,
        db: Session
    ) -> ComplianceTask:
        _verify_authorization(current_user, "assign compliance tasks")
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

        _verify_organization_access(current_user, task.organization_id)

        user_name, user_role, user_id = _get_user_info(current_user)
        old_assignee = task.assignee
        old_function = task.responsible_function

        task.assignee = assign_in.assignee
        if assign_in.responsible_function:
            task.responsible_function = assign_in.responsible_function
        task.updated_at = datetime.datetime.utcnow()

        activity = ComplianceTaskActivity(
            task_id=task.id,
            organization_id=task.organization_id,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            activity_type="ASSIGNED",
            message=f"Task assigned to '{assign_in.assignee}' (Function: {task.responsible_function or 'General'})." + (f" Notes: {assign_in.notes}" if assign_in.notes else ""),
            activity_metadata={"old_assignee": old_assignee, "new_assignee": assign_in.assignee, "notes": assign_in.notes}
        )
        db.add(activity)

        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="TASK_ASSIGNED",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"old_assignee": old_assignee, "new_assignee": assign_in.assignee, "responsible_function": task.responsible_function}
        )
        db.add(audit)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def add_evidence(
        cls,
        task_id: str,
        evidence_in: EvidenceCreate,
        current_user: Any,
        db: Session
    ) -> ComplianceTaskEvidence:
        _verify_authorization(current_user, "upload operational evidence")
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

        _verify_organization_access(current_user, task.organization_id)

        user_name, user_role, user_id = _get_user_info(current_user)

        evidence = ComplianceTaskEvidence(
            task_id=task.id,
            organization_id=task.organization_id,
            uploaded_by=user_name,
            uploader_role=user_role,
            evidence_type=evidence_in.evidence_type.upper(),
            file_name=evidence_in.file_name,
            file_url=evidence_in.file_url,
            description=evidence_in.description,
            evidence_date=evidence_in.evidence_date or datetime.datetime.utcnow()
        )
        db.add(evidence)

        activity = ComplianceTaskActivity(
            task_id=task.id,
            organization_id=task.organization_id,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            activity_type="EVIDENCE_ADDED",
            message=f"Attached operational evidence: {evidence_in.file_name} ({evidence_in.evidence_type}).",
            activity_metadata={"file_name": evidence_in.file_name, "evidence_type": evidence_in.evidence_type}
        )
        db.add(activity)

        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="TASK_EVIDENCE_ATTACHED",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"file_name": evidence_in.file_name, "evidence_type": evidence_in.evidence_type}
        )
        db.add(audit)
        db.commit()
        db.refresh(evidence)
        return evidence

    @classmethod
    def complete_task(
        cls,
        task_id: str,
        current_user: Any,
        db: Session,
        complete_in: Optional[TaskCompleteRequest] = None
    ) -> ComplianceTask:
        _verify_authorization(current_user, "complete compliance task")
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

        _verify_organization_access(current_user, task.organization_id)

        if task.status == "COMPLETED":
            return task

        if task.status in {"CANCELLED", "SUPERSEDED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete task with status '{task.status}'."
            )

        user_name, user_role, user_id = _get_user_info(current_user)
        notes = complete_in.confirmation_notes if complete_in else None

        task.status = "COMPLETED"
        task.completed_at = datetime.datetime.utcnow()
        task.completed_by = user_name
        task.updated_at = datetime.datetime.utcnow()

        activity = ComplianceTaskActivity(
            task_id=task.id,
            organization_id=task.organization_id,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            activity_type="COMPLETED",
            message=f"Task completed and certified by {user_name}." + (f" Notes: {notes}" if notes else ""),
            activity_metadata={"completed_by": user_name, "completed_at": str(task.completed_at), "notes": notes}
        )
        db.add(activity)

        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="TASK_COMPLETED",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"completed_by": user_name, "completed_at": str(task.completed_at), "notes": notes}
        )
        db.add(audit)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def reopen_task(
        cls,
        task_id: str,
        reopen_in: TaskReopenRequest,
        current_user: Any,
        db: Session
    ) -> ComplianceTask:
        _verify_authorization(current_user, "reopen compliance task")
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

        _verify_organization_access(current_user, task.organization_id)

        if task.status != "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reopen task with status '{task.status}'. Only COMPLETED tasks can be reopened."
            )

        user_name, user_role, user_id = _get_user_info(current_user)
        previous_completed_at = str(task.completed_at) if task.completed_at else None
        previous_completed_by = task.completed_by

        task.status = "REOPENED"
        task.reopened_at = datetime.datetime.utcnow()
        task.reopened_by = user_name
        task.updated_at = datetime.datetime.utcnow()

        activity = ComplianceTaskActivity(
            task_id=task.id,
            organization_id=task.organization_id,
            actor_id=user_id,
            actor_name=user_name,
            actor_role=user_role,
            activity_type="REOPENED",
            message=f"Task reopened by {user_name}. Reason: {reopen_in.reopen_reason}",
            activity_metadata={
                "reopened_by": user_name,
                "reopened_at": str(task.reopened_at),
                "reopen_reason": reopen_in.reopen_reason,
                "previous_completed_at": previous_completed_at,
                "previous_completed_by": previous_completed_by
            }
        )
        db.add(activity)

        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="TASK_REOPENED",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"reopened_by": user_name, "reason": reopen_in.reopen_reason}
        )
        db.add(audit)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def process_trigger_event(
        cls,
        event_in: TriggerEventCreate,
        current_user: Any,
        db: Session
    ) -> Tuple[ComplianceTriggerEvent, List[ComplianceTask]]:
        _verify_authorization(current_user, "record compliance trigger event")

        # Determine target organization
        org_id = event_in.organization_id
        if org_id:
            profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == org_id).first()
            if not profile:
                raise HTTPException(status_code=404, detail=f"EnterpriseProfile with ID '{org_id}' not found.")
        else:
            profile = db.query(EnterpriseProfile).first()
            if not profile:
                raise HTTPException(status_code=404, detail="No Enterprise Profile found.")

        _verify_organization_access(current_user, profile.id)

        user_name, user_role, user_id = _get_user_info(current_user)

        # Normalize timestamp to UTC naive for deterministic database storage
        event_ts = event_in.event_timestamp
        if event_ts.tzinfo is not None:
            event_ts = event_ts.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        # 1. Record the trigger event
        trigger_event = ComplianceTriggerEvent(
            organization_id=profile.id,
            event_type=event_in.event_type.upper(),
            event_timestamp=event_ts,
            source=event_in.source,
            description=event_in.description,
            event_metadata=event_in.event_metadata,
            created_by=user_name
        )
        db.add(trigger_event)
        db.commit()
        db.refresh(trigger_event)

        # 2. Find eligible active tasks in the SAME organization
        tasks_query = db.query(ComplianceTask).filter(
            ComplianceTask.organization_id == profile.id,
            ComplianceTask.trigger_type == trigger_event.event_type,
            ComplianceTask.status.notin_(["COMPLETED", "SUPERSEDED", "CANCELLED"])
        ).all()

        affected_tasks: List[ComplianceTask] = []

        for t in tasks_query:
            # Check originating obligation status is ACTIVE
            if t.regulatory_obligation_id:
                ob = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == t.regulatory_obligation_id).first()
                if not ob or ob.status != "ACTIVE":
                    continue

            # Duplicate trigger protection: if already triggered by this exact event, skip mutation
            if t.trigger_event_id == trigger_event.id:
                continue

            previous_trigger_event_id = t.trigger_event_id
            is_reassignment = previous_trigger_event_id is not None and previous_trigger_event_id != trigger_event.id

            # Deterministic calculation from structured metadata
            if t.trigger_offset_value is not None and t.trigger_offset_unit:
                unit = t.trigger_offset_unit.upper()
                val = t.trigger_offset_value
                if unit == "HOURS":
                    delta = datetime.timedelta(hours=val)
                elif unit == "MINUTES":
                    delta = datetime.timedelta(minutes=val)
                elif unit == "DAYS":
                    delta = datetime.timedelta(days=val)
                else:
                    delta = datetime.timedelta(hours=val)

                calc_datetime = trigger_event.event_timestamp + delta
                t.due_date = calc_datetime.date()
                t.trigger_event_id = trigger_event.id
                t.trigger_timestamp = trigger_event.event_timestamp
                t.updated_at = datetime.datetime.utcnow()

                act_type = "TRIGGER_REASSIGNED" if is_reassignment else "TRIGGER_APPLIED"
                activity = ComplianceTaskActivity(
                    task_id=t.id,
                    organization_id=t.organization_id,
                    actor_id=user_id,
                    actor_name=user_name,
                    actor_role=user_role,
                    activity_type=act_type,
                    message=(
                        f"{'Trigger reassigned to' if is_reassignment else 'Trigger event'} '{trigger_event.event_type}' ({trigger_event.source}). "
                        f"Calculated statutory due date: {calc_datetime.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({t.due_rule or 'Statutory window'})."
                    ),
                    activity_metadata={
                        "trigger_event_id": trigger_event.id,
                        "previous_trigger_event_id": previous_trigger_event_id,
                        "event_timestamp": str(trigger_event.event_timestamp),
                        "calculated_due_date": str(calc_datetime),
                        "trigger_offset_value": t.trigger_offset_value,
                        "trigger_offset_unit": t.trigger_offset_unit
                    }
                )
                db.add(activity)
                affected_tasks.append(t)
            else:
                # Safe uncertainty: Keep due_date = None
                t.due_date = None
                t.trigger_event_id = trigger_event.id
                t.trigger_timestamp = trigger_event.event_timestamp
                t.updated_at = datetime.datetime.utcnow()

                act_type = "TRIGGER_REASSIGNED" if is_reassignment else "TRIGGER_APPLIED"
                activity = ComplianceTaskActivity(
                    task_id=t.id,
                    organization_id=t.organization_id,
                    actor_id=user_id,
                    actor_name=user_name,
                    actor_role=user_role,
                    activity_type=act_type,
                    message=f"Trigger event '{trigger_event.event_type}' recorded, but structured offset is missing. Deadline requires manual review.",
                    activity_metadata={
                        "trigger_event_id": trigger_event.id,
                        "previous_trigger_event_id": previous_trigger_event_id
                    }
                )
                db.add(activity)
                affected_tasks.append(t)

        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="COMPLIANCE_TRIGGER_EVENT_RECORDED",
            target_type="COMPLIANCE_TRIGGER_EVENT",
            target_id=trigger_event.id,
            details={
                "event_type": trigger_event.event_type,
                "source": trigger_event.source,
                "organization_id": profile.id,
                "affected_tasks_count": len(affected_tasks)
            }
        )
        db.add(audit)
        db.commit()

        return trigger_event, affected_tasks
