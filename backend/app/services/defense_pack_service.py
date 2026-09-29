"""

defense_pack_service.py



Compliance Defense Pack Engine — Phase 3

==========================================

Builds versioned, immutable, auditable Compliance Defense Packs from

an existing ComplianceIntelligenceSnapshot.



SHA-256 hash determinism

------------------------

The canonical hash is computed over STABLE content only.

Excluded from hash input (volatile fields):

  - generated_at / created_at timestamps

  - database-generated UUIDs (pack id, manifest item ids)

  - pack_version string (since the same logical content at v2 must equal v1's hash)



Included in hash input (stable logical content):

  - organization_id

  - snapshot_id

  - engine_version

  - all summary JSON blobs from the snapshot

  - all manifest item content (title, status, provenance, etc.)



Versioning

-----------

Previous packs are marked SUPERSEDED when a newer pack is generated.

Historical packs are NEVER overwritten or deleted.



Evidence Manifest Completeness

-------------------------------

Manifest includes BOTH:

  PRESENT  — evidence that actually exists in the database

  MISSING  — expected evidence slots that have no uploaded file (evidence gaps)

  REQUIRES_REVIEW — evidence slots where status is indeterminate



This ensures an auditor sees the full picture.

"""



import datetime

import hashlib

import json

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

    ComplianceDefensePack,

    ComplianceEvidenceManifest,

)

from app.models.domain import generate_uuid

from app.services.compliance_intelligence_service import (

    ComplianceIntelligenceService,

    ENGINE_VERSION,

    COMPLIANCE_DISCLAIMER,

    APPLICABILITY_DISCLAIMER,

    _task_status_effective,

    _has_operational_evidence,

    _get_operational_evidence,

)



logger = logging.getLogger(__name__)





# ---------------------------------------------------------------------------

# Canonical hash helpers

# ---------------------------------------------------------------------------



def _stable_canonical(obj: Any) -> Any:

    """Recursively ensure all dict keys are sorted for canonical serialisation."""

    if isinstance(obj, dict):

        return {k: _stable_canonical(v) for k, v in sorted(obj.items())}

    if isinstance(obj, list):

        return [_stable_canonical(i) for i in obj]

    return obj





def _compute_content_hash(canonical_payload: Dict[str, Any]) -> str:

    """Compute deterministic SHA-256 over stable canonical content.



    Volatile fields (generated_at, pack_version, UUIDs) are intentionally

    excluded so that the same logical snapshot produces the same hash across

    multiple pack generations.

    """

    stable = _stable_canonical(canonical_payload)

    serialised = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str)

    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()





# ---------------------------------------------------------------------------

# Evidence manifest builders (3 non-overlapping layers)

# ---------------------------------------------------------------------------



def _build_regulatory_evidence(

    org_id: str,

    pack_id: str,

    obligations: List[RegulatoryObligation],

    db: Session,

) -> List[Dict[str, Any]]:

    """Layer 1 — Regulatory Evidence: statutory citations, source URLs, effective dates."""

    items = []

    seen_regs = set()

    for o in obligations:

        if o.regulation_id in seen_regs:

            continue

        seen_regs.add(o.regulation_id)

        reg = db.query(Regulation).filter(Regulation.id == o.regulation_id).first()

        if reg:

            items.append({

                "evidence_layer": "REGULATORY",

                "evidence_type": "STATUTORY_CITATION",

                "source_entity_type": "Regulation",

                "source_entity_id": reg.id,

                "title": reg.title,

                "description": f"Authoritative regulation: {reg.authority}",

                "source_url": reg.source_url,

                "source_citation": f"{reg.authority} — {reg.doc_number or ''}",

                "captured_at": reg.effective_date.isoformat() if reg.effective_date else None,

                "evidence_status": "PRESENT",

                "provenance_refs": {

                    "organization_id": org_id,

                    "regulation_id": reg.id,

                },

            })

    return items





def _build_organization_evidence(

    org_id: str,

    pack_id: str,

    org: EnterpriseProfile,

    assessments: List[RegulatoryApplicabilityAssessment],

    db: Session,

) -> List[Dict[str, Any]]:

    """Layer 2 — Organization Evidence: confirmed org facts, jurisdiction, business activities."""

    items = []



    # Confirmed org profile

    items.append({

        "evidence_layer": "ORGANIZATION",

        "evidence_type": "CONFIRMED_PROFILE",

        "source_entity_type": "EnterpriseProfile",

        "source_entity_id": org.id,

        "title": f"Confirmed Organisation Profile — {org.organization_name}",

        "description": (

            f"Country: {org.country}. "

            f"Discovery status: {org.discovery_status}. "

            f"Business activities: {', '.join(org.business_activities or [])}."

        ),

        "source_url": None,

        "source_citation": None,

        "captured_at": org.created_at.isoformat() if hasattr(org, "created_at") and org.created_at else None,

        "evidence_status": "PRESENT",

        "provenance_refs": {"organization_id": org_id},

    })



    # Discovered facts

    facts = db.query(DiscoveredFact).filter(DiscoveredFact.organization_id == org_id).all()

    for f in facts:

        items.append({

            "evidence_layer": "ORGANIZATION",

            "evidence_type": "REGULATORY_SIGNAL",

            "source_entity_type": "DiscoveredFact",

            "source_entity_id": f.id,

            "title": f"[Signal] {f.fact_value}",

            "description": f"Source: {f.source_url or 'N/A'}. Confidence: {f.confidence}",

            "source_url": f.source_url,

            "source_citation": None,

            "captured_at": f.created_at.isoformat() if f.created_at else None,

            "evidence_status": "PRESENT",

            "provenance_refs": {"organization_id": org_id, "fact_id": f.id},

        })



    # Applicability assessments

    for a in assessments:

        items.append({

            "evidence_layer": "ORGANIZATION",

            "evidence_type": "APPLICABILITY_ASSESSMENT",

            "source_entity_type": "RegulatoryApplicabilityAssessment",

            "source_entity_id": a.id,

            "title": f"Applicability Assessment — {a.status} — {a.regulation_id}",

            "description": a.rationale or "",

            "source_url": None,

            "source_citation": None,

            "captured_at": getattr(a, "evaluated_at", getattr(a, "created_at", None)).isoformat() if getattr(a, "evaluated_at", getattr(a, "created_at", None)) else None,

            "evidence_status": "PRESENT",

            "provenance_refs": {"organization_id": org_id, "regulation_id": a.regulation_id},

        })



    return items





def _build_operational_evidence(

    org_id: str,

    pack_id: str,

    obligations: List[RegulatoryObligation],

    tasks: List[ComplianceTask],

    db: Session,

) -> List[Dict[str, Any]]:

    """Layer 3 — Operational Evidence: uploaded logs, reports, completion records.

    Also includes MISSING entries for expected evidence gaps so auditors see

    the full picture.

    """

    items = []

    task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}



    for o in obligations:

        if o.status == "SUPERSEDED":

            continue

        task = task_map.get(o.id)

        if task is None:

            if o.status == "ACTIVE":

                # Expected evidence slot — MISSING (no task at all)

                items.append({

                    "evidence_layer": "OPERATIONAL",

                    "evidence_type": "MISSING_TASK",

                    "source_entity_type": "RegulatoryObligation",

                    "source_entity_id": o.id,

                    "title": f"[MISSING] No compliance task — {o.obligation_code}",

                    "description": "Active obligation has no linked operational compliance task",

                    "source_url": None,

                    "source_citation": o.source_citation,

                    "captured_at": None,

                    "evidence_status": "MISSING",

                    "provenance_refs": {

                        "organization_id": org_id,

                        "obligation_id": o.id,

                        "obligation_code": o.obligation_code,

                    },

                })

            continue



        evidence_files = _get_operational_evidence(task.id, db)

        eff_status = _task_status_effective(task)



        if not evidence_files:

            # Expected evidence slot — MISSING

            if eff_status == "COMPLETED":

                label = "[COMPLETED WITHOUT EVIDENCE]"

                reason = COMPLIANCE_DISCLAIMER

                status = "MISSING"

            elif o.status == "REQUIRES_REVIEW":

                label = "[REQUIRES REVIEW]"

                reason = "Obligation requires review; evidence status indeterminate"

                status = "REQUIRES_REVIEW"

            else:

                label = "[MISSING]"

                reason = "No operational evidence attached to active task"

                status = "MISSING"



            items.append({

                "evidence_layer": "OPERATIONAL",

                "evidence_type": "MISSING_EVIDENCE",

                "source_entity_type": "ComplianceTask",

                "source_entity_id": task.id,

                "title": f"{label} {task.title} — {o.obligation_code}",

                "description": reason,

                "source_url": None,

                "source_citation": o.source_citation,

                "captured_at": None,

                "evidence_status": status,

                "provenance_refs": {

                    "organization_id": org_id,

                    "obligation_id": o.id,

                    "task_id": task.id,

                },

            })

        else:

            for ev in evidence_files:

                items.append({

                    "evidence_layer": "OPERATIONAL",

                    "evidence_type": ev.evidence_type or "DOCUMENT",

                    "source_entity_type": "ComplianceTask",

                    "source_entity_id": task.id,

                    "title": ev.file_name,

                    "description": f"Task: {task.title}. Obligation: {o.obligation_code}.",

                    "source_url": ev.file_url,

                    "source_citation": o.source_citation,

                    "captured_at": ev.evidence_date.isoformat() if ev.evidence_date else None,

                    "evidence_status": "PRESENT",

                    "provenance_refs": {

                        "organization_id": org_id,

                        "obligation_id": o.id,

                        "task_id": task.id,

                        "evidence_id": ev.id,

                    },

                })



    return items





# ---------------------------------------------------------------------------

# Public service

# ---------------------------------------------------------------------------



class DefensePackService:



    @staticmethod

    def generate_defense_pack(

        snapshot_id: str,

        organization_id: str,

        db: Session,

        generated_by: Optional[str] = None,

    ) -> ComplianceDefensePack:

        """Generate a versioned, immutable Compliance Defense Pack from a snapshot.



        Previous packs for the same organisation become SUPERSEDED.

        Historical packs are never overwritten or deleted.

        """

        # ---- Fetch snapshot (tenant-isolated) -----------------------

        snapshot = (

            db.query(ComplianceIntelligenceSnapshot)

            .filter(

                ComplianceIntelligenceSnapshot.id == snapshot_id,

                ComplianceIntelligenceSnapshot.organization_id == organization_id,

            )

            .first()

        )

        if not snapshot:

            raise ValueError(f"Snapshot {snapshot_id} not found for organisation {organization_id}")



        org = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()

        if not org:

            raise ValueError(f"Organisation {organization_id} not found")



        # ---- Load source records ------------------------------------

        assessments = (

            db.query(RegulatoryApplicabilityAssessment)

            .filter(RegulatoryApplicabilityAssessment.organization_id == organization_id)

            .all()

        )

        obligations = (

            db.query(RegulatoryObligation)

            .filter(RegulatoryObligation.organization_id == organization_id)

            .all()

        )

        tasks = (

            db.query(ComplianceTask)

            .filter(ComplianceTask.organization_id == organization_id)

            .all()

        )

        trigger_events = (

            db.query(ComplianceTriggerEvent)

            .filter(ComplianceTriggerEvent.organization_id == organization_id)

            .all()

        )

        alerts = (

            db.query(ComplianceAlert)

            .filter(ComplianceAlert.organization_id == organization_id)

            .all()

        )



        # ---- Determine version ---------------------------------------

        existing_packs = (

            db.query(ComplianceDefensePack)

            .filter(ComplianceDefensePack.organization_id == organization_id)

            .all()

        )

        next_version_num = len(existing_packs) + 1

        pack_version = f"v{next_version_num}"



        # ---- Build evidence manifest (3 layers, with MISSING gaps) ---

        reg_evidence = _build_regulatory_evidence(organization_id, "", obligations, db)

        org_evidence = _build_organization_evidence(organization_id, "", org, assessments, db)

        op_evidence = _build_operational_evidence(organization_id, "", obligations, tasks, db)

        all_evidence = reg_evidence + org_evidence + op_evidence



        # ---- Build canonical pack payload (13 sections) --------------

        canonical_payload = DefensePackService._build_canonical_payload(

            org=org,

            snapshot=snapshot,

            assessments=assessments,

            obligations=obligations,

            tasks=tasks,

            trigger_events=trigger_events,

            alerts=alerts,

            reg_evidence=reg_evidence,

            org_evidence=org_evidence,

            op_evidence=op_evidence,

        )



        # ---- Compute deterministic SHA-256 ---------------------------

        # Volatile fields excluded: generated_at, pack id, pack_version

        hash_payload = {

            "organization_id": organization_id,

            "snapshot_id": snapshot_id,

            "engine_version": ENGINE_VERSION,

            "legal_summary": snapshot.legal_summary,

            "obligation_summary": snapshot.obligation_summary,

            "operational_summary": snapshot.operational_summary,

            "evidence_summary": snapshot.evidence_summary,

            "alert_summary": snapshot.alert_summary,

            "deadline_summary": snapshot.deadline_summary,

            "unresolved_items": snapshot.unresolved_items,

            "review_items": snapshot.review_items,

            "provenance_summary": snapshot.provenance_summary,

            "evidence_manifest": [

                {k: v for k, v in item.items() if k not in ("id", "defense_pack_id")}

                for item in all_evidence

            ],

        }

        content_hash = _compute_content_hash(hash_payload)



        # ---- Supersede previous GENERATED packs ---------------------

        for old_pack in existing_packs:

            if old_pack.status == "GENERATED":

                old_pack.status = "SUPERSEDED"

                old_pack.updated_at = datetime.datetime.utcnow()



        # ---- Persist pack -------------------------------------------

        pack = ComplianceDefensePack(

            id=generate_uuid(),

            organization_id=organization_id,

            snapshot_id=snapshot_id,

            pack_version=pack_version,

            generated_by=generated_by,

            generated_at=datetime.datetime.utcnow(),

            status="GENERATED",

            content_hash=content_hash,

            manifest=canonical_payload,

            engine_version=ENGINE_VERSION,

        )

        db.add(pack)

        db.flush()  # obtain pack.id before creating manifests



        # ---- Persist evidence manifest rows -------------------------

        for item in all_evidence:

            manifest_row = ComplianceEvidenceManifest(

                id=generate_uuid(),

                defense_pack_id=pack.id,

                organization_id=organization_id,

                evidence_layer=item["evidence_layer"],

                evidence_type=item.get("evidence_type"),

                source_entity_type=item.get("source_entity_type"),

                source_entity_id=item.get("source_entity_id"),

                title=item["title"],

                description=item.get("description"),

                source_url=item.get("source_url"),

                source_citation=item.get("source_citation"),

                captured_at=_parse_dt(item.get("captured_at")),

                provenance_refs=item.get("provenance_refs"),

                evidence_status=item["evidence_status"],

            )

            db.add(manifest_row)



        # ---- Immutable audit log ------------------------------------

        audit = AuditLog(

            organization_id=organization_id,

            id=generate_uuid(),

            user_name=generated_by or "system",

            user_role="system",

            action="COMPLIANCE_DEFENSE_PACK_GENERATED",

            target_type="ComplianceDefensePack",

            target_id=pack.id,

            details={

                "organization_id": organization_id,

                "pack_id": pack.id,

                "pack_version": pack_version,

                "snapshot_id": snapshot_id,

                "content_hash": content_hash,

                "engine_version": ENGINE_VERSION,

                "evidence_items": len(all_evidence),

                "present_count": sum(1 for e in all_evidence if e["evidence_status"] == "PRESENT"),

                "missing_count": sum(1 for e in all_evidence if e["evidence_status"] == "MISSING"),

            },

        )

        db.add(audit)

        db.commit()

        db.refresh(pack)

        logger.info("Defense Pack %s generated for org %s (hash=%s)", pack_version, organization_id, content_hash)

        return pack



    # ------------------------------------------------------------------



    @staticmethod

    def get_defense_pack(pack_id: str, organization_id: str, db: Session) -> Optional[ComplianceDefensePack]:

        return (

            db.query(ComplianceDefensePack)

            .filter(

                ComplianceDefensePack.id == pack_id,

                ComplianceDefensePack.organization_id == organization_id,

            )

            .first()

        )



    @staticmethod

    def get_defense_packs(organization_id: str, db: Session) -> List[ComplianceDefensePack]:

        return (

            db.query(ComplianceDefensePack)

            .filter(ComplianceDefensePack.organization_id == organization_id)

            .order_by(ComplianceDefensePack.created_at.desc())

            .all()

        )



    @staticmethod

    def get_defense_pack_manifest(

        pack_id: str, organization_id: str, db: Session

    ) -> List[ComplianceEvidenceManifest]:

        pack = DefensePackService.get_defense_pack(pack_id, organization_id, db)

        if not pack:

            return []

        return (

            db.query(ComplianceEvidenceManifest)

            .filter(ComplianceEvidenceManifest.defense_pack_id == pack_id)

            .all()

        )



    @staticmethod

    def export_defense_pack_json(

        pack_id: str,

        organization_id: str,

        db: Session,

        actor: Optional[str] = None,

    ) -> Dict[str, Any]:

        """Return full canonical pack JSON for download. Emits export audit log."""

        pack = DefensePackService.get_defense_pack(pack_id, organization_id, db)

        if not pack:

            raise ValueError(f"Pack {pack_id} not found for organisation {organization_id}")



        audit = AuditLog(

            organization_id=organization_id,

            id=generate_uuid(),

            user_name=actor or "system",

            user_role="system",

            action="COMPLIANCE_DEFENSE_PACK_EXPORTED",

            target_type="ComplianceDefensePack",

            target_id=pack.id,

            details={

                "organization_id": organization_id,

                "pack_id": pack.id,

                "pack_version": pack.pack_version,

                "content_hash": pack.content_hash,

                "engine_version": pack.engine_version,

            },

        )

        db.add(audit)

        db.commit()



        return {

            "pack_id": pack.id,

            "pack_version": pack.pack_version,

            "organization_id": pack.organization_id,

            "snapshot_id": pack.snapshot_id,

            "status": pack.status,

            "content_hash": pack.content_hash,

            "engine_version": pack.engine_version,

            "generated_at": pack.generated_at.isoformat() if pack.generated_at else None,

            "manifest": pack.manifest,

        }



    # ------------------------------------------------------------------

    # Canonical payload builder (13 sections)

    # ------------------------------------------------------------------



    @staticmethod

    def _build_canonical_payload(

        org: EnterpriseProfile,

        snapshot: ComplianceIntelligenceSnapshot,

        assessments: list,

        obligations: list,

        tasks: list,

        trigger_events: list,

        alerts: list,

        reg_evidence: list,

        org_evidence: list,

        op_evidence: list,

    ) -> Dict[str, Any]:

        task_map: Dict[str, ComplianceTask] = {t.regulatory_obligation_id: t for t in tasks if t.regulatory_obligation_id}



        return {

            # 1. Organisation Profile

            "organization": {

                "id": org.id,

                "name": org.organization_name,

                "country": org.country,

                "industry_sector": getattr(org, "industry_sector", None),

                "discovery_status": org.discovery_status,

                "business_activities": org.business_activities or [],

                "locations": org.locations or [],

            },

            # 2. Regulatory Landscape (from snapshot, not re-derived)

            "legal_landscape": snapshot.legal_summary,

            # 3. Applicability Assessments

            "applicability_assessments": [

                {

                    "id": a.id,

                    "regulation_id": a.regulation_id,

                    "status": a.status,

                    "score": a.applicability_score,

                    "rationale": a.rationale,

                    "engine_version": a.engine_version,

                }

                for a in assessments

            ],

            # 4. Active Regulatory Obligations

            "regulatory_obligations": [

                {

                    "id": o.id,

                    "obligation_code": o.obligation_code,

                    "title": o.title,

                    "description": o.description,

                    "regulation_id": o.regulation_id,

                    "obligation_type": o.obligation_type,

                    "priority": o.priority,

                    "status": o.status,

                    "source_citation": o.source_citation,

                    "authoritative_source_url": o.authoritative_source_url,

                    "trigger_type": o.trigger_type,

                    "trigger_offset_value": o.trigger_offset_value,

                    "trigger_offset_unit": o.trigger_offset_unit,

                    "due_rule": o.due_rule,

                    "effective_date": o.effective_date.isoformat() if o.effective_date else None,

                }

                for o in obligations

            ],

            # 5. Operational Compliance Tasks

            "compliance_tasks": [

                {

                    "id": t.id,

                    "control_code": t.control_code,

                    "title": t.title,

                    "regulatory_obligation_id": t.regulatory_obligation_id,

                    "effective_status": _task_status_effective(t),

                    "priority": t.priority,

                    "due_date": t.due_date.isoformat() if t.due_date else None,

                    "assignee": t.assignee,

                }

                for t in tasks

            ],

            # 6. Trigger Events & Deadlines

            "trigger_events": [

                {

                    "id": te.id,

                    "task_id": None,

                    "event_type": te.event_type,

                    "triggered_at": te.event_timestamp.isoformat() if te.event_timestamp else None,

                    "calculated_due_date": None,

                }

                for te in trigger_events

            ],

            "deadline_summary": snapshot.deadline_summary,

            # 7. Regulatory Evidence (Layer 1)

            "regulatory_evidence": reg_evidence,

            # 8. Organisation Evidence (Layer 2)

            "organization_evidence": org_evidence,

            # 9. Operational Evidence & Evidence Gaps (Layer 3)

            "operational_evidence": op_evidence,

            # 10. Compliance Alerts

            "compliance_alerts": [

                {

                    "id": a.id,

                    "alert_type": a.alert_type,

                    "severity": a.severity,

                    "status": a.status,

                    "description": a.description,

                }

                for a in alerts

            ],

            # 11. Compliance Posture

            "compliance_posture": {

                "evidence_summary": snapshot.evidence_summary,

                "alert_summary": snapshot.alert_summary,

                "operational_summary": snapshot.operational_summary,

                "obligation_summary": snapshot.obligation_summary,

            },

            # 12. Unresolved Items

            "unresolved_items": snapshot.unresolved_items or [],

            # 13. Provenance Graph + Generation Metadata + Legal Disclaimers

            "provenance_graph": snapshot.provenance_summary,

            "generation_metadata": {

                "engine_version": ENGINE_VERSION,

                "snapshot_id": snapshot.id,

                # NOTE: generated_at is deliberately NOT included in hash computation

            },

            "legal_disclaimers": {

                "compliance_disclaimer": COMPLIANCE_DISCLAIMER,

                "applicability_disclaimer": APPLICABILITY_DISCLAIMER,

            },

        }





# ---------------------------------------------------------------------------

# Utility

# ---------------------------------------------------------------------------



def _parse_dt(value) -> Optional[datetime.datetime]:

    if value is None:

        return None

    if isinstance(value, datetime.datetime):

        return value

    if isinstance(value, str):

        try:

            return datetime.datetime.fromisoformat(value)

        except ValueError:

            return None

    return None



