import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryObligation,
    ComplianceTask,
    AuditLog,
    ObligationControlMapping,
    ControlAssessment
)

logger = logging.getLogger("compliance_platform.task_engine")

ENGINE_VERSION = "v1.0.0-deterministic"

class TaskEngine:
    """
    Deterministic Compliance Task & Action Engine.
    """

    @classmethod
    def generate_tasks(
        cls,
        organization_id: str,
        db: Session,
        evaluated_by: str = "Compliance Officer"
    ) -> List[ComplianceTask]:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            logger.error("Cannot generate compliance tasks: EnterpriseProfile %s not found", organization_id)
            return []

        all_obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id
        ).all()
        active_ob_ids = {o.id for o in all_obligations if o.status == "ACTIVE"}
        non_active_ob_ids = {o.id for o in all_obligations if o.status != "ACTIVE"}

        # Supersede tasks for non-active obligations
        if non_active_ob_ids:
            stale_tasks = db.query(ComplianceTask).filter(
                ComplianceTask.organization_id == organization_id,
                ComplianceTask.regulatory_obligation_id.in_(non_active_ob_ids),
                ComplianceTask.status.notin_(["SUPERSEDED", "COMPLETED", "CANCELLED"])
            ).all()
            for st in stale_tasks:
                st.status = "SUPERSEDED"
                st.updated_at = datetime.datetime.utcnow()

        generated_tasks: List[ComplianceTask] = []
        created_count = 0
        updated_count = 0

        # Step 1: Handle legacy obligations without mapped controls
        mappings = db.query(ObligationControlMapping).filter(
            ObligationControlMapping.organization_id == organization_id,
            ObligationControlMapping.active == 1
        ).all()
        mapped_ob_ids = {m.obligation_id for m in mappings}
        unmapped_active_obs = [o for o in all_obligations if o.id in active_ob_ids and o.id not in mapped_ob_ids]

        for obligation in unmapped_active_obs:
            reg = db.query(Regulation).filter(Regulation.id == obligation.regulation_id).first()
            reg_title = reg.title if reg else "Authoritative Regulation"
            task, is_new, is_updated = cls._upsert_task_for_obligation(profile, obligation, reg_title, db)
            if is_new:
                created_count += 1
            elif is_updated:
                updated_count += 1
            generated_tasks.append(task)

        # Step 2: Handle mapped controls via ControlAssessment
        assessments = db.query(ControlAssessment).filter(
            ControlAssessment.organization_id == organization_id
        ).all()
        # Get the latest assessment for each control
        latest_assessments = {}
        for ca in assessments:
            if ca.control_id not in latest_assessments or ca.evaluated_at > latest_assessments[ca.control_id].evaluated_at:
                latest_assessments[ca.control_id] = ca

        for control_id, ca in latest_assessments.items():
            # Check if this control is mapped to any ACTIVE obligations
            control_mappings = [m for m in mappings if m.control_id == control_id and m.obligation_id in active_ob_ids]
            if not control_mappings:
                continue

            # It's mapped to active obligations. Generate task based on assessment status.
            status = ca.assessment_status
            if status in ["CONTROL_GAP", "INEFFECTIVE"]:
                task_type = "REMEDIATION"
            elif status == "CONTROL_REVIEW_REQUIRED":
                task_type = "REVIEW"
            elif status == "EFFECTIVE":
                # Mark existing REMEDIATION tasks as SUPERSEDED
                open_tasks = db.query(ComplianceTask).filter(
                    ComplianceTask.organization_id == organization_id,
                    ComplianceTask.control_id == control_id,
                    ComplianceTask.status == "OPEN",
                    ComplianceTask.task_type == "REMEDIATION"
                ).all()
                for ot in open_tasks:
                    ot.status = "SUPERSEDED"
                    ot.updated_at = datetime.datetime.utcnow()
                continue
            else:
                continue

            # Find or create task for this control
            existing = db.query(ComplianceTask).filter(
                ComplianceTask.organization_id == organization_id,
                ComplianceTask.control_id == control_id,
                ComplianceTask.task_type == task_type
            ).first()

            if not existing:
                # Need to create one. Link it to the first active obligation for backward compat
                ob = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == control_mappings[0].obligation_id).first()
                reg = db.query(Regulation).filter(Regulation.id == ob.regulation_id).first()
                
                existing = ComplianceTask(
                    organization_id=organization_id,
                    regulatory_obligation_id=ob.id,
                    regulation_id=ob.regulation_id,
                    control_id=control_id,
                    control_code=ob.obligation_code,
                    task_type=task_type,
                    title=f"Remediate Control: {control_id}" if task_type == "REMEDIATION" else f"Review Control: {control_id}",
                    description=f"Action required for control {control_id} due to {status}",
                    assignee=ob.responsible_function or "Information Security / SecOps / CISO",
                    reviewer="Compliance Officer",
                    priority=ob.priority or "HIGH",
                    status="OPEN",
                    due_date=None,
                    responsible_function=ob.responsible_function,
                    due_rule=ob.due_rule,
                    frequency=ob.frequency,
                    trigger_type=ob.trigger_type,
                    trigger_offset_value=ob.trigger_offset_value,
                    trigger_offset_unit=ob.trigger_offset_unit,
                    source_citation=ob.source_citation,
                    authoritative_source_url=ob.authoritative_source_url,
                    regulatory_evidence_refs=ob.regulatory_evidence_refs,
                    organization_evidence_refs=ob.organization_evidence_refs,
                    operational_evidence=None,
                    engine_version=ENGINE_VERSION
                )
                db.add(existing)
                created_count += 1
            else:
                if existing.status == "SUPERSEDED":
                    existing.status = "OPEN"
                    existing.updated_at = datetime.datetime.utcnow()
                    updated_count += 1

            generated_tasks.append(existing)

        # 4. Write immutable AuditLog entry
        if created_count > 0 or updated_count > 0 or not db.query(AuditLog).filter(
            AuditLog.organization_id == organization_id,
            AuditLog.action == "COMPLIANCE_TASKS_GENERATED"
        ).first():
            audit = AuditLog(
                organization_id=organization_id,
                user_name=evaluated_by,
                user_role="Compliance Officer",
                action="COMPLIANCE_TASKS_GENERATED",
                target_type="COMPLIANCE_TASK",
                target_id=organization_id,
                details={
                    "organization_id": organization_id,
                    "organization_name": profile.organization_name,
                    "active_obligations_evaluated": len(active_ob_ids),
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
    ) -> tuple[ComplianceTask, bool, bool]:
        existing = db.query(ComplianceTask).filter(
            ComplianceTask.organization_id == profile.id,
            ComplianceTask.regulatory_obligation_id == obligation.id
        ).first()

        is_new = False
        is_updated = False
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
                due_date=None,
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
            if existing.status == "SUPERSEDED":
                existing.status = "OPEN"
                is_updated = True
            
            # Simple check if anything changed
            if existing.control_code != obligation.obligation_code:
                existing.control_code = obligation.obligation_code
                is_updated = True
            if existing.due_rule != obligation.due_rule:
                existing.due_rule = obligation.due_rule
                is_updated = True
            if existing.frequency != obligation.frequency:
                existing.frequency = obligation.frequency
                is_updated = True
            if existing.trigger_type != obligation.trigger_type:
                existing.trigger_type = obligation.trigger_type
                is_updated = True
            if existing.trigger_offset_value != obligation.trigger_offset_value:
                existing.trigger_offset_value = obligation.trigger_offset_value
                is_updated = True
            if existing.trigger_offset_unit != obligation.trigger_offset_unit:
                existing.trigger_offset_unit = obligation.trigger_offset_unit
                is_updated = True
            if existing.responsible_function != obligation.responsible_function:
                existing.responsible_function = obligation.responsible_function
                is_updated = True
            if existing.source_citation != obligation.source_citation:
                existing.source_citation = obligation.source_citation
                is_updated = True
            if existing.authoritative_source_url != obligation.authoritative_source_url:
                existing.authoritative_source_url = obligation.authoritative_source_url
                is_updated = True
            if existing.regulatory_evidence_refs != obligation.regulatory_evidence_refs:
                existing.regulatory_evidence_refs = obligation.regulatory_evidence_refs
                is_updated = True
            if existing.organization_evidence_refs != obligation.organization_evidence_refs:
                existing.organization_evidence_refs = obligation.organization_evidence_refs
                is_updated = True
            if (obligation.priority and existing.priority != obligation.priority):
                existing.priority = obligation.priority
                is_updated = True
            
            if is_updated:
                existing.engine_version = ENGINE_VERSION
                existing.updated_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(existing)
        return existing, is_new, is_updated
