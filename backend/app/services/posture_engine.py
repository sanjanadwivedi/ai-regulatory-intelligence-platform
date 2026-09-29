import logging
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    InternalControl,
    ObligationControlMapping,
    ControlAssessment,
    ObligationPosture,
    RegulationPosture,
    OrganizationCompliancePosture,
    AuditLog
)

logger = logging.getLogger("compliance_platform.posture_engine")

ENGINE_VERSION = "v1.0.0-posture"

class PostureEngine:
    """
    Deterministic Compliance Posture & Assessment Engine.
    Evaluates obligation, regulation, and organization compliance posture.
    """

    @classmethod
    def evaluate_obligation_posture(
        cls,
        obligation_id: str,
        organization_id: str,
        db: Session,
        evaluated_by: str = "System"
    ) -> Optional[ObligationPosture]:
        
        obligation = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.id == obligation_id,
            RegulatoryObligation.organization_id == organization_id
        ).first()

        if not obligation:
            logger.error("Obligation %s not found for organization %s", obligation_id, organization_id)
            return None

        # Applicability determines everything
        applicability = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.id == obligation.applicability_assessment_id,
            RegulatoryApplicabilityAssessment.organization_id == organization_id
        ).first()

        if not applicability or applicability.status == "NOT_APPLICABLE":
            # If applicability changed to NOT_APPLICABLE, we exclude it from compliance requirements.
            # We don't track a posture record for NOT_APPLICABLE obligations.
            return None

        status = applicability.status
        missing_info = None
        
        control_count = 0
        effective_control_count = 0
        control_gap_count = 0
        review_required_count = 0

        posture_status = "CONTROL_GAP"

        if status == "REQUIRES_REVIEW":
            posture_status = "CONTROL_REVIEW_REQUIRED"
            missing_info = applicability.missing_information
        elif status == "APPLICABLE":
            mappings = db.query(ObligationControlMapping).filter(
                ObligationControlMapping.obligation_id == obligation.id,
                ObligationControlMapping.organization_id == organization_id,
                ObligationControlMapping.active == 1
            ).all()

            control_ids = [m.control_id for m in mappings]
            control_count = len(control_ids)
            
            if control_count == 0:
                posture_status = "CONTROL_GAP"
            else:
                assessments = []
                for cid in control_ids:
                    latest_ca = db.query(ControlAssessment).filter(
                        ControlAssessment.control_id == cid,
                        ControlAssessment.organization_id == organization_id
                    ).order_by(ControlAssessment.evaluated_at.desc()).first()
                    
                    if latest_ca:
                        assessments.append(latest_ca)
                        if latest_ca.assessment_status == "EFFECTIVE":
                            effective_control_count += 1
                        elif latest_ca.assessment_status in ["CONTROL_GAP", "INEFFECTIVE"]:
                            control_gap_count += 1
                        elif latest_ca.assessment_status == "CONTROL_REVIEW_REQUIRED":
                            review_required_count += 1
                    else:
                        control_gap_count += 1

                if control_gap_count > 0:
                    posture_status = "CONTROL_GAP"
                elif review_required_count > 0:
                    posture_status = "CONTROL_REVIEW_REQUIRED"
                elif effective_control_count == control_count:
                    posture_status = "SATISFIED"
                else:
                    posture_status = "CONTROL_GAP" # Fallback

                # Aggregate missing info from control assessments
                # We can aggregate missing info if review is required
                if posture_status == "CONTROL_REVIEW_REQUIRED":
                    aggregated_missing = []
                    for ca in assessments:
                        if ca.assessment_status == "CONTROL_REVIEW_REQUIRED" and ca.missing_information:
                            aggregated_missing.append({
                                "control_id": ca.control_id,
                                "missing_information": ca.missing_information
                            })
                    if aggregated_missing:
                        missing_info = {"control_missing_info": aggregated_missing}

        # Retrieve the latest posture
        latest_posture = db.query(ObligationPosture).filter(
            ObligationPosture.obligation_id == obligation.id,
            ObligationPosture.organization_id == organization_id
        ).order_by(ObligationPosture.evaluated_at.desc()).first()

        # Check immutability / idempotency
        if latest_posture:
            if (latest_posture.posture_status == posture_status and
                latest_posture.control_count == control_count and
                latest_posture.effective_control_count == effective_control_count and
                latest_posture.control_gap_count == control_gap_count and
                latest_posture.review_required_count == review_required_count and
                latest_posture.missing_information == missing_info):
                return latest_posture

        # Create new snapshot
        new_posture = ObligationPosture(
            organization_id=organization_id,
            obligation_id=obligation.id,
            posture_status=posture_status,
            control_count=control_count,
            effective_control_count=effective_control_count,
            control_gap_count=control_gap_count,
            review_required_count=review_required_count,
            missing_information=missing_info,
            evaluated_by=evaluated_by,
            engine_version=ENGINE_VERSION
        )
        db.add(new_posture)
        
        # Create Audit Log
        db.add(AuditLog(
            organization_id=organization_id,
            user_name=evaluated_by,
            user_role="System",
            action="OBLIGATION_POSTURE_EVALUATED",
            target_type="RegulatoryObligation",
            target_id=obligation.id,
            details={
                "previous_status": latest_posture.posture_status if latest_posture else "NONE",
                "new_status": posture_status,
                "engine_version": ENGINE_VERSION
            }
        ))
        
        db.commit()
        db.refresh(new_posture)
        return new_posture

    @classmethod
    def evaluate_regulation_posture(
        cls,
        regulation_id: str,
        organization_id: str,
        db: Session,
        evaluated_by: str = "System"
    ) -> Optional[RegulationPosture]:
        
        regulation = db.query(Regulation).filter(Regulation.id == regulation_id).first()
        if not regulation:
            return None

        # Get active obligations for this regulation
        obligations = db.query(RegulatoryObligation).filter(
            RegulatoryObligation.regulation_id == regulation_id,
            RegulatoryObligation.organization_id == organization_id,
            RegulatoryObligation.status == "ACTIVE"
        ).all()

        applicable_count = 0
        satisfied_count = 0
        gap_count = 0
        review_count = 0
        missing_info_aggregated = []

        for obs in obligations:
            # We fetch the latest obligation posture
            obs_posture = db.query(ObligationPosture).filter(
                ObligationPosture.obligation_id == obs.id,
                ObligationPosture.organization_id == organization_id
            ).order_by(ObligationPosture.evaluated_at.desc()).first()

            if obs_posture:
                applicable_count += 1
                if obs_posture.posture_status == "SATISFIED":
                    satisfied_count += 1
                elif obs_posture.posture_status == "CONTROL_GAP":
                    gap_count += 1
                elif obs_posture.posture_status == "CONTROL_REVIEW_REQUIRED":
                    review_count += 1
                    if obs_posture.missing_information:
                        missing_info_aggregated.append({
                            "obligation_id": obs.id,
                            "missing_information": obs_posture.missing_information
                        })
            else:
                # Need to check applicability - if it has no posture, is it NOT_APPLICABLE?
                applicability = db.query(RegulatoryApplicabilityAssessment).filter(
                    RegulatoryApplicabilityAssessment.id == obs.applicability_assessment_id,
                    RegulatoryApplicabilityAssessment.organization_id == organization_id
                ).first()
                if applicability and applicability.status != "NOT_APPLICABLE":
                    # For some reason there's no posture yet. Treat it as a gap or evaluate it?
                    # We should just evaluate it now to be safe.
                    obs_posture = cls.evaluate_obligation_posture(obs.id, organization_id, db, evaluated_by)
                    if obs_posture:
                        applicable_count += 1
                        if obs_posture.posture_status == "SATISFIED":
                            satisfied_count += 1
                        elif obs_posture.posture_status == "CONTROL_GAP":
                            gap_count += 1
                        elif obs_posture.posture_status == "CONTROL_REVIEW_REQUIRED":
                            review_count += 1
                            if obs_posture.missing_information:
                                missing_info_aggregated.append({
                                    "obligation_id": obs.id,
                                    "missing_information": obs_posture.missing_information
                                })

        # Check applicability assessment for this regulation and organization
        applicability = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.regulation_id == regulation_id,
            RegulatoryApplicabilityAssessment.organization_id == organization_id
        ).order_by(RegulatoryApplicabilityAssessment.evaluated_at.desc()).first()

        posture_status = "NO_APPLICABLE_REQUIREMENTS"
        if applicable_count > 0:
            if gap_count > 0:
                posture_status = "CONTROL_GAP"
            elif review_count > 0:
                posture_status = "CONTROL_REVIEW_REQUIRED"
            elif satisfied_count == applicable_count:
                posture_status = "SATISFIED"
            else:
                posture_status = "CONTROL_GAP"
        elif applicability and applicability.status == "APPLICABLE":
            # Finding-01: An applicable regulation with 0 active obligations is a statutory obligation mapping gap
            posture_status = "CONTROL_REVIEW_REQUIRED"
            review_count = 1
            missing_info_aggregated.append({
                "regulation_id": regulation_id,
                "missing_information": {
                    "mapping_gap": f"Regulation '{regulation.title}' is determined APPLICABLE but has 0 active obligations mapped. Statutory obligation review required.",
                    "reason": "STATUTORY_OBLIGATION_MAPPING_GAP",
                    "status": "REQUIRES_REVIEW"
                }
            })
        elif applicability and applicability.status == "REQUIRES_REVIEW":
            posture_status = "CONTROL_REVIEW_REQUIRED"
            review_count = 1
            missing_info_aggregated.append({
                "regulation_id": regulation_id,
                "missing_information": {
                    "mapping_gap": f"Regulation '{regulation.title}' applicability REQUIRES_REVIEW. Statutory obligation review required.",
                    "reason": "APPLICABILITY_REVIEW_REQUIRED",
                    "status": "REQUIRES_REVIEW"
                }
            })

        missing_info = None
        if missing_info_aggregated:
            missing_info = {"obligation_missing_info": missing_info_aggregated}

        latest_posture = db.query(RegulationPosture).filter(
            RegulationPosture.regulation_id == regulation_id,
            RegulationPosture.organization_id == organization_id
        ).order_by(RegulationPosture.evaluated_at.desc()).first()

        if latest_posture:
            if (latest_posture.posture_status == posture_status and
                latest_posture.applicable_obligation_count == applicable_count and
                latest_posture.satisfied_obligation_count == satisfied_count and
                latest_posture.control_gap_count == gap_count and
                latest_posture.review_required_count == review_count and
                latest_posture.missing_information == missing_info):
                return latest_posture

        new_posture = RegulationPosture(
            organization_id=organization_id,
            regulation_id=regulation_id,
            posture_status=posture_status,
            applicable_obligation_count=applicable_count,
            satisfied_obligation_count=satisfied_count,
            control_gap_count=gap_count,
            review_required_count=review_count,
            missing_information=missing_info,
            evaluated_by=evaluated_by,
            engine_version=ENGINE_VERSION
        )
        db.add(new_posture)
        
        db.add(AuditLog(
            organization_id=organization_id,
            user_name=evaluated_by,
            user_role="System",
            action="REGULATION_POSTURE_EVALUATED",
            target_type="Regulation",
            target_id=regulation_id,
            details={
                "previous_status": latest_posture.posture_status if latest_posture else "NONE",
                "new_status": posture_status,
                "engine_version": ENGINE_VERSION
            }
        ))
        
        db.commit()
        db.refresh(new_posture)
        return new_posture

    @classmethod
    def evaluate_organization_posture(
        cls,
        organization_id: str,
        db: Session,
        evaluated_by: str = "System"
    ) -> Optional[OrganizationCompliancePosture]:
        
        # Get all regulations that have been evaluated for applicability
        assessments = db.query(RegulatoryApplicabilityAssessment).filter(
            RegulatoryApplicabilityAssessment.organization_id == organization_id
        ).all()

        regulation_ids = list(set(a.regulation_id for a in assessments if a.status != "NOT_APPLICABLE"))
        
        app_reg_count = 0
        sat_reg_count = 0
        gap_reg_count = 0
        rev_reg_count = 0

        tot_app_obs = 0
        sat_obs = 0
        gap_obs = 0
        rev_obs = 0
        
        eff_ctrls = 0
        ineff_ctrls = 0
        rev_ctrls = 0

        missing_info_aggregated = []

        for reg_id in regulation_ids:
            reg_posture = db.query(RegulationPosture).filter(
                RegulationPosture.regulation_id == reg_id,
                RegulationPosture.organization_id == organization_id
            ).order_by(RegulationPosture.evaluated_at.desc()).first()

            if not reg_posture:
                reg_posture = cls.evaluate_regulation_posture(reg_id, organization_id, db, evaluated_by)
            
            if reg_posture and reg_posture.posture_status != "NO_APPLICABLE_REQUIREMENTS":
                app_reg_count += 1
                if reg_posture.posture_status == "SATISFIED":
                    sat_reg_count += 1
                elif reg_posture.posture_status == "CONTROL_GAP":
                    gap_reg_count += 1
                elif reg_posture.posture_status == "CONTROL_REVIEW_REQUIRED":
                    rev_reg_count += 1
                    if reg_posture.missing_information:
                        missing_info_aggregated.append({
                            "regulation_id": reg_id,
                            "missing_information": reg_posture.missing_information
                        })

                tot_app_obs += reg_posture.applicable_obligation_count
                sat_obs += reg_posture.satisfied_obligation_count
                gap_obs += reg_posture.control_gap_count
                rev_obs += reg_posture.review_required_count
                
                # Fetch obligation postures for this regulation to count controls accurately
                # This could be optimized, but for determinism we query the active obligations
                active_obs = db.query(RegulatoryObligation).filter(
                    RegulatoryObligation.regulation_id == reg_id,
                    RegulatoryObligation.organization_id == organization_id,
                    RegulatoryObligation.status == "ACTIVE"
                ).all()
                
                for ob in active_obs:
                    ob_posture = db.query(ObligationPosture).filter(
                        ObligationPosture.obligation_id == ob.id,
                        ObligationPosture.organization_id == organization_id
                    ).order_by(ObligationPosture.evaluated_at.desc()).first()
                    
                    if ob_posture:
                        eff_ctrls += ob_posture.effective_control_count
                        # Here ineffective/gap controls are grouped in control_gap_count
                        ineff_ctrls += ob_posture.control_gap_count
                        rev_ctrls += ob_posture.review_required_count

        posture_status = "NO_APPLICABLE_REQUIREMENTS"
        if app_reg_count > 0:
            if gap_reg_count > 0:
                posture_status = "CONTROL_GAP"
            elif rev_reg_count > 0:
                posture_status = "CONTROL_REVIEW_REQUIRED"
            elif sat_reg_count == app_reg_count:
                posture_status = "SATISFIED"
            else:
                posture_status = "CONTROL_GAP"

        if tot_app_obs == 0:
            if app_reg_count > 0:
                compliance_percentage = 0.0
            else:
                compliance_percentage = 100.0
        else:
            compliance_percentage = (sat_obs / tot_app_obs) * 100.0
            if rev_reg_count > 0 and compliance_percentage >= 100.0:
                compliance_percentage = 99.0

        missing_info = None
        if missing_info_aggregated:
            missing_info = {"regulation_missing_info": missing_info_aggregated}

        latest_posture = db.query(OrganizationCompliancePosture).filter(
            OrganizationCompliancePosture.organization_id == organization_id
        ).order_by(OrganizationCompliancePosture.evaluated_at.desc()).first()

        if latest_posture:
            if (latest_posture.posture_status == posture_status and
                latest_posture.applicable_regulation_count == app_reg_count and
                latest_posture.satisfied_regulation_count == sat_reg_count and
                latest_posture.control_gap_regulation_count == gap_reg_count and
                latest_posture.review_required_regulation_count == rev_reg_count and
                latest_posture.total_applicable_obligations == tot_app_obs and
                latest_posture.satisfied_obligations == sat_obs and
                latest_posture.control_gap_obligations == gap_obs and
                latest_posture.review_required_obligations == rev_obs and
                latest_posture.effective_controls == eff_ctrls and
                latest_posture.ineffective_controls == ineff_ctrls and
                latest_posture.controls_requiring_review == rev_ctrls and
                abs((latest_posture.compliance_percentage or 0) - compliance_percentage) < 0.01 and
                latest_posture.missing_information == missing_info):
                return latest_posture

        new_posture = OrganizationCompliancePosture(
            organization_id=organization_id,
            posture_status=posture_status,
            applicable_regulation_count=app_reg_count,
            satisfied_regulation_count=sat_reg_count,
            control_gap_regulation_count=gap_reg_count,
            review_required_regulation_count=rev_reg_count,
            total_applicable_obligations=tot_app_obs,
            satisfied_obligations=sat_obs,
            control_gap_obligations=gap_obs,
            review_required_obligations=rev_obs,
            effective_controls=eff_ctrls,
            ineffective_controls=ineff_ctrls,
            controls_requiring_review=rev_ctrls,
            compliance_percentage=compliance_percentage,
            missing_information=missing_info,
            evaluated_by=evaluated_by,
            engine_version=ENGINE_VERSION
        )
        db.add(new_posture)
        
        db.add(AuditLog(
            organization_id=organization_id,
            user_name=evaluated_by,
            user_role="System",
            action="ORGANIZATION_POSTURE_EVALUATED",
            target_type="EnterpriseProfile",
            target_id=organization_id,
            details={
                "previous_status": latest_posture.posture_status if latest_posture else "NONE",
                "new_status": posture_status,
                "engine_version": ENGINE_VERSION
            }
        ))
        
        db.commit()
        db.refresh(new_posture)
        return new_posture


