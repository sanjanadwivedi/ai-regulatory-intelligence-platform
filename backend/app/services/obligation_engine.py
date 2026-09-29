import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    AuditLog
)

logger = logging.getLogger("compliance_platform.obligation_engine")

ENGINE_VERSION = "v1.0.0-deterministic"

class ObligationEngine:
    """
    Deterministic, explainable Regulatory Obligation Engine.
    Strictly gates extraction:
      - ONLY APPLICABLE RegulatoryApplicabilityAssessment records may generate obligations.
      - NOT_APPLICABLE generates ZERO obligations.
      - REQUIRES_REVIEW generates ZERO ACTIVE obligations.
    """

    @classmethod
    def generate_obligations(
        cls,
        organization_id: str,
        db: Session,
        evaluated_by: str = "Compliance Officer"
    ) -> List[RegulatoryObligation]:
        """
        Extract authoritative regulatory obligations for all APPLICABLE assessments of an organization.
        Idempotently persists records and logs an immutable audit event.
        """
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            logger.error("Cannot generate obligations: EnterpriseProfile %s not found", organization_id)
            return []

        # 1. Load all assessments for this organization
        assessments = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.organization_id == organization_id
        ).all()

        applicable_assessments = [a for a in assessments if a.status == "APPLICABLE"]
        non_applicable_assessment_ids = {a.id for a in assessments if a.status in ["NOT_APPLICABLE", "REQUIRES_REVIEW"]}

        # If any old obligations exist for assessments that are no longer APPLICABLE, supersede them
        if non_applicable_assessment_ids:
            superseded_obs = db.query(RegulatoryObligation).filter(
                RegulatoryObligation.organization_id == organization_id,
                RegulatoryObligation.applicability_assessment_id.in_(non_applicable_assessment_ids),
                RegulatoryObligation.status == "ACTIVE"
            ).all()
            for obs in superseded_obs:
                obs.status = "SUPERSEDED"
                obs.updated_at = datetime.datetime.utcnow()
            if superseded_obs:
                db.commit()

        generated_obligations: List[RegulatoryObligation] = []

        for assessment in applicable_assessments:
            reg = db.query(Regulation).filter(Regulation.id == assessment.regulation_id).first()
            if not reg:
                continue

            extracted = cls._extract_obligations_for_regulation(
                profile=profile,
                assessment=assessment,
                regulation=reg,
                db=db
            )
            generated_obligations.extend(extracted)

        # 2. Log immutable audit trail
        active_count = sum(1 for o in generated_obligations if o.status == "ACTIVE")
        review_count = sum(1 for o in generated_obligations if o.status == "REQUIRES_REVIEW")

        audit = AuditLog(
            user_name=evaluated_by,
            user_role="Compliance Officer",
            action="OBLIGATIONS_GENERATED",
            target_type="REGULATORY_OBLIGATION",
            target_id=organization_id,
            details={
                "organization_id": organization_id,
                "organization_name": profile.organization_name,
                "applicable_regulations_count": len(applicable_assessments),
                "active_obligations_count": active_count,
                "requires_review_obligations_count": review_count,
                "total_generated_count": len(generated_obligations),
                "engine_version": ENGINE_VERSION
            }
        )
        db.add(audit)
        db.commit()

        return generated_obligations

    @classmethod
    def _extract_obligations_for_regulation(
        cls,
        profile: EnterpriseProfile,
        assessment: RegulatoryApplicabilityAssessment,
        regulation: Regulation,
        db: Session
    ) -> List[RegulatoryObligation]:
        """
        Deterministically extract authoritative obligations for a confirmed applicable regulation.
        """
        obligations: List[RegulatoryObligation] = []
        reg_title = (regulation.title or "").lower()

        is_certin = (regulation.id == "reg-cyber-2026" or "cert-in" in reg_title or "70b" in reg_title)
        default_url = "https://www.cert-in.org.in/Directions70B.jsp" if is_certin else (regulation.source_url or "")
        default_ref = "Section 70B(6) IT Act, 2000" if is_certin else (regulation.doc_number or f"Statutory provisions under {regulation.authority}")

        # Build base evidence links
        reg_evidence_refs = [{
            "regulation_id": regulation.id,
            "title": regulation.title,
            "authority": regulation.authority,
            "source_url": regulation.resolved_source_url or regulation.source_url or default_url,
            "statutory_reference": regulation.doc_number or default_ref
        }]

        org_evidence_refs = [{
            "organization_name": profile.organization_name,
            "matched_jurisdiction": profile.country or "India",
            "matched_activities": profile.business_activities or [],
            "applicability_assessment_id": assessment.id
        }]

        # ─── SPECIFIC STATUTORY OBLIGATIONS: CERT-In DIRECTIONS (reg-cyber-2026) ────
        if regulation.id == "reg-cyber-2026" or "cert-in" in reg_title or "70b" in reg_title:
            certin_specs = [
                {
                    "code": "OBL-CERTIN-INCIDENT-6H",
                    "title": "Mandatory Cyber Incident Reporting within 6 Hours",
                    "description": (
                        "Mandatory reporting of specified cyber security incidents to CERT-In within 6 hours "
                        "of noticing or being brought to notice by service providers, intermediaries, data centres, "
                        "body corporate, and cloud service providers."
                    ),
                    "type": "REPORTING",
                    "responsible": "Incident Response / SecOps / CISO",
                    "frequency": "UPON_INCIDENT",
                    "due_rule": "Within 6 hours of incident detection or notice",
                    "trigger_type": "INCIDENT_DETECTED",
                    "trigger_offset_value": 6,
                    "trigger_offset_unit": "HOURS",
                    "citation": "Direction 2(a) under Section 70B(6) of Information Technology Act, 2000",
                    "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
                    "priority": "CRITICAL",
                    "effective_date": datetime.date(2022, 6, 27)
                },
                {
                    "code": "OBL-CERTIN-LOGS-180D",
                    "title": "Mandatory ICT System Log Retention for 180 Days",
                    "description": (
                        "Mandatory maintenance and secure retention of logs of all ICT systems for a rolling "
                        "period of 180 days within the Indian jurisdiction to facilitate incident analysis."
                    ),
                    "type": "RECORD_KEEPING",
                    "responsible": "Cloud Infrastructure & SecOps",
                    "frequency": "CONTINUOUS",
                    "due_rule": "Continuous rolling retention of 180 days within Indian jurisdiction",
                    "trigger_type": None,
                    "trigger_offset_value": None,
                    "trigger_offset_unit": None,
                    "citation": "Direction 4 under Section 70B(6) of Information Technology Act, 2000",
                    "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
                    "priority": "HIGH",
                    "effective_date": datetime.date(2022, 6, 27)
                },
                {
                    "code": "OBL-CERTIN-NTP-SYNC",
                    "title": "Mandatory ICT System Clock Synchronization with Standard NTP",
                    "description": (
                        "Mandatory connection to Network Time Protocol (NTP) Server of National Physical Laboratory (NPL) "
                        "or National Informatics Centre (NIC) or servers traceable to them to synchronize all ICT system clocks."
                    ),
                    "type": "SECURITY_CONTROL",
                    "responsible": "Infrastructure & Network Engineering",
                    "frequency": "CONTINUOUS",
                    "due_rule": "Continuous synchronization with NPL / NIC NTP servers",
                    "trigger_type": None,
                    "trigger_offset_value": None,
                    "trigger_offset_unit": None,
                    "citation": "Direction 1 under Section 70B(6) of Information Technology Act, 2000",
                    "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
                    "priority": "MEDIUM",
                    "effective_date": datetime.date(2022, 6, 27)
                },
                {
                    "code": "OBL-CERTIN-POC-DESIGNATION",
                    "title": "Designation of Point of Contact (PoC) with CERT-In",
                    "description": (
                        "Designate a Point of Contact (PoC) to interface with CERT-In and communicate all relevant "
                        "contact information, updates, and incident coordination."
                    ),
                    "type": "GOVERNANCE",
                    "responsible": "Information Security & Legal/Compliance",
                    "frequency": "ONCE_AND_UPON_CHANGE",
                    "due_rule": "Immediate designation and prompt reporting of any POC changes",
                    "trigger_type": None,
                    "trigger_offset_value": None,
                    "trigger_offset_unit": None,
                    "citation": "Direction 5 under Section 70B(6) of Information Technology Act, 2000",
                    "source_url": "https://www.cert-in.org.in/Directions70B.jsp",
                    "priority": "HIGH",
                    "effective_date": datetime.date(2022, 6, 27)
                }
            ]

            for spec in certin_specs:
                ob = cls._upsert_obligation(
                    organization_id=profile.id,
                    regulation_id=regulation.id,
                    assessment_id=assessment.id,
                    obligation_code=spec["code"],
                    title=spec["title"],
                    description=spec["description"],
                    obligation_type=spec["type"],
                    responsible_function=spec["responsible"],
                    frequency=spec["frequency"],
                    due_rule=spec["due_rule"],
                    trigger_type=spec.get("trigger_type"),
                    trigger_offset_value=spec.get("trigger_offset_value"),
                    trigger_offset_unit=spec.get("trigger_offset_unit"),
                    effective_date=spec["effective_date"],
                    source_citation=spec["citation"],
                    authoritative_source_url=spec["source_url"],
                    regulatory_evidence_refs=reg_evidence_refs,
                    organization_evidence_refs=org_evidence_refs,
                    missing_information=None,
                    status="ACTIVE",
                    priority=spec["priority"],
                    db=db
                )
                obligations.append(ob)

        # ─── GENERIC APPLICABLE REGULATIONS WITHOUT STRUCTURED STATUTORY OBLIGATIONS ───
        else:
            # If a regulation was marked APPLICABLE but lacks structured obligation text in repository
            ob = cls._upsert_obligation(
                organization_id=profile.id,
                regulation_id=regulation.id,
                assessment_id=assessment.id,
                obligation_code=f"OBL-REV-{regulation.id[:12]}",
                title=f"Statutory Obligations Review for {regulation.title}",
                description=f"Authoritative obligation text for '{regulation.title}' is not sufficiently structured in the repository.",
                obligation_type="OTHER",
                responsible_function="Compliance Officer",
                frequency=None,
                due_rule=None,
                trigger_type=None,
                trigger_offset_value=None,
                trigger_offset_unit=None,
                effective_date=regulation.effective_date,
                source_citation=f"Authoritative provisions under {regulation.authority}",
                authoritative_source_url=regulation.source_url,
                regulatory_evidence_refs=reg_evidence_refs,
                organization_evidence_refs=org_evidence_refs,
                missing_information=[{"question": "Authoritative statutory obligation provisions are not structured in repository.", "status": "MISSING_EVIDENCE"}],
                status="REQUIRES_REVIEW",
                priority="MEDIUM",
                db=db
            )
            obligations.append(ob)

        return obligations

    @classmethod
    def _upsert_obligation(
        cls,
        organization_id: str,
        regulation_id: str,
        assessment_id: str,
        obligation_code: str,
        title: str,
        description: str,
        obligation_type: str,
        responsible_function: Optional[str],
        frequency: Optional[str],
        due_rule: Optional[str],
        trigger_type: Optional[str],
        trigger_offset_value: Optional[int],
        trigger_offset_unit: Optional[str],
        effective_date: Optional[datetime.date],
        source_citation: str,
        authoritative_source_url: Optional[str],
        regulatory_evidence_refs: Optional[List[Dict[str, Any]]],
        organization_evidence_refs: Optional[List[Dict[str, Any]]],
        missing_information: Optional[List[Dict[str, Any]]],
        status: str,
        priority: str,
        db: Session
    ) -> RegulatoryObligation:
        """
        Idempotently create or update a single RegulatoryObligation.
        """
        existing = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id,
            RegulatoryObligation.regulation_id == regulation_id,
            RegulatoryObligation.obligation_code == obligation_code
        ).first()

        if not existing:
            existing = RegulatoryObligation(
                organization_id=organization_id,
                regulation_id=regulation_id,
                applicability_assessment_id=assessment_id,
                obligation_code=obligation_code,
                title=title,
                description=description,
                obligation_type=obligation_type,
                responsible_function=responsible_function,
                frequency=frequency,
                due_rule=due_rule,
                trigger_type=trigger_type,
                trigger_offset_value=trigger_offset_value,
                trigger_offset_unit=trigger_offset_unit,
                effective_date=effective_date,
                source_citation=source_citation,
                authoritative_source_url=authoritative_source_url,
                regulatory_evidence_refs=regulatory_evidence_refs,
                organization_evidence_refs=organization_evidence_refs,
                missing_information=missing_information,
                status=status,
                priority=priority,
                engine_version=ENGINE_VERSION
            )
            db.add(existing)
        else:
            existing.applicability_assessment_id = assessment_id
            existing.title = title
            existing.description = description
            existing.obligation_type = obligation_type
            existing.responsible_function = responsible_function
            existing.frequency = frequency
            existing.due_rule = due_rule
            existing.trigger_type = trigger_type
            existing.trigger_offset_value = trigger_offset_value
            existing.trigger_offset_unit = trigger_offset_unit
            existing.effective_date = effective_date
            existing.source_citation = source_citation
            existing.authoritative_source_url = authoritative_source_url
            existing.regulatory_evidence_refs = regulatory_evidence_refs
            existing.organization_evidence_refs = organization_evidence_refs
            existing.missing_information = missing_information
            existing.status = status
            existing.priority = priority
            existing.engine_version = ENGINE_VERSION
            existing.updated_at = datetime.datetime.utcnow()

        db.commit()
        db.refresh(existing)
        return existing
