import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.core.database import SessionLocal
from app.models.domain import EnterpriseProfile, RegulatoryApplicabilityAssessment
from app.services.applicability_engine import ApplicabilityEngine

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

assessments = ApplicabilityEngine.evaluate_organization(profile.id, db)
print(f'EVALUATED {len(assessments)} REGULATIONS FOR {profile.organization_name}\n')

for a in assessments:
    reg = a.regulation
    print('=' * 80)
    print(f'REGULATION: {reg.title}')
    print(f'AUTHORITY: {reg.authority}')
    print(f'STATUS: {a.status}')
    print(f'SCORE: {a.applicability_score}')
    print(f'MATCHED CRITERIA ({len(a.matched_criteria or [])}):')
    for m in (a.matched_criteria or []):
        print(f'  [MATCH] {m.get("criterion_name")}: {m.get("evidence")}')
    print(f'UNMET CRITERIA ({len(a.unmet_criteria or [])}):')
    for u in (a.unmet_criteria or []):
        print(f'  [NO_MATCH] {u.get("criterion_name")}: {u.get("reason")}')
    print(f'MISSING INFO ({len(a.missing_information or [])}):')
    for mi in (a.missing_information or []):
        print(f'  [MISSING] {mi}')
    print(f'ORGANIZATION EVIDENCE REFS: {a.organization_evidence_refs}')
    print(f'REGULATORY EVIDENCE REFS: {a.regulatory_evidence_refs}')
    print(f'REGULATORY SIGNAL REFS: {a.regulatory_signal_refs}')
    print(f'RATIONALE:\n{a.rationale}\n')

db.close()
