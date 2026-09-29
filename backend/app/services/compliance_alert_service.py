import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTaskActivity,
    ComplianceAlert,
    AuditLog
)
from app.services.task_execution_service import (
    _verify_authorization,
    _verify_organization_access,
    _get_user_info
)

class ComplianceAlertService:
    """
    Deterministic Compliance Alert Engine.
    Evaluates and generates alerts strictly from authoritative upstream state (tasks, obligations, assessments).
    Idempotent and guarantees 100% upstream immutability on resolution.
    """

    @classmethod
    def evaluate_and_sync_alerts(cls, organization_id: str, db: Session) -> List[ComplianceAlert]:
        """
        Evaluates the current state of an organization and creates or updates alerts idempotently.
        """
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Enterprise profile {organization_id} not found")

        today = datetime.date.today()

        # Fetch authoritative models
        tasks = db.query(ComplianceTask).filter(ComplianceTask.organization_id == organization_id).all()
        obligations = db.query(RegulatoryObligation).filter(RegulatoryObligation.organization_id == organization_id).all()
        assessments = db.query(RegulatoryApplicabilityAssessment).filter(RegulatoryApplicabilityAssessment.organization_id == organization_id).all()
        evidence_records = db.query(ComplianceTaskEvidence).filter(ComplianceTaskEvidence.organization_id == organization_id).all()

        evidence_by_task_id: Dict[str, List[ComplianceTaskEvidence]] = {}
        for ev in evidence_records:
            evidence_by_task_id.setdefault(ev.task_id, []).append(ev)

        candidate_alerts: List[Dict[str, Any]] = []

        # 1. OVERDUE TASKS
        for t in tasks:
            if t.status not in {"COMPLETED", "SUPERSEDED", "CANCELLED"} and t.due_date is not None and t.due_date < today:
                candidate_alerts.append({
                    "alert_type": "OVERDUE_TASK",
                    "severity": "CRITICAL",
                    "title": f"Overdue Task: {t.title}",
                    "description": f"Task '{t.title}' is overdue statutory deadline of {t.due_date}. (Control Code: {t.control_code or 'N/A'}).",
                    "source_entity_type": "COMPLIANCE_TASK",
                    "source_entity_id": t.id,
                    "regulation_id": t.regulation_id,
                    "obligation_id": t.regulatory_obligation_id,
                    "task_id": t.id,
                    "evidence_refs": {"due_date": str(t.due_date), "control_code": t.control_code}
                })

        # 2. BLOCKED CRITICAL & HIGH PRIORITY TASKS
        for t in tasks:
            if t.status == "BLOCKED":
                sev = "CRITICAL" if t.priority == "CRITICAL" else ("HIGH" if t.priority == "HIGH" else "MEDIUM")
                al_type = "CRITICAL_BLOCKED_TASK" if t.priority == "CRITICAL" else "HIGH_PRIORITY_BLOCKED_TASK"
                candidate_alerts.append({
                    "alert_type": al_type,
                    "severity": sev,
                    "title": f"Blocked Task ({t.priority}): {t.title}",
                    "description": f"Task '{t.title}' is currently BLOCKED in operational execution.",
                    "source_entity_type": "COMPLIANCE_TASK",
                    "source_entity_id": t.id,
                    "regulation_id": t.regulation_id,
                    "obligation_id": t.regulatory_obligation_id,
                    "task_id": t.id,
                    "evidence_refs": {"priority": t.priority, "status": t.status}
                })

        # 3. EVIDENCE GAPS FOR ACTIVE OBLIGATIONS & ORPHANED OBLIGATIONS
        for obl in obligations:
            if obl.status == "ACTIVE":
                related_tasks = [t for t in tasks if t.regulatory_obligation_id == obl.id and t.status != "SUPERSEDED"]
                if not related_tasks:
                    candidate_alerts.append({
                        "alert_type": "ORPHANED_ACTIVE_OBLIGATION",
                        "severity": "HIGH",
                        "title": f"Active Obligation Missing Operational Task: {obl.obligation_code}",
                        "description": f"Statutory obligation '{obl.obligation_code}' is ACTIVE but has no operational tasks created.",
                        "source_entity_type": "REGULATORY_OBLIGATION",
                        "source_entity_id": obl.id,
                        "regulation_id": obl.regulation_id,
                        "obligation_id": obl.id,
                        "task_id": None,
                        "evidence_refs": {"obligation_code": obl.obligation_code}
                    })
                else:
                    ev_count = sum(len(evidence_by_task_id.get(t.id, [])) for t in related_tasks)
                    if ev_count == 0:
                        candidate_alerts.append({
                            "alert_type": "EVIDENCE_GAP",
                            "severity": "HIGH",
                            "title": f"Evidence Gap for Obligation {obl.obligation_code}",
                            "description": f"ACTIVE obligation '{obl.obligation_code}' has operational tasks but zero operational evidence records attached.",
                            "source_entity_type": "REGULATORY_OBLIGATION",
                            "source_entity_id": obl.id,
                            "regulation_id": obl.regulation_id,
                            "obligation_id": obl.id,
                            "task_id": related_tasks[0].id if related_tasks else None,
                            "evidence_refs": {"obligation_code": obl.obligation_code, "task_count": len(related_tasks)}
                        })

        # 4. COMPLETED WITHOUT EVIDENCE
        for t in tasks:
            if t.status == "COMPLETED" and len(evidence_by_task_id.get(t.id, [])) == 0:
                candidate_alerts.append({
                    "alert_type": "COMPLETED_WITHOUT_EVIDENCE",
                    "severity": "MEDIUM",
                    "title": f"Completed Task Without Evidence: {t.title}",
                    "description": f"Task '{t.title}' was marked COMPLETED without attached operational verification evidence.",
                    "source_entity_type": "COMPLIANCE_TASK",
                    "source_entity_id": t.id,
                    "regulation_id": t.regulation_id,
                    "obligation_id": t.regulatory_obligation_id,
                    "task_id": t.id,
                    "evidence_refs": {"completed_at": str(t.completed_at), "completed_by": t.completed_by}
                })

        # 5. REQUIRES REVIEW ASSESSMENTS
        for a in assessments:
            if a.status == "REQUIRES_REVIEW":
                reg = db.query(Regulation).filter(Regulation.id == a.regulation_id).first()
                reg_title = reg.title if reg else "Regulation"
                candidate_alerts.append({
                    "alert_type": "REVIEW_REQUIRED",
                    "severity": "MEDIUM",
                    "title": f"Applicability Requires Legal Review: {reg_title}",
                    "description": f"Applicability assessment for '{reg_title}' is marked REQUIRES_REVIEW: {a.rationale or 'Inconclusive criteria'}.",
                    "source_entity_type": "REGULATORY_APPLICABILITY_ASSESSMENT",
                    "source_entity_id": a.id,
                    "regulation_id": a.regulation_id,
                    "obligation_id": None,
                    "task_id": None,
                    "evidence_refs": {"missing_information": a.missing_information}
                })

        # 6. MISSING TRIGGER METADATA
        for t in tasks:
            if t.trigger_type is not None and (t.trigger_offset_value is None or not t.trigger_offset_unit):
                candidate_alerts.append({
                    "alert_type": "MISSING_TRIGGER_METADATA",
                    "severity": "MEDIUM",
                    "title": f"Missing Structured Trigger Timing: {t.title}",
                    "description": f"Task has trigger_type '{t.trigger_type}' but missing structured offset value or unit.",
                    "source_entity_type": "COMPLIANCE_TASK",
                    "source_entity_id": t.id,
                    "regulation_id": t.regulation_id,
                    "obligation_id": t.regulatory_obligation_id,
                    "task_id": t.id,
                    "evidence_refs": {"trigger_type": t.trigger_type}
                })

        # Idempotently persist or sync candidate alerts
        active_alerts: List[ComplianceAlert] = []

        for cand in candidate_alerts:
            existing = db.query(ComplianceAlert).filter(
                ComplianceAlert.organization_id == organization_id,
                ComplianceAlert.alert_type == cand["alert_type"],
                ComplianceAlert.source_entity_type == cand["source_entity_type"],
                ComplianceAlert.source_entity_id == cand["source_entity_id"]
            ).first()

            if not existing:
                alert = ComplianceAlert(
                    organization_id=organization_id,
                    alert_type=cand["alert_type"],
                    severity=cand["severity"],
                    title=cand["title"],
                    description=cand["description"],
                    source_entity_type=cand["source_entity_type"],
                    source_entity_id=cand["source_entity_id"],
                    regulation_id=cand.get("regulation_id"),
                    obligation_id=cand.get("obligation_id"),
                    task_id=cand.get("task_id"),
                    status="ACTIVE",
                    evidence_refs=cand.get("evidence_refs"),
                    created_at=datetime.datetime.utcnow()
                )
                db.add(alert)
                active_alerts.append(alert)
            else:
                if existing.status != "ACTIVE":
                    existing.status = "ACTIVE"
                    existing.resolved_at = None
                    existing.resolution_note = None
                active_alerts.append(existing)

        db.commit()
        return active_alerts

    @classmethod
    def resolve_alert(
        cls,
        alert_id: str,
        current_user: Any,
        resolution_notes: str,
        db: Session,
        organization_id: str
    ) -> ComplianceAlert:
        """
        Resolves an alert operationally.
        GUARANTEE: NEVER modifies originating regulation, obligation, applicability assessment, or task legal metadata.
        """
        _verify_authorization(current_user, "resolve compliance alert")

        alert = db.query(ComplianceAlert).filter(
            ComplianceAlert.id == alert_id,
            ComplianceAlert.organization_id == organization_id
        ).first()
        if not alert:
            raise HTTPException(status_code=404, detail=f"Compliance alert {alert_id} not found")

        if alert.status == "RESOLVED":
            return alert

        user_name, user_role, user_id = _get_user_info(current_user)
        previous_status = alert.status

        # 1. Update operational alert state
        alert.status = "RESOLVED"
        alert.resolved_at = datetime.datetime.utcnow()
        alert.resolved_by = user_name
        alert.resolution_notes = resolution_notes

        # 2. Add ComplianceTaskActivity if alert is linked to a task
        if alert.task_id:
            activity = ComplianceTaskActivity(
                task_id=alert.task_id,
                organization_id=alert.organization_id,
                actor_id=user_id,
                actor_name=user_name,
                actor_role=user_role,
                activity_type="ALERT_RESOLVED",
                message=f"Compliance alert '{alert.title}' marked RESOLVED by {user_name}. Notes: {resolution_notes}",
                activity_metadata={
                    "alert_id": alert.id,
                    "alert_type": alert.alert_type,
                    "resolution_notes": resolution_notes
                }
            )
            db.add(activity)

        # 3. Create Immutable AuditLog
        audit = AuditLog(
            user_name=user_name,
            user_role=user_role,
            action="COMPLIANCE_ALERT_RESOLVED",
            target_type="COMPLIANCE_ALERT",
            target_id=alert.id,
            details={
                "organization_id": alert.organization_id,
                "alert_id": alert.id,
                "alert_type": alert.alert_type,
                "previous_status": previous_status,
                "new_status": "RESOLVED",
                "resolution_notes": resolution_notes
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(alert)
        return alert
