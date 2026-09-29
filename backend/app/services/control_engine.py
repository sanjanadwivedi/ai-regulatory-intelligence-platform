import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    InternalControl,
    RegulatoryObligation,
    ObligationControlMapping,
    ControlAssessment,
    DiscoveredFact,
    AuditLog,
    ComplianceTaskEvidence
)

logger = logging.getLogger("compliance_platform.control_engine")

ENGINE_VERSION = "v1.0.0-deterministic"

class ControlEngine:
    """
    Deterministic Control Engine evaluating organization controls.
    """

    @classmethod
    def evaluate_organization_controls(
        cls,
        organization_id: str,
        db: Session,
        evaluated_by: str = "System"
    ) -> List[ControlAssessment]:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.id == organization_id).first()
        if not profile:
            logger.error("Cannot evaluate controls: EnterpriseProfile %s not found", organization_id)
            return []

        # Find ACTIVE obligations belonging to this organization
        obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.organization_id == organization_id,
            RegulatoryObligation.status == "ACTIVE"
        ).all()

        if not obligations:
            return []

        obligation_ids = [ob.id for ob in obligations]

        # Find active mappings for these obligations
        mappings = db.query(ObligationControlMapping).filter(
            ObligationControlMapping.organization_id == organization_id,
            ObligationControlMapping.obligation_id.in_(obligation_ids),
            ObligationControlMapping.active == 1
        ).all()

        # Deduplicate shared controls
        control_ids = list(set(m.control_id for m in mappings))
        
        controls = db.query(InternalControl).filter(
            InternalControl.organization_id == organization_id,
            InternalControl.id.in_(control_ids)
        ).all()

        new_assessments = []

        for control in controls:
            assessment = cls.evaluate_control(control.id, organization_id, db, evaluated_by)
            if assessment and assessment.id: # If new assessment was created
                # Check if it was newly added in this session.
                # To be simple, we just return the latest for each anyway, or only the newly appended ones.
                # evaluate_control adds it to db, but we can check if it's dirty/new.
                new_assessments.append(assessment)

        db.commit()
        return new_assessments

    @classmethod
    def evaluate_control(
        cls,
        control_id: str,
        organization_id: str,
        db: Session,
        evaluated_by: str = "System"
    ) -> Optional[ControlAssessment]:
        control = db.query(InternalControl).filter(
            InternalControl.organization_id == organization_id,
            InternalControl.id == control_id
        ).first()

        if not control:
            return None


        control_state = control.status or "DRAFT"
        evidence_summary, missing_info = cls._evaluate_evidence(control, db)
        assessment_status = cls._determine_assessment_status(control_state, evidence_summary)

        # Check idempotency
        latest_assessment = db.query(ControlAssessment).filter(
            ControlAssessment.organization_id == organization_id,
            ControlAssessment.control_id == control_id
        ).order_by(ControlAssessment.evaluated_at.desc()).first()

        if latest_assessment:
            if (latest_assessment.assessment_status == assessment_status and 
                latest_assessment.control_state == control_state and 
                latest_assessment.evidence_summary == evidence_summary):
                return latest_assessment

        # Create new assessment
        assessment = ControlAssessment(
            organization_id=organization_id,
            control_id=control_id,
            assessment_status=assessment_status,
            control_state=control_state,
            evidence_summary=evidence_summary,
            missing_information=missing_info,
            evaluated_by=evaluated_by,
            engine_version=ENGINE_VERSION
        )
        db.add(assessment)

        # Audit Log
        prev_status = latest_assessment.assessment_status if latest_assessment else "NONE"
        audit_log = AuditLog(
            organization_id=organization_id,
            user_name=evaluated_by,
            user_role="System",
            action="CONTROL_EVALUATED",
            target_type="InternalControl",
            target_id=control_id,
            details={
                "previous_status": prev_status,
                "new_status": assessment_status,
                "control_state": control_state,
                "evidence_summary": evidence_summary,
                "engine_version": ENGINE_VERSION,
                "reason": f"State transition from {prev_status} to {assessment_status}"
            }
        )
        db.add(audit_log)
        
        db.commit()
        db.refresh(assessment)

        # Trigger downstream PostureEngine recalculation
        from app.services.posture_engine import PostureEngine
        
        mappings = db.query(ObligationControlMapping).filter(
            ObligationControlMapping.control_id == control_id,
            ObligationControlMapping.organization_id == organization_id,
            ObligationControlMapping.active == 1
        ).all()
        
        reg_ids = set()
        for mapping in mappings:
            PostureEngine.evaluate_obligation_posture(mapping.obligation_id, organization_id, db, evaluated_by)
            ob = db.query(RegulatoryObligation).filter(RegulatoryObligation.id == mapping.obligation_id).first()
            if ob:
                reg_ids.add(ob.regulation_id)
                
        for reg_id in reg_ids:
            PostureEngine.evaluate_regulation_posture(reg_id, organization_id, db, evaluated_by)
            
        PostureEngine.evaluate_organization_posture(organization_id, db, evaluated_by)

        return assessment

    @classmethod
    def _evaluate_evidence(cls, control: InternalControl, db: Session) -> Tuple[str, Optional[Dict[str, Any]]]:
        # Legacy DiscoveredFacts
        facts = db.query(DiscoveredFact).filter(
            DiscoveredFact.organization_id == control.organization_id,
            DiscoveredFact.fact_type == "CONTROL_IMPLEMENTATION",
            DiscoveredFact.fact_value == control.control_code
        ).all()

        # Task Evidence (Direct or via Task for legacy)
        from app.models.domain import ComplianceTask
        
        task_evidence = db.query(ComplianceTaskEvidence).outerjoin(
            ComplianceTask, ComplianceTaskEvidence.task_id == ComplianceTask.id
        ).filter(
            ComplianceTaskEvidence.organization_id == control.organization_id,
            ComplianceTaskEvidence.status == "ACTIVE",
            (ComplianceTaskEvidence.control_id == control.id) | (ComplianceTask.control_id == control.id)
        ).all()

        current_utc = datetime.datetime.utcnow()
        valid_task_evidence = []
        for ev in task_evidence:
            if ev.valid_until and ev.valid_until < current_utc:
                continue # Expired
            valid_task_evidence.append(ev)

        if not facts and not valid_task_evidence:
            return "NO_EVIDENCE", {"reason": "No valid evidence records found for this control."}

        # Check evidence strength
        authoritative = any(f.evidence_strength == "AUTHORITATIVE" for f in facts) or \
                        any(e.evidence_strength == "AUTHORITATIVE" for e in valid_task_evidence)
                        
        documented = any(f.evidence_strength == "DOCUMENTED" for f in facts) or \
                     any(e.evidence_strength == "DOCUMENTED" for e in valid_task_evidence)
                     
        inferred = any(f.evidence_strength in ["INFERRED", "ATTESTED"] for f in facts) or \
                   any(e.evidence_strength in ["INFERRED", "ATTESTED"] for e in valid_task_evidence)

        if authoritative:
            return "EVIDENCE_AUTHORITATIVE", None
        elif documented:
            return "EVIDENCE_PRESENT", None
        elif inferred:
            return "EVIDENCE_INSUFFICIENT", {"reason": "Evidence is only inferred or attested. Authoritative evidence required."}
        else:
            return "EVIDENCE_INSUFFICIENT", {"reason": "Evidence strength is insufficient."}

    @classmethod
    def _determine_assessment_status(cls, control_state: str, evidence_summary: str) -> str:
        if control_state in ["DRAFT", "PLANNED"]:
            return "CONTROL_GAP"
        
        if control_state == "RETIRED":
            return "CONTROL_GAP"

        if control_state == "UNDER_REVIEW":
            return "CONTROL_REVIEW_REQUIRED"
            
        if control_state == "INEFFECTIVE":
            return "INEFFECTIVE"

        if control_state == "IMPLEMENTED":
            if evidence_summary == "NO_EVIDENCE":
                return "CONTROL_REVIEW_REQUIRED"
            if evidence_summary == "EVIDENCE_INSUFFICIENT":
                return "CONTROL_REVIEW_REQUIRED"
            # It needs to be explicitly EFFECTIVE state and authoritative evidence to be EFFECTIVE
            # If implemented with authoritative evidence, we still might require review unless state is EFFECTIVE
            return "CONTROL_REVIEW_REQUIRED"

        if control_state == "EFFECTIVE":
            if evidence_summary == "EVIDENCE_AUTHORITATIVE":
                return "EFFECTIVE"
            else:
                return "CONTROL_REVIEW_REQUIRED"

        return "CONTROL_REVIEW_REQUIRED"

    @classmethod
    def get_obligation_posture(cls, obligation_id: str, organization_id: str, db: Session) -> str:
        obligation = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.id == obligation_id,
            RegulatoryObligation.organization_id == organization_id
        ).first()

        if not obligation or obligation.status != "ACTIVE":
            return "CONTROL_GAP"

        mappings = db.query(ObligationControlMapping).filter(
            ObligationControlMapping.obligation_id == obligation_id,
            ObligationControlMapping.organization_id == organization_id,
            ObligationControlMapping.active == 1
        ).all()

        if not mappings:
            return "CONTROL_GAP"

        control_ids = [m.control_id for m in mappings]
        
        assessments = []
        for cid in control_ids:
            latest = db.query(ControlAssessment).filter(
                ControlAssessment.organization_id == organization_id,
                ControlAssessment.control_id == cid
            ).order_by(ControlAssessment.evaluated_at.desc()).first()
            if latest:
                assessments.append(latest)

        if not assessments:
            return "CONTROL_GAP"

        statuses = set(a.assessment_status for a in assessments)

        if "INEFFECTIVE" in statuses or "CONTROL_GAP" in statuses:
            return "CONTROL_GAP"

        if "CONTROL_REVIEW_REQUIRED" in statuses:
            return "CONTROL_REVIEW_REQUIRED"

        if all(s == "EFFECTIVE" for s in statuses):
            return "SATISFIED"

        return "CONTROL_REVIEW_REQUIRED"


