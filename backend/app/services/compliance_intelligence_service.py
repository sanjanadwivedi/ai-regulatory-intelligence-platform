"""
compliance_intelligence_service.py

Compliance Intelligence Engine — Phase 2
=========================================
READ-ONLY aggregation layer. Consumes authoritative upstream records without
mutating any of: EnterpriseProfile, DiscoveredFact, Regulation,
RegulatoryApplicabilityAssessment, RegulatoryObligation, ComplianceTask.

Snapshot immutability guarantee
--------------------------------
Each call to generate_snapshot() creates a NEW record. Existing snapshots
are never updated; their JSON fields remain frozen at the time of generation.

Evidence segregation (three non-overlapping layers)
-----------------------------------------------------
  REGULATORY   — statutory citations, source URLs, effective dates
  ORGANIZATION — confirmed org facts, jurisdiction, business activities
  OPERATIONAL  — uploaded logs, audit reports, task completion records

Compliance disclaimer
----------------------
A completed task or uploaded evidence DOES NOT mean the organisation is
legally compliant. This service always surfaces that distinction.
"""

import datetime
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    DiscoveredFact,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTriggerEvent,
    ComplianceAlert,
    AuditLog,
    ComplianceIntelligenceSnapshot,
)
from app.models.domain import generate_uuid

logger = logging.getLogger(__name__)

ENGINE_VERSION = "v1.0.0-deterministic"
COMPLIANCE_DISCLAIMER = (
    "Operational evidence demonstrates execution activity; it does not "
    "independently establish legal compliance."
)
APPLICABILITY_DISCLAIMER = (
    "Regulatory applicability determinations are based on the recorded "
    "assessment and authoritative regulatory evidence available at the "
    "time of evaluation."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_status_effective(task: ComplianceTask) -> str:
    """Return effective task status, promoting OPEN tasks with past due_date to OVERDUE."""
    if task.due_date and task.status in ("OPEN", "IN_PROGRESS"):
        today = datetime.datetime.utcnow().date()
        due = task.due_date if isinstance(task.due_date, datetime.date) else getattr(task.due_date, 'date', lambda: task.due_date)()
        if due < today:
            return "OVERDUE"
    return task.status


def _has_operational_evidence(task_id: str, db: Session) -> bool:
    return db.query(ComplianceTaskEvidence).filter(
        ComplianceTaskEvidence.task_id == task_id
    ).count() > 0


def _get_operational_evidence(task_id: str, db: Session) -> List[ComplianceTaskEvidence]:
    return db.query(ComplianceTaskEvidence).filter(
        ComplianceTaskEvidence.task_id == task_id
    ).all()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ComplianceIntelligenceService:

    # ------------------------------------------------------------------
    # generate_snapshot
    # ------------------------------------------------------------------

    @staticmethod
    def generate_snapshot(
        organization_id: str,
        db: Session,
        generated_by: Optional[str] = None,
    ) -> ComplianceIntelligenceSnapshot:
        """Create a new immutable point-in-time compliance intelligence snapshot.

        This method NEVER modifies an existing snapshot. Each invocation
        produces a new database record with a new UUID.
        """
        # Verify org exists
        org = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not org:
            raise ValueError(f"Organisation {organization_id} not found")

        # ---- Legal landscape ----------------------------------------
        assessments = (
            db.query(RegulatoryApplicabilityAssessment)
            .filter(RegulatoryApplicabilityAssessment.organization_id == organization_id)
            .all()
        )
        legal_summary = ComplianceIntelligenceService._build_legal_summary(assessments)

        # ---- Obligations --------------------------------------------
        obligations = (
            db.query(RegulatoryObligation)
            .filter(RegulatoryObligation.organization_id == organization_id)
            .all()
        )
        obligation_summary = ComplianceIntelligenceService._build_obligation_summary(obligations, db)

        # ---- Operational tasks --------------------------------------
        tasks = (
            db.query(ComplianceTask)
            .filter(ComplianceTask.organization_id == organization_id)
            .all()
        )
        operational_summary = ComplianceIntelligenceService._build_operational_summary(tasks, db)

        # ---- Evidence coverage --------------------------------------
        evidence_summary = ComplianceIntelligenceService._build_evidence_summary(obligations, tasks, db)

        # ---- Alerts -------------------------------------------------
        alerts = (
            db.query(ComplianceAlert)
            .filter(ComplianceAlert.organization_id == organization_id)
            .all()
        )
        alert_summary = ComplianceIntelligenceService._build_alert_summary(alerts)

        # ---- Deadlines ----------------------------------------------
        deadline_summary = ComplianceIntelligenceService._build_deadline_summary(obligations, tasks, db)

        # ---- Unresolved & review items ------------------------------
        unresolved_items = ComplianceIntelligenceService._build_unresolved_items(
            assessments, obligations, tasks, alerts, db
        )
        review_items = [i for i in unresolved_items if i.get("severity") in ("REVIEW", "REQUIRES_REVIEW")]

        # ---- Provenance graph ---------------------------------------
        provenance_summary = ComplianceIntelligenceService._build_provenance_graph(
            organization_id, assessments, obligations, tasks, db
        )

        # ---- Persist snapshot (NEW record, never update old) --------
        snapshot = ComplianceIntelligenceSnapshot(
            id=generate_uuid(),
            organization_id=organization_id,
            snapshot_type="POINT_IN_TIME",
            generated_by=generated_by,
            generated_at=datetime.datetime.utcnow(),
            engine_version=ENGINE_VERSION,
            legal_summary=legal_summary,
            obligation_summary=obligation_summary,
            operational_summary=operational_summary,
            evidence_summary=evidence_summary,
            alert_summary=alert_summary,
            deadline_summary=deadline_summary,
            unresolved_items=unresolved_items,
            review_items=review_items,
            provenance_summary=provenance_summary,
        )
        db.add(snapshot)

        # ---- Immutable audit log ------------------------------------
        audit = AuditLog(
            id=generate_uuid(),
            user_name=generated_by or "system",
            user_role="system",
            action="COMPLIANCE_INTELLIGENCE_SNAPSHOT_GENERATED",
            target_type="ComplianceIntelligenceSnapshot",
            target_id=snapshot.id,
            details={
                "organization_id": organization_id,
                "snapshot_id": snapshot.id,
                "engine_version": ENGINE_VERSION,
                "applicable_count": legal_summary.get("applicable", 0),
                "active_obligations": obligation_summary.get("active", 0),
                "unresolved_count": len(unresolved_items),
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(snapshot)
        logger.info("Snapshot generated: %s for org %s", snapshot.id, organization_id)
        return snapshot

    # ------------------------------------------------------------------
    # get_current_snapshot / get_snapshot_by_id
    # ------------------------------------------------------------------

    @staticmethod
    def get_current_snapshot(
        organization_id: str,
        db: Session,
    ) -> Optional[ComplianceIntelligenceSnapshot]:
        return (
            db.query(ComplianceIntelligenceSnapshot)
            .filter(ComplianceIntelligenceSnapshot.organization_id == organization_id)
            .order_by(ComplianceIntelligenceSnapshot.generated_at.desc())
            .first()
        )

    @staticmethod
    def get_snapshot_by_id(
        snapshot_id: str,
        organization_id: str,
        db: Session,
    ) -> Optional[ComplianceIntelligenceSnapshot]:
        """Retrieve snapshot enforcing strict tenant isolation."""
        return (
            db.query(ComplianceIntelligenceSnapshot)
            .filter(
                ComplianceIntelligenceSnapshot.id == snapshot_id,
                ComplianceIntelligenceSnapshot.organization_id == organization_id,
            )
            .first()
        )

    # ------------------------------------------------------------------
    # Internal aggregation builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_legal_summary(assessments: list) -> Dict[str, Any]:
        counts: Dict[str, int] = {"APPLICABLE": 0, "NOT_APPLICABLE": 0, "REQUIRES_REVIEW": 0}
        breakdown = []
        for a in assessments:
            s = a.status if a.status in counts else "REQUIRES_REVIEW"
            counts[s] += 1
            breakdown.append({
                "assessment_id": a.id,
                "regulation_id": a.regulation_id,
                "status": a.status,
                "score": a.applicability_score,
                "engine_version": a.engine_version,
            })
        return {
            "applicable": counts["APPLICABLE"],
            "not_applicable": counts["NOT_APPLICABLE"],
            "requires_review": counts["REQUIRES_REVIEW"],
            "total": len(assessments),
            "breakdown": breakdown,
        }

    @staticmethod
    def _build_obligation_summary(obligations: list, db: Session) -> Dict[str, Any]:
        counts: Dict[str, int] = {"ACTIVE": 0, "SUPERSEDED": 0, "REQUIRES_REVIEW": 0}
        by_type: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        breakdown = []
        for o in obligations:
            s = o.status if o.status in counts else "REQUIRES_REVIEW"
            counts[s] += 1
            by_type[o.obligation_type] = by_type.get(o.obligation_type, 0) + 1
            p = o.priority or "HIGH"
            by_priority[p] = by_priority.get(p, 0) + 1
            breakdown.append({
                "obligation_id": o.id,
                "obligation_code": o.obligation_code,
                "regulation_id": o.regulation_id,
                "status": o.status,
                "obligation_type": o.obligation_type,
                "priority": o.priority,
            })
        return {
            "active": counts["ACTIVE"],
            "superseded": counts["SUPERSEDED"],
            "requires_review": counts["REQUIRES_REVIEW"],
            "total": len(obligations),
            "by_type": by_type,
            "by_priority": by_priority,
            "breakdown": breakdown,
        }

    @staticmethod
    def _build_operational_summary(tasks: list, db: Session) -> Dict[str, Any]:
        counts: Dict[str, int] = {
            "OPEN": 0, "IN_PROGRESS": 0, "BLOCKED": 0,
            "COMPLETED": 0, "REOPENED": 0, "OVERDUE": 0,
        }
        breakdown = []
        for t in tasks:
            eff = _task_status_effective(t)
            counts[eff] = counts.get(eff, 0) + 1
            breakdown.append({
                "task_id": t.id,
                "control_code": t.control_code,
                "title": t.title,
                "effective_status": eff,
                "regulatory_obligation_id": t.regulatory_obligation_id,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            })
        return {**counts, "total": len(tasks), "breakdown": breakdown}

    @staticmethod
    def _build_evidence_summary(obligations: list, tasks: list, db: Session) -> Dict[str, Any]:
        task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}
        present = 0
        gap = 0
        completed_without_evidence = 0
        items = []

        for o in obligations:
            if o.status == "SUPERSEDED":
                continue

            task = task_map.get(o.id)
            if task is None:
                # No task linked to this obligation
                if o.status == "ACTIVE":
                    gap += 1
                    items.append({
                        "obligation_id": o.id,
                        "obligation_code": o.obligation_code,
                        "task_id": None,
                        "evidence_status": "EVIDENCE_GAP",
                        "reason": "No compliance task linked to active obligation",
                    })
                continue

            eff_status = _task_status_effective(task)
            has_evidence = _has_operational_evidence(task.id, db)

            if o.status == "REQUIRES_REVIEW":
                items.append({
                    "obligation_id": o.id,
                    "obligation_code": o.obligation_code,
                    "task_id": task.id,
                    "evidence_status": "REQUIRES_REVIEW",
                    "reason": "Obligation requires review; evidence status indeterminate",
                })
            elif eff_status == "COMPLETED" and not has_evidence:
                completed_without_evidence += 1
                items.append({
                    "obligation_id": o.id,
                    "obligation_code": o.obligation_code,
                    "task_id": task.id,
                    "evidence_status": "COMPLETED_WITHOUT_EVIDENCE",
                    "reason": "Task marked COMPLETED but no operational evidence was attached. "
                              + COMPLIANCE_DISCLAIMER,
                })
            elif o.status == "ACTIVE" and not has_evidence:
                gap += 1
                items.append({
                    "obligation_id": o.id,
                    "obligation_code": o.obligation_code,
                    "task_id": task.id,
                    "evidence_status": "EVIDENCE_GAP",
                    "reason": "Active task has no operational evidence attached",
                })
            elif has_evidence:
                present += 1
                items.append({
                    "obligation_id": o.id,
                    "obligation_code": o.obligation_code,
                    "task_id": task.id,
                    "evidence_status": "EVIDENCE_PRESENT",
                    "reason": None,
                })

        return {
            "evidence_present": present,
            "evidence_gap": gap,
            "completed_without_evidence": completed_without_evidence,
            "items": items,
            "disclaimer": COMPLIANCE_DISCLAIMER,
        }

    @staticmethod
    def _build_alert_summary(alerts: list) -> Dict[str, Any]:
        active = [a for a in alerts if a.status == "ACTIVE"]
        resolved = [a for a in alerts if a.status == "RESOLVED"]
        critical = [a for a in active if a.severity == "CRITICAL"]
        high = [a for a in active if a.severity == "HIGH"]
        type_counts: Dict[str, int] = {}
        for a in active:
            type_counts[a.alert_type] = type_counts.get(a.alert_type, 0) + 1
        return {
            "active_count": len(active),
            "resolved_count": len(resolved),
            "critical_count": len(critical),
            "high_count": len(high),
            "by_type": type_counts,
        }

    @staticmethod
    def _build_deadline_summary(obligations: list, tasks: list, db: Session) -> Dict[str, Any]:
        """Build deadline summary using ONLY structured trigger metadata.
        Never parses due_rule text. Never invents deadlines.
        """
        triggered = []
        awaiting = []
        continuous = []
        missing_metadata = []
        overdue = []

        task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}

        for o in obligations:
            if o.status != "ACTIVE":
                continue
            task = task_map.get(o.id)

            entry = {
                "obligation_id": o.id,
                "obligation_code": o.obligation_code,
                "due_rule": o.due_rule,
                "trigger_type": o.trigger_type,
                "trigger_offset_value": o.trigger_offset_value,
                "trigger_offset_unit": o.trigger_offset_unit,
                "task_id": task.id if task else None,
                "due_date": task.due_date.isoformat() if task and task.due_date else None,
            }

            if not o.trigger_type and not (task and task.due_date):
                # No structured trigger — continuous or unscheduled obligation
                if o.frequency:
                    continuous.append({**entry, "frequency": o.frequency})
                else:
                    missing_metadata.append(entry)
            elif o.trigger_type and o.trigger_offset_value and o.trigger_offset_unit:
                # Structured trigger exists; check if it has been fired
                if task and task.due_date:
                    eff = _task_status_effective(task)
                    if eff == "OVERDUE":
                        overdue.append(entry)
                    else:
                        triggered.append(entry)
                else:
                    awaiting.append(entry)
            else:
                missing_metadata.append(entry)

        return {
            "triggered": triggered,
            "awaiting_trigger": awaiting,
            "continuous": continuous,
            "missing_trigger_metadata": missing_metadata,
            "overdue": overdue,
        }

    @staticmethod
    def _build_unresolved_items(
        assessments: list,
        obligations: list,
        tasks: list,
        alerts: list,
        db: Session,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}

        # REQUIRES_REVIEW applicability
        for a in assessments:
            if a.status == "REQUIRES_REVIEW":
                items.append({
                    "category": "REQUIRES_REVIEW_APPLICABILITY",
                    "severity": "REQUIRES_REVIEW",
                    "entity_type": "RegulatoryApplicabilityAssessment",
                    "entity_id": a.id,
                    "title": f"Applicability REQUIRES_REVIEW — regulation {a.regulation_id}",
                    "reason": "Regulatory applicability could not be deterministically established",
                    "provenance_refs": {"regulation_id": a.regulation_id},
                })

        # REQUIRES_REVIEW obligations
        for o in obligations:
            if o.status == "REQUIRES_REVIEW":
                items.append({
                    "category": "REQUIRES_REVIEW_OBLIGATION",
                    "severity": "REQUIRES_REVIEW",
                    "entity_type": "RegulatoryObligation",
                    "entity_id": o.id,
                    "title": f"Obligation REQUIRES_REVIEW — {o.obligation_code}",
                    "reason": "Obligation requires human review before active compliance tasks can be generated",
                    "provenance_refs": {"obligation_code": o.obligation_code, "regulation_id": o.regulation_id},
                })

        # Overdue tasks
        for t in tasks:
            if _task_status_effective(t) == "OVERDUE":
                items.append({
                    "category": "OVERDUE_TASK",
                    "severity": "CRITICAL",
                    "entity_type": "ComplianceTask",
                    "entity_id": t.id,
                    "title": f"Overdue — {t.title}",
                    "reason": f"Statutory deadline {t.due_date.isoformat() if t.due_date else 'N/A'} passed without completion",
                    "provenance_refs": {"regulatory_obligation_id": t.regulatory_obligation_id},
                })

        # Blocked tasks
        for t in tasks:
            if t.status == "BLOCKED":
                items.append({
                    "category": "BLOCKED_TASK",
                    "severity": "HIGH" if (t.priority in ("CRITICAL", "HIGH")) else "MEDIUM",
                    "entity_type": "ComplianceTask",
                    "entity_id": t.id,
                    "title": f"Blocked — {t.title}",
                    "reason": "Task is blocked and cannot progress",
                    "provenance_refs": {"regulatory_obligation_id": t.regulatory_obligation_id},
                })

        # Orphaned active obligations (ACTIVE with no task)
        for o in obligations:
            if o.status == "ACTIVE" and o.id not in task_map:
                items.append({
                    "category": "ORPHANED_ACTIVE_OBLIGATION",
                    "severity": "HIGH",
                    "entity_type": "RegulatoryObligation",
                    "entity_id": o.id,
                    "title": f"Orphaned obligation — {o.obligation_code}",
                    "reason": "Active obligation has no operational compliance task",
                    "provenance_refs": {"regulation_id": o.regulation_id},
                })

        # Evidence gaps
        for o in obligations:
            if o.status != "ACTIVE":
                continue
            task = task_map.get(o.id)
            if task and not _has_operational_evidence(task.id, db):
                if _task_status_effective(task) == "COMPLETED":
                    items.append({
                        "category": "COMPLETED_WITHOUT_EVIDENCE",
                        "severity": "HIGH",
                        "entity_type": "ComplianceTask",
                        "entity_id": task.id,
                        "title": f"Completed without evidence — {task.title}",
                        "reason": COMPLIANCE_DISCLAIMER,
                        "provenance_refs": {"obligation_id": o.id},
                    })
                else:
                    items.append({
                        "category": "EVIDENCE_GAP",
                        "severity": "MEDIUM",
                        "entity_type": "ComplianceTask",
                        "entity_id": task.id,
                        "title": f"Evidence gap — {task.title}",
                        "reason": "No operational evidence attached to active task",
                        "provenance_refs": {"obligation_id": o.id},
                    })

        # Missing trigger metadata on active obligations
        for o in obligations:
            if o.status == "ACTIVE" and o.due_rule and not (o.trigger_type and o.trigger_offset_value and o.trigger_offset_unit):
                items.append({
                    "category": "MISSING_TRIGGER_METADATA",
                    "severity": "REQUIRES_REVIEW",
                    "entity_type": "RegulatoryObligation",
                    "entity_id": o.id,
                    "title": f"Missing structured trigger — {o.obligation_code}",
                    "reason": "due_rule text exists but trigger_type/offset metadata is incomplete; no deadline can be calculated",
                    "provenance_refs": {"due_rule": o.due_rule},
                })

        # Active alerts
        for a in alerts:
            if a.status == "ACTIVE":
                items.append({
                    "category": "ACTIVE_ALERT",
                    "severity": a.severity or "MEDIUM",
                    "entity_type": "ComplianceAlert",
                    "entity_id": a.id,
                    "title": f"Active alert — {a.alert_type}",
                    "reason": a.description or a.alert_type,
                    "provenance_refs": {
                        "alert_type": a.alert_type,
                        "source_entity_type": a.source_entity_type,
                        "source_entity_id": a.source_entity_id,
                    },
                })

        return items

    @staticmethod
    def _build_provenance_graph(
        organization_id: str,
        assessments: list,
        obligations: list,
        tasks: list,
        db: Session,
    ) -> Dict[str, Any]:
        """Build full 5-tier provenance graph.
        Regulation → Assessment → Obligation → Task → Evidence
        Each node retains entity type, ID, title, status, and timestamps.
        """
        assessment_map: Dict[str, RegulatoryApplicabilityAssessment] = {a.regulation_id: a for a in assessments}
        obligation_map: Dict[str, List[RegulatoryObligation]] = {}
        for o in obligations:
            obligation_map.setdefault(o.regulation_id, []).append(o)

        task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}

        chains = []
        for a in assessments:
            reg_node = {
                "entity_type": "Regulation",
                "entity_id": a.regulation_id,
                "title": f"Regulation {a.regulation_id}",
                "status": None,
            }
            assess_node = {
                "entity_type": "RegulatoryApplicabilityAssessment",
                "entity_id": a.id,
                "title": f"Applicability Assessment — {a.status}",
                "status": a.status,
                "score": a.applicability_score,
                "timestamp": a.evaluated_at.isoformat() if getattr(a, "evaluated_at", None) else None,
            }

            obl_chains = []
            for o in obligation_map.get(a.regulation_id, []):
                obl_node = {
                    "entity_type": "RegulatoryObligation",
                    "entity_id": o.id,
                    "title": o.title,
                    "status": o.status,
                    "obligation_code": o.obligation_code,
                    "priority": o.priority,
                    "source_citation": o.source_citation,
                }
                task = task_map.get(o.id)
                if task:
                    evs = _get_operational_evidence(task.id, db)
                    evidence_nodes = [
                        {"entity_type": "ComplianceTaskEvidence",
                        "entity_id": ev.id,
                        "title": ev.file_name,
                        "status": "PRESENT",
                        "evidence_type": ev.evidence_type,
                        "timestamp": ev.evidence_date.isoformat() if ev.evidence_date else None,
                    }
                        for ev in evs
                    ]
                    task_node = {
                        "entity_type": "ComplianceTask",
                        "entity_id": task.id,
                        "title": task.title,
                        "status": _task_status_effective(task),
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "evidence": evidence_nodes,
                        "evidence_count": len(evidence_nodes),
                    }
                    obl_chains.append({"obligation": obl_node, "task": task_node})
                else:
                    obl_chains.append({"obligation": obl_node, "task": None})

            chains.append({
                "regulation": reg_node,
                "assessment": assess_node,
                "obligations": obl_chains,
            })

        return {
            "organization_id": organization_id,
            "chains": chains,
            "total_chains": len(chains),
        }
