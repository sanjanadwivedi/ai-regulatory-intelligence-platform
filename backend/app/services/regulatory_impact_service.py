"""
Regulatory Impact Service — Phase 22
=====================================
Analyzes the impact of a RegulatoryChange on the organization.

Provides a deterministic mapping from RegulatoryChange to RegulatoryObligationImpact.
Preserves non-destructive posture traceability.
"""

import logging
import datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

from app.models.domain import (
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    RegulatoryChange,
    Regulation,
    RegulatoryObligationImpact,
    ObligationControlMapping,
    ComplianceTask,
    AuditLog,
)

logger = logging.getLogger("compliance_platform.impact_service")

def trigger_impact_analysis(
    db: Session,
    regulation_id: str,
    change_id: Optional[str],
    triggered_by: str
) -> None:
    """
    LEGACY FUNCTION: Replaced by propagate_change_impact.
    This was previously mutating assessment and obligation statuses.
    We are keeping the signature for backward compatibility with older tests,
    but it now simply no-ops because we enforce manual impact propagation
    and non-destructive state changes.
    """
    logger.warning("trigger_impact_analysis is deprecated. Use propagate_change_impact.")
    pass


def propagate_change_impact(
    db: Session,
    change_id: str,
    organization_id: str,
    triggered_by: str
) -> Dict[str, Any]:
    """
    Manually triggered impact propagation for a given RegulatoryChange and Tenant.
    
    Case A: Regulation is NOT APPLICABLE -> no impact.
    Case B: Regulation is APPLICABLE and obligations exist -> create RegulatoryObligationImpact records.
    Case C: Regulation is APPLICABLE but zero obligations exist -> returns REQUIRES_HUMAN_REVIEW (mapping gap).
    """
    change = db.query(RegulatoryChange).filter(RegulatoryChange.id == change_id).first()
    if not change:
        raise ValueError("Change not found")
        
    reg = change.regulation
    
    # 1. Check Applicability
    assessment = db.query(RegulatoryApplicabilityAssessment).filter(
        RegulatoryApplicabilityAssessment.regulation_id == reg.id,
        RegulatoryApplicabilityAssessment.organization_id == organization_id
    ).first()
    
    if not assessment or assessment.status != "APPLICABLE":
        return {
            "regulatory_change_id": change_id,
            "organization_id": organization_id,
            "impact_status": "NOT_AFFECTED",
            "summary": {
                "obligations_affected": 0,
                "controls_affected": 0,
                "tasks_affected": 0,
                "human_review_required": 0
            },
            "mapping_gap": False,
            "reason": "Regulation is not applicable to this organization."
        }
        
    # 2. Check for Obligations
    obligations = db.query(RegulatoryObligation).filter(
        RegulatoryObligation.regulation_id == reg.id,
        RegulatoryObligation.organization_id == organization_id,
        RegulatoryObligation.status == "ACTIVE"
    ).all()
    
    if not obligations:
        # Case C: Applicable, but no extracted obligations
        return {
            "regulatory_change_id": change_id,
            "organization_id": organization_id,
            "impact_status": "REQUIRES_HUMAN_REVIEW",
            "summary": {
                "obligations_affected": 0,
                "controls_affected": 0,
                "tasks_affected": 0,
                "human_review_required": 1
            },
            "mapping_gap": True,
            "reason": "Regulation is applicable, but no actionable obligations are currently available for downstream impact propagation."
        }
        
    # 3. Propagate to Obligations
    affected_obligations = []
    affected_controls = set()
    affected_tasks = set()
    
    for ob in obligations:
        # Determine confidence (here we are conservative)
        # If we had robust diff matching, we could set DIRECTLY_AFFECTED for exact matches.
        # For now, we assume POTENTIALLY_AFFECTED.
        
        # Upsert Impact
        impact = db.query(RegulatoryObligationImpact).filter(
            RegulatoryObligationImpact.organization_id == organization_id,
            RegulatoryObligationImpact.regulatory_change_id == change_id,
            RegulatoryObligationImpact.obligation_id == ob.id
        ).first()
        
        if not impact:
            impact = RegulatoryObligationImpact(
                organization_id=organization_id,
                regulatory_change_id=change_id,
                obligation_id=ob.id,
                impact_status="POTENTIALLY_AFFECTED",
                review_status="REQUIRES_REVIEW",
                reason="Regulation changed, requiring review of mapped obligations."
            )
            db.add(impact)
            
        affected_obligations.append(ob.id)
        
        # Traverse downstream to Controls
        mappings = db.query(ObligationControlMapping).filter(
            ObligationControlMapping.obligation_id == ob.id,
            ObligationControlMapping.organization_id == organization_id,
            ObligationControlMapping.active == 1
        ).all()
        for m in mappings:
            affected_controls.add(m.control_id)
            
        # Traverse downstream to Tasks
        tasks = db.query(ComplianceTask).filter(
            ComplianceTask.regulatory_obligation_id == ob.id,
            ComplianceTask.organization_id == organization_id
        ).all()
        for t in tasks:
            affected_tasks.add(t.id)
            
    # Audit Log
    audit = AuditLog(
        organization_id=organization_id,
        user_name=triggered_by,
        user_role="SYSTEM",
        action="REGULATORY_IMPACT_PROPAGATION",
        target_type="RegulatoryChange",
        target_id=change_id,
        details={
            "obligations_affected": len(affected_obligations),
            "controls_affected": len(affected_controls),
            "tasks_affected": len(affected_tasks)
        }
    )
    db.add(audit)
    db.commit()
    
    return {
        "regulatory_change_id": change_id,
        "organization_id": organization_id,
        "impact_status": "POTENTIALLY_AFFECTED",
        "summary": {
            "obligations_affected": len(affected_obligations),
            "controls_affected": len(affected_controls),
            "tasks_affected": len(affected_tasks),
            "human_review_required": len(affected_obligations)
        },
        "mapping_gap": False,
        "reason": "Successfully propagated impact to downstream obligations."
    }
