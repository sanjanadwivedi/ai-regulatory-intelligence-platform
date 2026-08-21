import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile
from app.core.database import get_db
from app.core.security import get_current_user, get_current_organization
from app.models.domain import (
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTaskActivity,
    TaskComment,
    Regulation,
    RegulatoryObligation,
    EnterpriseProfile,
    AuditLog
)
from app.schemas.schemas import (
    TaskResponse,
    TaskCreate,
    TaskUpdate,
    TaskAssignRequest,
    TaskStatusTransitionRequest,
    TaskCompleteRequest,
    TaskReopenRequest,
    EvidenceCreate,
    EvidenceResponse,
    ActivityResponse,
    CommentCreate,
    CommentResponse
)
from app.services.task_engine import TaskEngine
from app.services.task_execution_service import TaskExecutionService, _verify_authorization, _verify_organization_access

router = APIRouter()

def _format_task_response(task: ComplianceTask, db: Session) -> dict:
    t_dict = TaskResponse.model_validate(task).model_dump()
    if task.regulation_id:
        reg = db.query(Regulation.title).filter(Regulation.id == task.regulation_id).first()
        t_dict["regulation_title"] = reg[0] if reg else "General Regulatory Directive"
    if task.regulatory_obligation_id:
        ob = db.query(RegulatoryObligation.obligation_code).filter(RegulatoryObligation.id == task.regulatory_obligation_id).first()
        t_dict["obligation_code"] = ob[0] if ob else None

    # Compute operational counts
    ev_count = db.query(ComplianceTaskEvidence).filter(ComplianceTaskEvidence.task_id == task.id).count()
    act_count = db.query(ComplianceTaskActivity).filter(ComplianceTaskActivity.task_id == task.id).count()
    t_dict["evidence_count"] = ev_count
    t_dict["activity_count"] = act_count

    # Overdue and deadline status message logic
    if task.status == "COMPLETED":
        t_dict["is_overdue"] = False
        t_dict["deadline_status_message"] = f"Completed by {task.completed_by or 'Assignee'} on {task.completed_at.strftime('%Y-%m-%d') if task.completed_at else 'Verified'}"
    elif task.due_date is not None:
        t_dict["is_overdue"] = task.due_date < datetime.date.today()
        if task.trigger_timestamp:
            t_dict["deadline_status_message"] = f"Triggered on {task.trigger_timestamp.strftime('%d %b %Y, %H:%M')} — Due: {task.due_date}"
        else:
            t_dict["deadline_status_message"] = f"Due: {task.due_date}"
    else:
        t_dict["is_overdue"] = False
        if task.frequency == "CONTINUOUS":
            t_dict["deadline_status_message"] = "Continuous obligation (no calendar deadline)"
        elif task.trigger_type:
            t_dict["deadline_status_message"] = f"Awaiting trigger event: {task.trigger_type}"
        else:
            t_dict["deadline_status_message"] = "No calendar deadline"

    return t_dict

@router.post("/generate", response_model=List[TaskResponse])
def generate_compliance_tasks(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Deterministically instantiate or update operational compliance tasks strictly for ACTIVE obligations.
    Idempotent and creates an immutable audit trail.
    """
    _verify_authorization(current_user, "generate compliance tasks")
    profile = current_profile

    _verify_organization_access(current_user, profile.id)

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    tasks = TaskEngine.generate_tasks(
        organization_id=profile.id,
        db=db,
        evaluated_by=user_name
    )

    return [_format_task_response(t, db) for t in tasks]

@router.get("", response_model=List[TaskResponse])
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: OPEN, IN_PROGRESS, BLOCKED, COMPLETED, REOPENED, NEEDS_REVIEW"),
    priority: Optional[str] = Query(None, description="Filter by priority: CRITICAL, HIGH, MEDIUM, LOW"),
    responsible_function: Optional[str] = Query(None, description="Filter by responsible_function"),
    regulation_id: Optional[str] = Query(None, description="Filter by regulation_id"),
    regulatory_obligation_id: Optional[str] = Query(None, description="Filter by regulatory_obligation_id"),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    query = db.query(ComplianceTask)

    user_org_id = getattr(current_user, "organization_id", None)
    if user_org_id:
        query = query.filter(ComplianceTask.organization_id == user_org_id)

    if status:
        query = query.filter(ComplianceTask.status == status)
    if priority:
        query = query.filter(ComplianceTask.priority == priority.upper())
    if responsible_function:
        query = query.filter(ComplianceTask.responsible_function == responsible_function)
    if regulation_id:
        query = query.filter(ComplianceTask.regulation_id == regulation_id)
    if regulatory_obligation_id:
        query = query.filter(ComplianceTask.regulatory_obligation_id == regulatory_obligation_id)
    if assignee:
        query = query.filter(ComplianceTask.assignee == assignee)

    tasks = query.order_by(ComplianceTask.created_at.desc()).all()
    return [_format_task_response(t, db) for t in tasks]

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")
    _verify_organization_access(current_user, task.organization_id)
    return _format_task_response(task, db)

@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: str,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    """
    Controlled operational update of task fields.
    """
    update_data = task_in.model_dump(exclude_unset=True)
    if "status" in update_data:
        task = TaskExecutionService.transition_status(
            task_id=task_id,
            target_status=update_data["status"],
            current_user=current_user,
            db=db
        )
    else:
        task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Compliance task {task_id} not found")

    for field, val in update_data.items():
        if field != "status":
            setattr(task, field, val)

    task.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _format_task_response(task, db)

@router.post("/{task_id}/assign", response_model=TaskResponse)
def assign_task_endpoint(
    task_id: str,
    assign_in: TaskAssignRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    task = TaskExecutionService.assign_task(
        task_id=task_id,
        assign_in=assign_in,
        current_user=current_user,
        db=db
    )
    return _format_task_response(task, db)

@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task_endpoint(
    task_id: str,
    complete_in: Optional[TaskCompleteRequest] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    task = TaskExecutionService.complete_task(
        task_id=task_id,
        current_user=current_user,
        db=db,
        complete_in=complete_in
    )
    return _format_task_response(task, db)

@router.post("/{task_id}/reopen", response_model=TaskResponse)
def reopen_task_endpoint(
    task_id: str,
    reopen_in: TaskReopenRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    task = TaskExecutionService.reopen_task(
        task_id=task_id,
        reopen_in=reopen_in,
        current_user=current_user,
        db=db
    )
    return _format_task_response(task, db)

@router.post("/{task_id}/evidence", response_model=EvidenceResponse)
def upload_task_evidence(
    task_id: str,
    evidence_in: EvidenceCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    evidence = TaskExecutionService.add_evidence(
        task_id=task_id,
        evidence_in=evidence_in,
        current_user=current_user,
        db=db
    )
    return EvidenceResponse.model_validate(evidence)

@router.get("/{task_id}/evidence", response_model=List[EvidenceResponse])
def list_task_evidence(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    evidence_list = db.query(ComplianceTaskEvidence).filter(
        ComplianceTaskEvidence.task_id == task_id
    ).order_by(ComplianceTaskEvidence.created_at.desc()).all()
    return [EvidenceResponse.model_validate(e) for e in evidence_list]

@router.get("/{task_id}/activities", response_model=List[ActivityResponse])
def list_task_activities(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    activities = db.query(ComplianceTaskActivity).filter(
        ComplianceTaskActivity.task_id == task_id
    ).order_by(ComplianceTaskActivity.created_at.desc()).all()
    return [ActivityResponse.model_validate(a) for a in activities]

@router.post("/{task_id}/comments", response_model=CommentResponse)
def add_task_comment(
    task_id: str,
    comment_in: CommentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    _verify_authorization(current_user, "add task comment")
    task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _verify_organization_access(current_user, task.organization_id)

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    user_role = getattr(current_user, "role", "Compliance Officer")
    user_id = str(getattr(current_user, "id", "")) if hasattr(current_user, "id") else None

    comment = TaskComment(
        task_id=task.id,
        author_name=user_name,
        author_role=user_role,
        comment_text=comment_in.comment_text
    )
    db.add(comment)

    activity = ComplianceTaskActivity(
        task_id=task.id,
        organization_id=task.organization_id,
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        activity_type="COMMENT_ADDED",
        message=f"Added comment: {comment_in.comment_text[:80]}..." if len(comment_in.comment_text) > 80 else f"Added comment: {comment_in.comment_text}",
        activity_metadata={"comment_text": comment_in.comment_text}
    )
    db.add(activity)

    audit = AuditLog(
        user_name=user_name,
        user_role=user_role,
        action="TASK_COMMENT_ADDED",
        target_type="COMPLIANCE_TASK",
        target_id=task.id,
        details={"comment_preview": comment_in.comment_text[:100]}
    )
    db.add(audit)
    db.commit()
    db.refresh(comment)
    return CommentResponse.model_validate(comment)

@router.post("", response_model=TaskResponse)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    _verify_authorization(current_user, "create manual compliance task")
    if task_in.organization_id:
        _verify_organization_access(current_user, task_in.organization_id)

    task = ComplianceTask(**task_in.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    user_role = getattr(current_user, "role", "Compliance Officer")
    user_id = str(getattr(current_user, "id", "")) if hasattr(current_user, "id") else None

    activity = ComplianceTaskActivity(
        task_id=task.id,
        organization_id=task.organization_id,
        actor_id=user_id,
        actor_name=user_name,
        actor_role=user_role,
        activity_type="CREATED",
        message=f"Task '{task.title}' created.",
        activity_metadata={"title": task.title, "assignee": task.assignee}
    )
    db.add(activity)

    audit = AuditLog(
        user_name=user_name,
        user_role=user_role,
        action="TASK_CREATED",
        target_type="COMPLIANCE_TASK",
        target_id=task.id,
        details={"title": task.title, "assignee": task.assignee, "due_date": str(task.due_date) if task.due_date else None}
    )
    db.add(audit)
    db.commit()

    return _format_task_response(task, db)

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_profile: EnterpriseProfile = Depends(get_current_organization)
):
    task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != task.status:
        task = TaskExecutionService.transition_status(
            task_id=task_id,
            target_status=update_data["status"],
            current_user=current_user,
            db=db
        )

    for field, val in update_data.items():
        if field != "status":
            setattr(task, field, val)

    task.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(task)

    return _format_task_response(task, db)
