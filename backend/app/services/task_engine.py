import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryObligation,
    ComplianceTask,
    AuditLog
)

logger = logging.getLogger("compliance_platform.task_engine")

ENGINE_VERSION = "v1.0.0-deterministic"

class TaskEngine:
    """
    Deterministic Compliance Task & Action Engine.
    Strictly gates instantiation:
      - ONLY ACTIVE RegulatoryObligation records may generate operational compliance tasks.
      - NOT_APPLICABLE assessments generate ZERO tasks.
      - REQUIRES_REVIEW assessments generate ZERO tasks.
      - REQUIRES_REVIEW / SUPERSEDED obligations generate ZERO active tasks.
      - Website regulatory signals NEVER generate tasks.
      - Deadlines are preserved as due_rule; due_date is NULL unless an authoritative calendar date exists.
    """

    @classmethod
    def generate_tasks(
        cls,
        organization_id: str,
        db: Session,
        evaluated_by: str = "Compliance Officer"
    ) -> List[ComplianceTask]:
        """
        Instantiate or update operational compliance tasks strictly for ACTIVE obligations.
        Idempotently persists records and writes an immutable audit event.
        """
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            logger.error("Cannot generate compliance tasks: EnterpriseProfile %s not found", organization_id)
            return []

        # 1. Load all obligations for this organization
        all_obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id
        ).all()

        active_obligations = [o for o in all_obligations if o.status == "ACTIVE"]
        non_active_obligation_ids = {o.id for o in all_obligations if o.status != "ACTIVE"}

        # 2. If existing tasks point to obligations that are no longer ACTIVE, mark them SUPERSEDED
        if non_active_obligation_ids:
            stale_tasks = db.query(ComplianceTask).filter(
                ComplianceTask.organization_id == organization_id,
                ComplianceTask.regulatory_obligation_id.in_(non_active_obligation_ids),
                ComplianceTask.status.notin_(["SUPERSEDED", "COMPLETED", "CANCELLED"])
            ).all()
            for st in stale_tasks:
                st.status = "SUPERSEDED"
                st.updated_at = datetime.datetime.utcnow()
            if stale_tasks:
                db.commit()

        generated_tasks: List[ComplianceTask] = []
        created_count = 0
        updated_count = 0

        # 3. For each ACTIVE obligation, deterministically create or update an operational task
        for obligation in active_obligations:
            reg = db.query(Regulation).filter(Regulation.id == obligation.regulation_id).first()
            reg_title = reg.title if reg else "Authoritative Regulation"

            task, is_new = cls._upsert_task_for_obligation(
                profile=profile,
                obligation=obligation,
                reg_title=reg_title,
                db=db
            )
            if is_new:
                created_count += 1
            else:
                updated_count += 1
            generated_tasks.append(task)

        # 4. Write immutable AuditLog entry
        audit = AuditLog(
            user_name=evaluated_by,
            user_role="Compliance Officer",
            action="COMPLIANCE_TASKS_GENERATED",
            target_type="COMPLIANCE_TASK",
            target_id=organization_id,
            details={
                "organization_id": organization_id,
                "organization_name": profile.organization_name,
                "active_obligations_evaluated": len(active_obligations),
                "tasks_created": created_count,
                "tasks_updated": updated_count,
                "tasks_total": len(generated_tasks),
                "tasks_skipped": 0,
                "engine_version": ENGINE_VERSION
            }
        )
        db.add(audit)
        db.commit()

        return generated_tasks

    @classmethod
    def _upsert_task_for_obligation(
        cls,
        profile: EnterpriseProfile,
        obligation: RegulatoryObligation,
        reg_title: str,
        db: Session
    ) -> tuple[ComplianceTask, bool]:
        """
        Deterministically create or update a single ComplianceTask for an active obligation.
        """
        existing = db.query(ComplianceTask).filter(
            ComplianceTask.organization_id == profile.id,
            ComplianceTask.regulatory_obligation_id == obligation.id
        ).first()

        is_new = False
        default_assignee = obligation.responsible_function or "Information Security / SecOps / CISO"
        task_title = f"Implement: {obligation.title}"
        task_desc = (
            f"Operational compliance action mandated by {obligation.source_citation}.\n\n"
            f"Statutory Requirement:\n{obligation.description}\n\n"
            f"Compliance Rule: {obligation.due_rule or 'Continuous Compliance'}"
        )

        if not existing:
            is_new = True
            existing = ComplianceTask(
                organization_id=profile.id,
                regulatory_obligation_id=obligation.id,
                regulation_id=obligation.regulation_id,
                control_code=obligation.obligation_code,
                title=task_title,
                description=task_desc,
                assignee=default_assignee,
                reviewer="Compliance Officer",
                priority=obligation.priority or "HIGH",
                status="OPEN",
                due_date=None,  # Preserved: NO hallucinated calendar dates!
                responsible_function=obligation.responsible_function,
                due_rule=obligation.due_rule,
                frequency=obligation.frequency,
                trigger_type=obligation.trigger_type,
                trigger_offset_value=obligation.trigger_offset_value,
                trigger_offset_unit=obligation.trigger_offset_unit,
                source_citation=obligation.source_citation,
                authoritative_source_url=obligation.authoritative_source_url,
                regulatory_evidence_refs=obligation.regulatory_evidence_refs,
                organization_evidence_refs=obligation.organization_evidence_refs,
                operational_evidence=None,
                engine_version=ENGINE_VERSION
            )
            db.add(existing)
        else:
            # If the task was previously SUPERSEDED but the obligation is now ACTIVE, reactivate to OPEN
            if existing.status == "SUPERSEDED":
                existing.status = "OPEN"

            # Update provenance and statutory fields while preserving user status if in progress/completed
            existing.control_code = obligation.obligation_code
            existing.due_rule = obligation.due_rule
            existing.frequency = obligation.frequency
            existing.trigger_type = obligation.trigger_type
            existing.trigger_offset_value = obligation.trigger_offset_value
            existing.trigger_offset_unit = obligation.trigger_offset_unit
            existing.responsible_function = obligation.responsible_function
            existing.source_citation = obligation.source_citation
            existing.authoritative_source_url = obligation.authoritative_source_url
            existing.regulatory_evidence_refs = obligation.regulatory_evidence_refs
            existing.organization_evidence_refs = obligation.organization_evidence_refs
            existing.priority = obligation.priority or existing.priority
            existing.engine_version = ENGINE_VERSION
            existing.updated_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(existing)
        return existing, is_new
