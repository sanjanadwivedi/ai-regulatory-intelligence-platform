import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.core.database import SessionLocal
from app.models.domain import (
    EnterpriseProfile,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    AuditLog
)
from app.services.applicability_engine import ApplicabilityEngine
from app.services.obligation_engine import ObligationEngine

db = SessionLocal()
profile = db.query(EnterpriseProfile).first()
if not profile:
    profile = EnterpriseProfile(
        organization_name='NEC India',
        country='India',
        locations=['India', 'Mumbai', 'Noida'],
        business_activities=['ICT & Digital Transformation Solutions', 'Cloud & Technology Infrastructure', 'Digital Identity & Biometrics'],
        discovery_status='CONFIRMED'
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

print(f"=== 1. EVALUATING APPLICABILITY FOR {profile.organization_name} ===")
assessments = ApplicabilityEngine.evaluate_organization(profile.id, db)
print(f"Total Regulations Evaluated: {len(assessments)}")

applicable_assessments = [a for a in assessments if a.status == "APPLICABLE"]
not_applicable_assessments = [a for a in assessments if a.status == "NOT_APPLICABLE"]
requires_review_assessments = [a for a in assessments if a.status == "REQUIRES_REVIEW"]

print(f"  - APPLICABLE: {len(applicable_assessments)}")
print(f"  - NOT_APPLICABLE: {len(not_applicable_assessments)}")
print(f"  - REQUIRES_REVIEW: {len(requires_review_assessments)}")

print(f"\n=== 2. GENERATING REGULATORY OBLIGATIONS (IDEMPOTENT RUN 1) ===")
obligations_run_1 = ObligationEngine.generate_obligations(profile.id, db)
print(f"Obligations Generated (Run 1): {len(obligations_run_1)}")

active_obs = [o for o in obligations_run_1 if o.status == "ACTIVE"]
review_obs = [o for o in obligations_run_1 if o.status == "REQUIRES_REVIEW"]
superseded_obs = [o for o in obligations_run_1 if o.status == "SUPERSEDED"]

print(f"  - ACTIVE Obligations: {len(active_obs)}")
print(f"  - REQUIRES_REVIEW Obligations: {len(review_obs)}")
print(f"  - SUPERSEDED Obligations: {len(superseded_obs)}")

print(f"\n=== 3. GENERATING REGULATORY OBLIGATIONS (IDEMPOTENT RUN 2) ===")
obligations_run_2 = ObligationEngine.generate_obligations(profile.id, db)
db_active_count = db.query(RegulatoryObligation).filter(
    RegulatoryObligation.organization_id == profile.id,
    RegulatoryObligation.status == "ACTIVE"
).count()
print(f"Obligations Generated (Run 2): {len(obligations_run_2)}")
print(f"Database Active Obligation Count: {db_active_count}")
assert len(obligations_run_1) == len(obligations_run_2) == db_active_count, "Idempotency invariant violated!"
print(">>> IDEMPOTENCY VERIFIED: Exact match, no duplicates created.")

print(f"\n=== 4. REGULATION-BY-REGULATION BOUNDARY AUDIT ===")
for a in assessments:
    reg = a.regulation
    obs_for_reg = [o for o in obligations_run_2 if o.regulation_id == reg.id]
    active_for_reg = [o for o in obs_for_reg if o.status == "ACTIVE"]
    print("-" * 80)
    print(f"Regulation: {reg.title}")
    print(f"  Authority: {reg.authority}")
    print(f"  Applicability Status: {a.status}")
    print(f"  Total Obligations: {len(obs_for_reg)} (ACTIVE: {len(active_for_reg)})")
    
    if a.status == "APPLICABLE":
        for o in active_for_reg:
            print(f"    * [{o.obligation_code}] {o.title}")
            print(f"      Type: {o.obligation_type} | Priority: {o.priority} | Freq: {o.frequency}")
            print(f"      Due Rule: {o.due_rule}")
            print(f"      Citation: {o.source_citation}")
            print(f"      Source URL: {o.authoritative_source_url}")
    elif a.status == "NOT_APPLICABLE":
        assert len(obs_for_reg) == 0, f"NOT_APPLICABLE regulation {reg.id} generated obligations!"
        print("    -> ZERO obligations generated (Correctly excluded)")
    elif a.status == "REQUIRES_REVIEW":
        assert len(active_for_reg) == 0, f"REQUIRES_REVIEW regulation {reg.id} generated ACTIVE obligations!"
        print(f"    -> ZERO ACTIVE obligations generated (Requires human review: {a.missing_information})")

print(f"\n=== 5. IMMUTABLE AUDIT LOG VERIFICATION ===")
latest_audit = db.query(AuditLog).filter(AuditLog.action == "OBLIGATIONS_GENERATED").order_by(AuditLog.created_at.desc()).first()
if latest_audit:
    print(f"Action: {latest_audit.action}")
    print(f"User: {latest_audit.user_name} ({latest_audit.user_role})")
    print(f"Target: {latest_audit.target_type} ({latest_audit.target_id})")
    print(f"Details: {latest_audit.details}")
    print(f"Timestamp: {latest_audit.created_at}")

db.close()
