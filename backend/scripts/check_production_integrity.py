import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.domain import (
    InternalControl,
    ObligationControlMapping,
    ComplianceTask,
    ComplianceTaskEvidence,
    RegulatoryObligation,
    RegulatoryApplicabilityAssessment,
    Regulation,
    EnterpriseProfile,
    DocumentVersion,
    RegulatoryChange,
    DiscoveredFact,
    RegulatoryChangeTenantReview
)

def run_integrity_checks(db: Session) -> int:
    violations = 0

    print("Running production integrity checks...\n")

    # 1. Orphan InternalControls (must have organization_id)
    orphan_controls = db.query(InternalControl).filter(InternalControl.organization_id == None).count()
    if orphan_controls > 0:
        print(f"[VIOLATION] Found {orphan_controls} orphan InternalControls (missing organization_id)")
        violations += orphan_controls

    # 2. Orphan ObligationControlMapping (must point to valid obligation and control)
    orphan_mappings_ctrl = db.query(ObligationControlMapping).outerjoin(InternalControl).filter(InternalControl.id == None).count()
    if orphan_mappings_ctrl > 0:
        print(f"[VIOLATION] Found {orphan_mappings_ctrl} ObligationControlMapping pointing to missing control")
        violations += orphan_mappings_ctrl

    orphan_mappings_obl = db.query(ObligationControlMapping).outerjoin(RegulatoryObligation).filter(RegulatoryObligation.id == None).count()
    if orphan_mappings_obl > 0:
        print(f"[VIOLATION] Found {orphan_mappings_obl} ObligationControlMapping pointing to missing obligation")
        violations += orphan_mappings_obl

    # 3. Orphan ComplianceTasks (must point to organization)
    orphan_tasks = db.query(ComplianceTask).filter(ComplianceTask.organization_id == None).count()
    if orphan_tasks > 0:
        print(f"[VIOLATION] Found {orphan_tasks} orphan ComplianceTasks (missing organization_id)")
        violations += orphan_tasks

    # 4. Cross-tenant ComplianceTask/control relationships
    cross_tenant_tasks = db.query(ComplianceTask, InternalControl).join(
        InternalControl, ComplianceTask.control_id == InternalControl.id
    ).filter(ComplianceTask.organization_id != InternalControl.organization_id).count()
    if cross_tenant_tasks > 0:
        print(f"[VIOLATION] Found {cross_tenant_tasks} cross-tenant ComplianceTask/InternalControl relationships")
        violations += cross_tenant_tasks

    # 5. Cross-tenant obligation/control relationships
    cross_tenant_mappings = db.query(ObligationControlMapping, RegulatoryObligation, InternalControl).join(
        RegulatoryObligation, ObligationControlMapping.obligation_id == RegulatoryObligation.id
    ).join(
        InternalControl, ObligationControlMapping.control_id == InternalControl.id
    ).filter(RegulatoryObligation.organization_id != InternalControl.organization_id).count()
    if cross_tenant_mappings > 0:
        print(f"[VIOLATION] Found {cross_tenant_mappings} cross-tenant obligation/control mappings")
        violations += cross_tenant_mappings

    # 6. Cross-tenant evidence/task relationships
    cross_tenant_evidence = db.query(ComplianceTaskEvidence, ComplianceTask).join(
        ComplianceTask, ComplianceTaskEvidence.task_id == ComplianceTask.id
    ).filter(ComplianceTaskEvidence.organization_id != ComplianceTask.organization_id).count()
    if cross_tenant_evidence > 0:
        print(f"[VIOLATION] Found {cross_tenant_evidence} cross-tenant evidence/task relationships")
        violations += cross_tenant_evidence

    # 7. Regulation -> applicability -> obligation consistency
    # Obligation must match regulation of the assessment
    inconsistent_obs = db.query(RegulatoryObligation, RegulatoryApplicabilityAssessment).join(
        RegulatoryApplicabilityAssessment, RegulatoryObligation.applicability_assessment_id == RegulatoryApplicabilityAssessment.id
    ).filter(RegulatoryObligation.regulation_id != RegulatoryApplicabilityAssessment.regulation_id).count()
    if inconsistent_obs > 0:
        print(f"[VIOLATION] Found {inconsistent_obs} Obligations inconsistent with Assessment's Regulation")
        violations += inconsistent_obs

    # 8. Organization/tenant ownership boundaries (Basic checks on assessments)
    cross_tenant_assessments = db.query(RegulatoryApplicabilityAssessment, RegulatoryObligation).join(
        RegulatoryObligation, RegulatoryApplicabilityAssessment.id == RegulatoryObligation.applicability_assessment_id
    ).filter(RegulatoryApplicabilityAssessment.organization_id != RegulatoryObligation.organization_id).count()
    if cross_tenant_assessments > 0:
        print(f"[VIOLATION] Found {cross_tenant_assessments} cross-tenant Assessment/Obligation relationships")
        violations += cross_tenant_assessments

    # 9. No orphaned regulatory change/version records
    orphan_doc_versions = db.query(DocumentVersion).filter(DocumentVersion.regulation_id == None).count()
    if orphan_doc_versions > 0:
        print(f"[VIOLATION] Found {orphan_doc_versions} orphaned DocumentVersion records")
        violations += orphan_doc_versions

    orphan_reg_changes = db.query(RegulatoryChange).filter(RegulatoryChange.regulation_id == None).count()
    if orphan_reg_changes > 0:
        print(f"[VIOLATION] Found {orphan_reg_changes} orphaned RegulatoryChange records")
        violations += orphan_reg_changes

    # 10. No duplicate organization facts after Phase 19.1
    facts = db.query(DiscoveredFact).all()
    fact_set = set()
    duplicate_facts = 0
    for fact in facts:
        key = (fact.organization_id, fact.fact_type, fact.fact_value)
        if key in fact_set:
            duplicate_facts += 1
        fact_set.add(key)
    
    if duplicate_facts > 0:
        print(f"[VIOLATION] Found {duplicate_facts} duplicate semantic facts")
        violations += duplicate_facts

    # 11. No duplicate regulatory versions/change records after Phase 20
    versions = db.query(DocumentVersion).all()
    version_set = set()
    duplicate_versions = 0
    for v in versions:
        key = (v.regulation_id, v.version_number)
        if key in version_set:
            duplicate_versions += 1
        version_set.add(key)
    
    if duplicate_versions > 0:
        print(f"[VIOLATION] Found {duplicate_versions} duplicate regulatory versions")
        violations += duplicate_versions
        
    # Historical tasks (ensure none were accidentally deleted if they had evidence)
    orphan_evidence = db.query(ComplianceTaskEvidence).outerjoin(ComplianceTask).filter(ComplianceTask.id == None).count()
    if orphan_evidence > 0:
        print(f"[VIOLATION] Found {orphan_evidence} orphan Evidence records (task missing)")
        violations += orphan_evidence

    # Phase 21A: RegulatoryChangeTenantReview integrity
    orphan_reviews = db.query(RegulatoryChangeTenantReview).filter(
        (RegulatoryChangeTenantReview.organization_id == None) | (RegulatoryChangeTenantReview.change_id == None)
    ).count()
    if orphan_reviews > 0:
        print(f"[VIOLATION] Found {orphan_reviews} orphan RegulatoryChangeTenantReview records")
        violations += orphan_reviews
        
    invalid_org_reviews = db.query(RegulatoryChangeTenantReview).outerjoin(EnterpriseProfile).filter(EnterpriseProfile.id == None).count()
    if invalid_org_reviews > 0:
        print(f"[VIOLATION] Found {invalid_org_reviews} RegulatoryChangeTenantReview with invalid organization_id")
        violations += invalid_org_reviews
        
    invalid_change_reviews = db.query(RegulatoryChangeTenantReview).outerjoin(RegulatoryChange).filter(RegulatoryChange.id == None).count()
    if invalid_change_reviews > 0:
        print(f"[VIOLATION] Found {invalid_change_reviews} RegulatoryChangeTenantReview with invalid change_id")
        violations += invalid_change_reviews
        
    reviews = db.query(RegulatoryChangeTenantReview).all()
    review_set = set()
    duplicate_reviews = 0
    for r in reviews:
        key = (r.organization_id, r.change_id)
        if key in review_set:
            duplicate_reviews += 1
        review_set.add(key)
    
    if duplicate_reviews > 0:
        print(f"[VIOLATION] Found {duplicate_reviews} duplicate RegulatoryChangeTenantReview records")
        violations += duplicate_reviews

    if violations == 0:
        print("PASS")
        print("0 orphan records")
        print("0 cross-tenant violations")
        print("0 duplicate semantic facts")
        print("0 regulatory-version inconsistencies")
        print("0 broken hierarchy relationships")
        return 0
    else:
        print(f"\nFAILED: {violations} total integrity violations found.")
        return 1

if __name__ == "__main__":
    db = SessionLocal()
    try:
        sys.exit(run_integrity_checks(db))
    finally:
        db.close()
