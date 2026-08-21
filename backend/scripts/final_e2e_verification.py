import os
import sys
import hashlib
import json
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.main import app
from app.core.database import SessionLocal
from app.models.domain import (
    EnterpriseProfile, DiscoveredFact, Regulation, 
    RegulatoryApplicabilityAssessment, RegulatoryObligation,
    ComplianceTask
)
from app.core.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def hash_table_state(model_class, org_id=None):
    query = db.query(model_class)
    if hasattr(model_class, 'organization_id') and org_id:
        query = query.filter(model_class.organization_id == org_id)
    records = query.all()
    
    # Simple deterministic serialization
    data = []
    for r in records:
        r_dict = {k: str(v) for k, v in r.__dict__.items() if not k.startswith('_')}
        data.append(r_dict)
    
    data.sort(key=lambda x: str(x.get('id', '')))
    encoded = json.dumps(data, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def get_upstream_hashes(org_id):
    return {
        "EnterpriseProfile": hash_table_state(EnterpriseProfile, org_id),
        "DiscoveredFact": hash_table_state(DiscoveredFact, org_id),
        "Regulation": hash_table_state(Regulation),
        "RegulatoryApplicabilityAssessment": hash_table_state(RegulatoryApplicabilityAssessment, org_id),
        "RegulatoryObligation": hash_table_state(RegulatoryObligation, org_id)
    }

def run_e2e_pipeline():
    # Setup test user token
    token = create_access_token({"sub": "compliance.officer@enterprise.com", "role": "Compliance Officer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Setup isolated test organization
    profile = EnterpriseProfile(
        id="test-org-e2e-1234",
        organization_name="Test Org E2E",
        discovery_status="UNINITIALIZED",
        industry_sector="Technology",
        country="India"
    )
    # Clear old
    db.query(EnterpriseProfile).filter(EnterpriseProfile.id == "test-org-e2e-1234").delete()
    db.add(profile)
    db.commit()

    print("Phase 7 & 8: FINAL E2E PIPELINE & UPSTREAM IMMUTABILITY VERIFICATION")
    print("==================================================================")

    # Note: Because the actual pipeline endpoints are mocked or need external LLMs, 
    # we simulate the pipeline completion by manually triggering the internal service classes
    # or making the API requests.

    # 1. Discovery
    print("STEP 1: Discovery")
    resp = client.post("/api/v1/discovery/start", json={"url": "https://in.nec.com"}, headers=headers)
    
    # Let's bypass LLM calls by directly seeding the profile if needed for tests.
    profile.discovery_status = "CONFIRMED"
    profile.country = "India"
    profile.industry_sector = "Technology"
    db.commit()

    # Seed an applicable regulation and obligation
    from app.services.applicability_engine import ApplicabilityEngine
    from app.services.obligation_engine import ObligationEngine
    from app.services.task_engine import TaskEngine
    
    print("STEP 2 & 3: Applicability")
    ApplicabilityEngine.evaluate_organization(profile.id, db)
    
    print("STEP 4: Obligations")
    ObligationEngine.generate_obligations(profile.id, db)
    
    print("STEP 5: Tasks")
    TaskEngine.generate_tasks(profile.id, db)
    
    # ---------------------------------------------------------
    # CAPTURE HASHES BEFORE OPERATIONAL ACTIVITIES (PHASE 8)
    # ---------------------------------------------------------
    print("\n--- CAPTURING UPSTREAM HASHES BEFORE EXECUTION ---")
    hashes_before = get_upstream_hashes(profile.id)
    for k, v in hashes_before.items():
        print(f"{k}: {v[:16]}...")
        
    print("\nSTEP 6: Execution")
    # Transition a task
    task = db.query(ComplianceTask).filter(ComplianceTask.organization_id == profile.id).first()
    if task:
        print(f"Executing task {task.id}")
        resp = client.post(f"/api/v1/compliance/tasks/{task.id}/status", json={"status": "IN_PROGRESS", "notes": "E2E start"}, headers=headers)
        assert resp.status_code == 200, resp.text
        resp = client.post(f"/api/v1/compliance/tasks/{task.id}/status", json={"status": "COMPLETED", "notes": "E2E done"}, headers=headers)
        assert resp.status_code == 200, resp.text

    print("STEP 7: Evidence")
    if task:
        resp = client.post(f"/api/v1/compliance/tasks/{task.id}/evidence", json={
            "title": "E2E Evidence",
            "description": "Proof",
            "source_url": "https://example.com"
        }, headers=headers)
        assert resp.status_code == 200, resp.text

    print("STEP 8: Trigger")
    from app.models.domain import ComplianceTriggerEvent
    event = ComplianceTriggerEvent(
        organization_id=profile.id,
        event_type="INCIDENT_DETECTED",
        description="E2E Incident",
        source="SYSTEM",
        created_by="E2E Script",
        event_timestamp=datetime.utcnow()
    )
    db.add(event)
    db.commit()

    print("STEP 9: Monitoring & Alerts")
    from app.services.compliance_alert_service import ComplianceAlertService
    ComplianceAlertService.evaluate_and_sync_alerts(profile.id, db)

    print("STEP 10 & 11: Intelligence Snapshot & Defense Pack")
    from app.services.compliance_intelligence_service import ComplianceIntelligenceService
    from app.services.defense_pack_service import DefensePackService
    
    snapshot = ComplianceIntelligenceService.generate_snapshot(profile.id, db)
    dp1 = DefensePackService.generate_defense_pack(snapshot.id, profile.id, db)
    dp2 = DefensePackService.generate_defense_pack(snapshot.id, profile.id, db)
    
    print(f"DP 1 Hash: {dp1.content_hash}")
    print(f"DP 2 Hash: {dp2.content_hash}")
    assert dp1.content_hash == dp2.content_hash, "Defense pack hash determinism failed!"
    print("[PASS] Defense Pack Hash Determinism Verified!")

    print("STEP 12: Tenant Isolation")
    # Try accessing with another user
    token2 = create_access_token({"sub": "other@enterprise.com", "role": "Compliance Officer"})
    headers2 = {"Authorization": f"Bearer {token2}"}
    if task:
        resp = client.post(f"/api/v1/compliance/tasks/{task.id}/status", json={"status": "OPEN", "notes": "hacked"}, headers=headers2)
        assert resp.status_code in [403, 404], "Tenant isolation failed!"
    print("[PASS] Tenant Isolation Verified!")

    # ---------------------------------------------------------
    # CAPTURE HASHES AFTER OPERATIONAL ACTIVITIES (PHASE 8)
    # ---------------------------------------------------------
    print("\n--- CAPTURING UPSTREAM HASHES AFTER EXECUTION ---")
    hashes_after = get_upstream_hashes(profile.id)
    
    mismatch = False
    for k in hashes_before:
        if hashes_before[k] != hashes_after[k]:
            print(f"[FAIL] IMMUTABILITY BREACHED IN {k}!")
            mismatch = True
            
    if not mismatch:
        print("[PASS] Upstream Immutability Verified! Zero mutations detected.")

    if not mismatch and dp1.content_hash == dp2.content_hash:
        print("\n[PASS] FINAL E2E PIPELINE SUCCESSFUL.")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(run_e2e_pipeline())
