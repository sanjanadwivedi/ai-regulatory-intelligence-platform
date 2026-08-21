import datetime
from sqlalchemy.orm import Session
from app.models.domain import ApplicabilityReviewItem, DiscoveredFact
from app.services.applicability_engine import ApplicabilityEngine

class ReviewService:
    @classmethod
    def resolve_applicability_review(
        cls, db: Session, item_id: str, organization_id: str, user_id: str, user_role: str,
        evidence_fact_value: str, evidence_type: str, evidence_strength: str, 
        source_url: str, snippet: str = "", known_state: str = "TRUE"
    ):
        # 1. Load review item
        item = db.query(ApplicabilityReviewItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Review item {item_id} not found.")

        # 2. Verify tenant
        if item.organization_id != organization_id:
            raise PermissionError("Tenant isolation violation: organization mismatch.")

        # 3. Verify RBAC
        if user_role not in ["COMPLIANCE_OFFICER", "ADMIN"]:
            raise PermissionError(f"User role {user_role} not authorized for human review.")

        # 4. Verify open status
        if item.status not in ["OPEN", "EVIDENCE_REQUESTED", "UNDER_REVIEW"]:
            raise ValueError(f"Review item {item_id} is already {item.status}.")

        # 5. Create the structured DiscoveredFact (tenant isolated)
        fact = DiscoveredFact(
            organization_id=organization_id,
            fact_type=item.required_fact,
            fact_value=evidence_fact_value,
            known_state=known_state,
            source_url=source_url,
            snippet=snippet,
            evidence_type=evidence_type,
            evidence_strength=evidence_strength,
            extraction_method="USER_PROVIDED",
            confidence=1.0, # Human provided
            status="CONFIRMED"
        )
        db.add(fact)
        db.flush()

        # 6. Re-run ApplicabilityEngine for the organization
        # This will create a NEW RegulatoryApplicabilityAssessment, 
        # and idempotently update or resolve ApplicabilityReviewItems.
        assessments = ApplicabilityEngine.evaluate_organization(organization_id, db)

        # 7. Check if the engine resolved our specific item
        db.refresh(item)
        if item.status == "RESOLVED":
            item.resolved_by = user_id
            item.resolution_evidence_reference = source_url
            db.commit()
            return {"status": "RESOLVED", "assessment_id": item.assessment_id, "message": "Criterion satisfied and review item resolved."}
        else:
            item.status = "UNDER_REVIEW" # Updated from OPEN since we submitted evidence, but it wasn't enough
            db.commit()
            return {"status": "UNDER_REVIEW", "assessment_id": item.assessment_id, "message": "Evidence submitted but criterion remains UNKNOWN (insufficient strength or missing)."}
