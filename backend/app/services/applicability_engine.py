import logging
import datetime
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.domain import (
    EnterpriseProfile, 
    Regulation, 
    RegulatoryApplicabilityAssessment,
    RegulatoryApplicabilityCriterion,
    DiscoveredFact,
    ApplicabilityReviewItem,
    AuditLog
)

logger = logging.getLogger(__name__)

ENGINE_VERSION = "v1.1.0-deterministic"


class ApplicabilityEngine:
    """
    Deterministic Legal Applicability Engine (Core Domain Service)
    Evaluates enterprise facts against authoritative statutory criteria.
    Never hallucinates legal conclusions. Unmet mandatory criteria yield REQUIRES_REVIEW or NOT_APPLICABLE.
    """

    @classmethod
    def evaluate_organization(cls, organization_id: str, db_session: Session = None, evaluated_by: str = "System", **kwargs) -> List[RegulatoryApplicabilityAssessment]:
        # Handle kwargs like db=db_session mapping
        if db_session is None and "db" in kwargs:
            db_session = kwargs["db"]
            
        profile = db_session.query(EnterpriseProfile).filter_by(id=organization_id).first()
        if not profile:
            raise ValueError(f"Organization {organization_id} not found.")

        STRENGTH_RANKS = {"UNKNOWN": 0, "INFERRED": 1, "ATTESTED": 2, "DOCUMENTED": 3, "AUTHORITATIVE": 4}

        org_facts = {}
        for f in db_session.query(DiscoveredFact).filter_by(organization_id=organization_id).all():
            org_facts.setdefault(f.fact_type, []).append(f)

        # Build combined fact context mapping
        org_values_by_type = {}
        def _add_p(typ, lst):
            if lst:
                if isinstance(lst, str): lst = [lst]
                org_values_by_type.setdefault(typ, []).extend([(x, "TRUE", f"EnterpriseProfile.{typ.lower()}", "DOCUMENTED") for x in lst])
                
        _add_p("LOCATION", [profile.country] if profile.country else [])
        _add_p("LOCATION", profile.locations)
        _add_p("BUSINESS_ACTIVITY", profile.business_activities)
        _add_p("LICENSE", profile.licenses)
        
        for f_type, facts in org_facts.items():
            for f in facts:
                strength = getattr(f, "evidence_strength", "UNKNOWN")
                org_values_by_type.setdefault(f_type, []).append((f.fact_value, f.known_state, f.source_url, strength))

        assessments = []
        regulations = db_session.query(Regulation).filter(Regulation.status != "DRAFT").all()

        for reg in regulations:
            try:
                assessment = cls._evaluate_single_regulation(profile, reg, org_values_by_type, db_session, STRENGTH_RANKS)
                assessments.append(assessment)
            except Exception as e:
                logger.error(f"Error evaluating regulation {reg.id} for {organization_id}: {str(e)}")

        applicable_count = sum(1 for a in assessments if a.status == "APPLICABLE")
        not_applicable_count = sum(1 for a in assessments if a.status == "NOT_APPLICABLE")
        requires_review_count = sum(1 for a in assessments if a.status == "REQUIRES_REVIEW")

        audit = AuditLog(
            user_name=evaluated_by,
            user_role="SYSTEM" if evaluated_by == "System" else "COMPLIANCE_OFFICER",
            action="APPLICABILITY_EVALUATION_COMPLETED",
            target_type="REGULATORY_APPLICABILITY",
            target_id="bulk",
            details={
                "organization_id": organization_id,
                "applicable_count": applicable_count,
                "not_applicable_count": not_applicable_count,
                "requires_review_count": requires_review_count,
                "engine_version": ENGINE_VERSION,
                "evaluated_by": evaluated_by
            }
        )
        db_session.add(audit)
        db_session.commit()

        return assessments

    @classmethod
    def _evaluate_single_regulation(
        cls, profile: EnterpriseProfile, regulation: Regulation, 
        org_values_by_type: Dict[str, list], db_session: Session, STRENGTH_RANKS: dict
    ) -> RegulatoryApplicabilityAssessment:
        
        matched_criteria = []
        unmet_criteria = []
        missing_information = []
        org_evidence_refs = []
        signal_refs = []
        
        regulatory_signals = db_session.query(DiscoveredFact).filter(
            DiscoveredFact.organization_id == profile.id,
            DiscoveredFact.fact_type == "REGULATORY_SIGNAL",
            DiscoveredFact.known_state != "FALSE"
        ).all()

        criteria = regulation.applicability_criteria
        if not criteria:
            missing_information.append({
                "criterion_id": "missing",
                "criterion": "structured_criteria_missing",
                "status": "MISSING_EVIDENCE",
                "required_fact": "N/A",
                "question": f"Does the regulation '{regulation.title}' apply?",
                "reason": "Authoritative statutory applicability rules for this regulation are not sufficiently available.",
                "is_mandatory": True,
                "minimum_evidence_strength": "AUTHORITATIVE",
                "evidence_required": "Provide structural rules."
            })
            return cls._persist_assessment(
                profile, regulation, "REQUIRES_REVIEW", 0.40,
                "Regulatory applicability REQUIRES REVIEW due to missing criteria.",
                matched_criteria, unmet_criteria, missing_information, org_evidence_refs, [], signal_refs, db_session
            )

        seen_sig_keys = set()
        for s in regulatory_signals:
            sig_key = (s.fact_value.strip(), (s.snippet or "").strip())
            if sig_key not in seen_sig_keys:
                signal_refs.append({
                    "signal_id": s.id,
                    "signal_name": s.fact_value,
                    "confidence": s.confidence,
                    "evidence_quote": s.snippet,
                    "source_url": s.source_url,
                    "interpretation": "Discovered potential relevance from public website; contextual input only."
                })
                seen_sig_keys.add(sig_key)

        def evaluate_criterion(crit):
            fact_type = crit.evidence_fact_type
            expected = crit.expected_value.lower()
            operator = crit.operator
            req_rank = STRENGTH_RANKS.get(getattr(crit, "minimum_evidence_strength", "DOCUMENTED"), 3)
            
            available_facts = org_values_by_type.get(fact_type, [])
            if not available_facts:
                return "UNKNOWN", f"No authoritative organization fact establishes {crit.criterion_type}.", None
            
            sufficient_facts = []
            for val, state, source, strength in available_facts:
                if STRENGTH_RANKS.get(strength, 0) >= req_rank:
                    sufficient_facts.append((val, state, source))
            
            if not sufficient_facts:
                return "UNKNOWN", f"Evidence found but insufficient strength (requires {getattr(crit, 'minimum_evidence_strength', 'DOCUMENTED')}).", None
            
            for val, state, source in sufficient_facts:
                if state == "UNKNOWN":
                    continue 
                    
                val_lower = val.lower() if isinstance(val, str) else str(val).lower()
                
                if operator in (">", ">=", "<", "<=", "==", "!="):
                    try:
                        v_num = float(val)
                        e_num = float(expected)
                        if operator == ">" and v_num > e_num: return "SATISFIED", f"{fact_type} {v_num} > {e_num}", source
                        if operator == ">=" and v_num >= e_num: return "SATISFIED", f"{fact_type} {v_num} >= {e_num}", source
                        if operator == "<" and v_num < e_num: return "SATISFIED", f"{fact_type} {v_num} < {e_num}", source
                        if operator == "<=" and v_num <= e_num: return "SATISFIED", f"{fact_type} {v_num} <= {e_num}", source
                        if operator == "==" and v_num == e_num: return "SATISFIED", f"{fact_type} {v_num} == {e_num}", source
                        if operator == "!=" and v_num != e_num: return "SATISFIED", f"{fact_type} {v_num} != {e_num}", source
                    except ValueError:
                        pass
                        
                if operator == "CONTAINS":
                    if expected in val_lower:
                        if state == "FALSE":
                            return "NOT_SATISFIED", f"Explicitly verified: does not do '{expected}'", source
                        return "SATISFIED", f"Matches '{expected}'", source
                elif operator == "EQUALS":
                    if val_lower == expected:
                        if state == "FALSE":
                            return "NOT_SATISFIED", f"Explicitly verified: does not match '{expected}'", source
                        return "SATISFIED", f"Equals '{expected}'", source
                elif operator == "IN":
                    exp_list = [x.strip() for x in expected.split(',')]
                    if val_lower in exp_list:
                        if state == "FALSE":
                            return "NOT_SATISFIED", f"Explicitly verified: not in {exp_list}", source
                        return "SATISFIED", f"Found in {exp_list}", source

            for val, state, source in sufficient_facts:
                val_lower = val.lower() if isinstance(val, str) else str(val).lower()
                if state == "FALSE" and (operator == "CONTAINS" and expected in val_lower):
                    return "NOT_SATISFIED", f"Explicitly verified false for '{expected}'", source
                    
            return "UNKNOWN", f"No definitive fact found matching '{expected}' via operator {operator}.", None

        eval_results = {}
        for crit in criteria:
            status, msg, source = evaluate_criterion(crit)
            eval_results[crit.id] = {"status": status, "msg": msg, "source": source, "crit": crit}

        # Evaluate groups
        group_results = {}
        for crit in criteria:
            grp = getattr(crit, "criterion_group", None)
            if grp:
                if grp not in group_results:
                    group_results[grp] = {"operator": getattr(crit, "group_operator", "OR"), "criteria": []}
                group_results[grp]["criteria"].append(eval_results[crit.id])
            else:
                # Treat standalone as an AND group of 1
                grp = f"__standalone_{crit.id}__"
                group_results[grp] = {"operator": "AND", "criteria": [eval_results[crit.id]]}

        final_group_statuses = {}
        for grp, data in group_results.items():
            op = data["operator"]
            statuses = [c["status"] for c in data["criteria"]]
            if op == "OR":
                if "SATISFIED" in statuses:
                    final_group_statuses[grp] = "SATISFIED"
                elif all(s == "NOT_SATISFIED" for s in statuses):
                    final_group_statuses[grp] = "NOT_SATISFIED"
                else:
                    final_group_statuses[grp] = "UNKNOWN"
            elif op == "AND":
                if "NOT_SATISFIED" in statuses:
                    final_group_statuses[grp] = "NOT_SATISFIED"
                elif "UNKNOWN" in statuses:
                    final_group_statuses[grp] = "UNKNOWN"
                else:
                    final_group_statuses[grp] = "SATISFIED"
            else:
                final_group_statuses[grp] = "UNKNOWN"

        # Populate matched, unmet, missing based on group results
        for grp, data in group_results.items():
            grp_status = final_group_statuses[grp]
            for c in data["criteria"]:
                crit = c["crit"]
                status = c["status"]
                msg = c["msg"]
                source = c["source"]
                
                # If the group is satisfied, report the satisfied criteria within it
                if status == "SATISFIED":
                    matched_criteria.append({
                        "criterion_id": crit.id,
                        "criterion_name": crit.criterion_type,
                        "result": "MATCH",
                        "evidence": msg,
                        "authoritative_source": crit.provenance_reference,
                        "is_mandatory": getattr(crit, "is_mandatory", 1)
                    })
                    if source:
                        org_evidence_refs.append({"type": crit.evidence_fact_type, "value": msg, "source": source})
                elif status == "NOT_SATISFIED":
                    # Only report as unmet if the whole group failed or it's a standalone
                    if grp_status == "NOT_SATISFIED":
                        unmet_criteria.append({
                            "criterion_id": crit.id,
                            "criterion_name": crit.criterion_type,
                            "result": "NO_MATCH",
                            "reason": msg,
                            "authoritative_source": crit.provenance_reference,
                            "is_mandatory": getattr(crit, "is_mandatory", 1)
                        })
                elif status == "UNKNOWN":
                    # Only require review if the group is UNKNOWN
                    if grp_status == "UNKNOWN":
                        missing_information.append({
                            "criterion_id": crit.id,
                            "criterion": crit.criterion_type,
                            "status": "MISSING_EVIDENCE",
                            "required_fact": crit.evidence_fact_type,
                            "question": f"Is condition '{crit.operator} {crit.expected_value}' met for {crit.evidence_fact_type}?",
                            "reason": msg,
                            "is_mandatory": getattr(crit, "is_mandatory", 1),
                            "minimum_evidence_strength": getattr(crit, "minimum_evidence_strength", "DOCUMENTED"),
                            "evidence_required": f"Provide {getattr(crit, 'minimum_evidence_strength', 'DOCUMENTED')} evidence for '{crit.expected_value}'."
                        })

        overall_statuses = list(final_group_statuses.values())
        if not overall_statuses:
            final_status = "NOT_APPLICABLE"
            score = 0.0
            rationale_lines = [f"No criteria defined for {regulation.id}."]
        elif "NOT_SATISFIED" in overall_statuses:
            final_status = "NOT_APPLICABLE"
            score = 0.0
            rationale_lines = [f"Regulation is determined **NOT APPLICABLE** to {profile.organization_name} based on authoritative scope exclusions:"]
            for u in unmet_criteria:
                rationale_lines.append(f"- **{u['criterion_name']}**: {u['reason']}")
        elif "UNKNOWN" in overall_statuses:
            final_status = "REQUIRES_REVIEW"
            score = 0.65 if matched_criteria else 0.40
            rationale_lines = [f"Regulatory applicability **REQUIRES REVIEW** for {profile.organization_name}."]
            if matched_criteria:
                rationale_lines.append("\n**Matched Context:**")
                for m in matched_criteria:
                    rationale_lines.append(f"- {m['criterion_name']}: {m['evidence']}")
            if signal_refs:
                rationale_lines.append("\n**Discovered Regulatory Signals:**")
                for s in signal_refs:
                    rationale_lines.append(f"- Discovered '{s['signal_name']}' on corporate website (Evidence: *\"{s['evidence_quote']}\"*).")
            if missing_information:
                rationale_lines.append("\n**Items Requiring Review:**")
                for m in missing_information:
                    rationale_lines.append(f"- {m['question']} ({m['reason']})")
        else:
            final_status = "APPLICABLE"
            score = 0.95
            rationale_lines = [f"Regulation is determined **APPLICABLE** based on satisfied statutory criteria:"]
            for m in matched_criteria:
                rationale_lines.append(f"- **{m['criterion_name']}**: {m['evidence']}")
                    
        rationale = "\n".join(rationale_lines)

        return cls._persist_assessment(
            profile, regulation, final_status, score, rationale,
            matched_criteria, unmet_criteria, missing_information,
            org_evidence_refs, None, signal_refs, db_session
        )

    @classmethod
    def _persist_assessment(cls, profile: EnterpriseProfile, regulation: Regulation,
                            status: str, score: float, rationale: str,
                            matched: list, unmet: list, missing: list,
                            org_ev: list, reg_ev: list, signals: list, db_session: Session) -> RegulatoryApplicabilityAssessment:
        
        if reg_ev is None:
            reg_ev = [{
                "regulation_id": regulation.id,
                "title": regulation.title,
                "authority": regulation.authority
            }]
            
        existing_items = db_session.query(ApplicabilityReviewItem).filter(
            ApplicabilityReviewItem.organization_id == profile.id,
            ApplicabilityReviewItem.regulation_id == regulation.id,
            ApplicabilityReviewItem.status.in_(["OPEN", "EVIDENCE_REQUESTED", "EVIDENCE_RECEIVED", "UNDER_REVIEW"])
        ).all()
        existing_by_criterion = {item.criterion_id: item for item in existing_items}
        
        assessment = db_session.query(RegulatoryApplicabilityAssessment).filter_by(
            organization_id=profile.id,
            regulation_id=regulation.id
        ).order_by(RegulatoryApplicabilityAssessment.evaluated_at.desc()).first()
        
        if assessment and (
            assessment.status == status and
            assessment.applicability_score == score and
            assessment.matched_criteria == matched and
            assessment.unmet_criteria == unmet and
            assessment.missing_information == missing and
            assessment.regulatory_signal_refs == signals
        ):
            # Idempotent: No material changes, keep the existing snapshot
            pass
        else:
            assessment = RegulatoryApplicabilityAssessment(
                organization_id=profile.id,
                regulation_id=regulation.id,
                status=status,
                applicability_score=score,
                rationale=rationale,
                matched_criteria=matched,
                unmet_criteria=unmet,
                missing_information=missing,
                organization_evidence_refs=org_ev,
                regulatory_evidence_refs=reg_ev,
                regulatory_signal_refs=signals,
                engine_version=ENGINE_VERSION
            )
            db_session.add(assessment)
            
        db_session.flush() 
        
        resolved_criteria_ids = {m["criterion_id"] for m in matched} | {u["criterion_id"] for u in unmet}
        
        for m in missing:
            crit_id = m.get("criterion_id")
            if not crit_id or crit_id == "missing": continue
            if crit_id in existing_by_criterion:
                item = existing_by_criterion[crit_id]
                item.assessment_id = assessment.id
            else:
                new_item = ApplicabilityReviewItem(
                    organization_id=profile.id,
                    regulation_id=regulation.id,
                    assessment_id=assessment.id,
                    criterion_id=crit_id,
                    status="OPEN",
                    question=m["question"],
                    reason=m["reason"],
                    required_fact=m["required_fact"],
                    evidence_required=m.get("evidence_required"),
                    assigned_role="COMPLIANCE_OFFICER"
                )
                db_session.add(new_item)
                
        for crit_id, item in existing_by_criterion.items():
            if crit_id in resolved_criteria_ids:
                item.status = "RESOLVED"
                item.resolved_at = datetime.datetime.utcnow()
                item.resolved_by = "ApplicabilityEngine (Auto-Evaluated)"
                item.assessment_id = assessment.id
        
        return assessment
