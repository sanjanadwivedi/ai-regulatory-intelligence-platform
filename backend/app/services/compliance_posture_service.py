import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTriggerEvent
)

class CompliancePostureService:
    """
    Deterministic Compliance Posture Engine.
    Aggregates authoritative legal determinations, statutory obligations, operational tasks,
    and operational evidence into an explainable, multi-dimensional compliance posture.
    
    NON-NEGOTIABLE RULES:
    - READ/AGGREGATE ONLY. Never mutates legal records or task states.
    - Never equates operational completion with legal compliance.
    - Never calls due_date = NULL tasks overdue.
    - Explains every posture determination with deterministic reasons.
    """

    @classmethod
    def calculate_posture(cls, organization_id: str, db: Session) -> Dict[str, Any]:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Enterprise profile with ID '{organization_id}' not found."
            )

        today = datetime.date.today()

        # 1. LEGAL / REGULATORY LANDSCAPE
        assessments = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.organization_id == organization_id
        ).all()

        applicable_assessments = [a for a in assessments if a.status == "APPLICABLE"]
        not_applicable_assessments = [a for a in assessments if a.status == "NOT_APPLICABLE"]
        review_assessments = [a for a in assessments if a.status == "REQUIRES_REVIEW"]

        legal_summary = {
            "total_regulations_evaluated": len(assessments),
            "applicable_count": len(applicable_assessments),
            "not_applicable_count": len(not_applicable_assessments),
            "requires_review_count": len(review_assessments),
            "applicable_regulation_ids": [a.regulation_id for a in applicable_assessments if a.regulation_id]
        }

        # 2. STATUTORY OBLIGATION STATE
        obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id
        ).all()

        active_obligations = [o for o in obligations if o.status == "ACTIVE"]
        review_obligations = [o for o in obligations if o.status == "REQUIRES_REVIEW"]
        superseded_obligations = [o for o in obligations if o.status == "SUPERSEDED"]

        priorities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for o in active_obligations:
            p = (o.priority or "MEDIUM").upper()
            priorities[p] = priorities.get(p, 0) + 1

        regulations_represented = len({o.regulation_id for o in active_obligations if o.regulation_id})

        obligation_summary = {
            "total_obligations": len(obligations),
            "active_obligations_count": len(active_obligations),
            "requires_review_count": len(review_obligations),
            "superseded_count": len(superseded_obligations),
            "by_priority": priorities,
            "regulations_represented": regulations_represented
        }

        # 3. OPERATIONAL TASK EXECUTION STATE
        tasks = db.query(ComplianceTask).filter(
            ComplianceTask.organization_id == organization_id
        ).all()

        open_tasks = [t for t in tasks if t.status == "OPEN"]
        in_progress_tasks = [t for t in tasks if t.status == "IN_PROGRESS"]
        blocked_tasks = [t for t in tasks if t.status == "BLOCKED"]
        completed_tasks = [t for t in tasks if t.status == "COMPLETED"]
        reopened_tasks = [t for t in tasks if t.status == "REOPENED"]
        superseded_tasks = [t for t in tasks if t.status == "SUPERSEDED"]

        # Calculate overdue tasks: ONLY incomplete tasks with structured due_date < today
        overdue_tasks = [
            t for t in tasks
            if t.status not in {"COMPLETED", "SUPERSEDED", "CANCELLED"}
            and t.due_date is not None
            and t.due_date < today
        ]

        # Continuous tasks
        continuous_tasks = [
            t for t in tasks
            if t.frequency == "CONTINUOUS" or (t.trigger_type is None and t.due_date is None)
        ]

        # Awaiting trigger tasks
        awaiting_trigger_tasks = [
            t for t in tasks
            if t.trigger_type is not None
            and t.trigger_timestamp is None
            and t.due_date is None
            and t.status not in {"COMPLETED", "SUPERSEDED", "CANCELLED"}
        ]

        # Incomplete trigger tasks with missing machine offset
        missing_trigger_offset_tasks = [
            t for t in tasks
            if t.trigger_type is not None
            and (t.trigger_offset_value is None or not t.trigger_offset_unit)
        ]

        operational_summary = {
            "total_tasks": len(tasks),
            "open_count": len(open_tasks),
            "in_progress_count": len(in_progress_tasks),
            "blocked_count": len(blocked_tasks),
            "completed_count": len(completed_tasks),
            "reopened_count": len(reopened_tasks),
            "superseded_count": len(superseded_tasks),
            "overdue_count": len(overdue_tasks),
            "continuous_count": len(continuous_tasks),
            "awaiting_trigger_count": len(awaiting_trigger_tasks)
        }

        # 4. OPERATIONAL EVIDENCE COVERAGE
        # Fetch all operational evidence for this org
        evidence_records = db.query(ComplianceTaskEvidence).filter(
            ComplianceTaskEvidence.organization_id == organization_id
        ).all()
        evidence_by_task_id: Dict[str, List[ComplianceTaskEvidence]] = {}
        for ev in evidence_records:
            evidence_by_task_id.setdefault(ev.task_id, []).append(ev)

        # Check evidence coverage for active obligations
        obligations_with_evidence = 0
        obligations_without_evidence = 0
        orphaned_active_obligations: List[RegulatoryObligation] = []

        for obl in active_obligations:
            related_tasks = [t for t in tasks if t.regulatory_obligation_id == obl.id and t.status != "SUPERSEDED"]
            if not related_tasks:
                orphaned_active_obligations.append(obl)
                obligations_without_evidence += 1
                continue

            obl_ev_count = sum(len(evidence_by_task_id.get(t.id, [])) for t in related_tasks)
            if obl_ev_count > 0:
                obligations_with_evidence += 1
            else:
                obligations_without_evidence += 1

        # Completed tasks without evidence
        completed_without_evidence = [
            t for t in completed_tasks
            if len(evidence_by_task_id.get(t.id, [])) == 0
        ]

        evidence_summary = {
            "total_evidence_records": len(evidence_records),
            "obligations_with_evidence": obligations_with_evidence,
            "obligations_without_evidence": obligations_without_evidence,
            "completed_without_evidence_count": len(completed_without_evidence)
        }

        # 5. DETERMINISTIC POSTURE EVALUATION & EXPLANATION
        posture_reasons: List[str] = []
        is_critical = False
        is_attention = False
        is_review = False

        # CRITICAL conditions
        if overdue_tasks:
            is_critical = True
            posture_reasons.append(f"{len(overdue_tasks)} triggered compliance task(s) are OVERDUE statutory deadlines.")

        critical_blocked = [t for t in blocked_tasks if t.priority == "CRITICAL"]
        if critical_blocked:
            is_critical = True
            posture_reasons.append(f"{len(critical_blocked)} CRITICAL priority task(s) are BLOCKED.")

        # ATTENTION_REQUIRED conditions
        high_blocked = [t for t in blocked_tasks if t.priority == "HIGH"]
        if high_blocked:
            is_attention = True
            posture_reasons.append(f"{len(high_blocked)} HIGH priority task(s) are BLOCKED.")

        if orphaned_active_obligations:
            is_attention = True
            posture_reasons.append(f"{len(orphaned_active_obligations)} ACTIVE statutory obligation(s) have no operational task instantiated.")

        if obligations_without_evidence > 0 and len(active_obligations) > 0:
            is_attention = True
            posture_reasons.append(f"{obligations_without_evidence} of {len(active_obligations)} active statutory obligation(s) lack operational evidence.")

        if completed_without_evidence:
            is_attention = True
            posture_reasons.append(f"{len(completed_without_evidence)} task(s) marked COMPLETED without attached operational verification evidence.")

        # REQUIRES_REVIEW conditions
        if review_assessments:
            is_review = True
            posture_reasons.append(f"{len(review_assessments)} regulatory applicability assessment(s) require legal review.")

        if review_obligations:
            is_review = True
            posture_reasons.append(f"{len(review_obligations)} regulatory obligation(s) require review or clarification.")

        if missing_trigger_offset_tasks:
            is_review = True
            posture_reasons.append(f"{len(missing_trigger_offset_tasks)} event-driven task(s) have incomplete statutory offset metadata.")

        # Posture Status Priority Resolution:
        # CRITICAL > ATTENTION_REQUIRED > REQUIRES_REVIEW > HEALTHY
        if is_critical:
            posture_status = "CRITICAL"
        elif is_attention:
            posture_status = "ATTENTION_REQUIRED"
        elif is_review:
            posture_status = "REQUIRES_REVIEW"
        else:
            posture_status = "HEALTHY"
            posture_reasons.append("All applicable regulations evaluated; active obligations covered by operational tasks with zero overdue deadlines.")

        return {
            "organization": {
                "id": profile.id,
                "organization_name": profile.organization_name,
                "country": profile.country,
                "industry_sector": profile.industry_sector,
                "discovery_status": profile.discovery_status
            },
            "legal_summary": legal_summary,
            "obligation_summary": obligation_summary,
            "operational_summary": operational_summary,
            "evidence_summary": evidence_summary,
            "posture_status": posture_status,
            "posture_reasons": posture_reasons,
            "generated_at": datetime.datetime.utcnow().isoformat()
        }
