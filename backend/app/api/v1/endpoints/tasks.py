from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.domain import ComplianceTask, Regulation, AuditLog
from app.schemas.schemas import TaskResponse, TaskCreate, TaskUpdate

router = APIRouter()

@router.get("", response_model=List[TaskResponse])
def list_tasks(
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(ComplianceTask).order_by(ComplianceTask.due_date.asc())
    if status:
        query = query.filter(ComplianceTask.status == status)
    if assignee:
        query = query.filter(ComplianceTask.assignee == assignee)

    tasks = query.all()
    resp = []
    for task in tasks:
        reg = db.query(Regulation.title).filter(Regulation.id == task.regulation_id).first()
        t_dict = TaskResponse.model_validate(task).model_dump()
        t_dict["regulation_title"] = reg[0] if reg else "General Regulatory Directive"
        resp.append(t_dict)
    return resp

@router.post("", response_model=TaskResponse)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = ComplianceTask(**task_in.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
    user_role = getattr(current_user, "role", "Compliance Officer")

    audit = AuditLog(
        user_name=user_name,
        user_role=user_role,
        action="TASK_CREATED",
        target_type="COMPLIANCE_TASK",
        target_id=task.id,
        details={"title": task.title, "assignee": task.assignee, "due_date": str(task.due_date)}
    )
    db.add(audit)
    db.commit()

    reg = db.query(Regulation.title).filter(Regulation.id == task.regulation_id).first()
    res_dict = TaskResponse.model_validate(task).model_dump()
    res_dict["regulation_title"] = reg[0] if reg else "General Regulatory Directive"
    return res_dict

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    task = db.query(ComplianceTask).filter(ComplianceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != task.status:
        user_name = getattr(current_user, "full_name", None) or getattr(current_user, "user_name", None) or getattr(current_user, "email", "Compliance Officer")
        user_role = getattr(current_user, "role", "Compliance Manager")
        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,

            action=f"WORKFLOW_TRANSITION_{task.status}_TO_{update_data['status']}",
            target_type="COMPLIANCE_TASK",
            target_id=task.id,
            details={"previous_status": task.status, "new_status": update_data["status"]}
        )
        db.add(audit)

    for field, val in update_data.items():
        setattr(task, field, val)

    db.commit()
    db.refresh(task)

    reg = db.query(Regulation.title).filter(Regulation.id == task.regulation_id).first()
    res_dict = TaskResponse.model_validate(task).model_dump()
    res_dict["regulation_title"] = reg[0] if reg else "General Regulatory Directive"
    return res_dict
