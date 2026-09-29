import sys
import os
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.models.domain import EnterpriseProfile, EnterpriseUser, RegulatoryChange, RegulatoryChangeTenantReview
from app.core.security import get_current_user
from sqlalchemy.orm import Session

def run_validation():
    print("Starting Phase 21B API Validation...\n")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Setup multi-tenant context
    org_a_id = "test-org-a-" + str(uuid.uuid4())[:8]
    org_b_id = "test-org-b-" + str(uuid.uuid4())[:8]
    
    org_a = EnterpriseProfile(id=org_a_id, organization_name="Org A Valid", industry_sector="Finance")
    org_b = EnterpriseProfile(id=org_b_id, organization_name="Org B Valid", industry_sector="Tech")
    db.add(org_a)
    db.add(org_b)
    
    user_a = EnterpriseUser(id="user_a", organization_id=org_a_id, full_name="User A", role="ADMIN")
    user_b = EnterpriseUser(id="user_b", organization_id=org_b_id, full_name="User B", role="ADMIN")
    db.commit()
    
    client = TestClient(app)
    
    try:
        # Authenticate as Org A
        app.dependency_overrides[get_current_user] = lambda: user_a
        print("--- Authenticated as Org A ---")
        
        # 2. Summary
        resp = client.get("/api/v1/regulatory-intelligence/summary")
        assert resp.status_code == 200, f"Summary failed: {resp.text}"
        summary = resp.json()
        print(f"Summary OK: {summary}")
        
        # 3. Change feed
        resp = client.get("/api/v1/regulatory-intelligence/changes")
        assert resp.status_code == 200, f"Feed failed: {resp.text}"
        feed = resp.json()
        print(f"Feed OK, total changes: {feed.get('total')}")
        
        if feed["total"] == 0:
            print("No regulatory changes found to test with. Creating one.")
            from app.models.domain import Regulation, DocumentVersion
            import datetime
            reg = db.query(Regulation).filter_by(id="dummy-reg").first()
            if not reg:
                reg = Regulation(
                    id="dummy-reg", 
                    title="Dummy Reg", 
                    authority="Dummy Auth",
                    publication_date=datetime.date.today(),
                    sector="Finance",
                    region="Global",
                    content_text="dummy text"
                )
                db.add(reg)
            
            doc_version = DocumentVersion(
                id=str(uuid.uuid4()),
                regulation_id="dummy-reg",
                version_no=1,
                content_hash=str(uuid.uuid4()),
                content_text="dummy text",
                source_url="http://dummy"
            )
            db.add(doc_version)
            db.commit()

            change = RegulatoryChange(
                id=str(uuid.uuid4()),
                regulation_id="dummy-reg",
                new_version_id=doc_version.id,
                change_type="NEW_REGULATION",
                detected_at=datetime.datetime.utcnow(),
                detected_by="test",
                content_hash_after="xyz"
            )
            db.add(change)
            db.commit()
            change_id = change.id
        else:
            change_id = feed["items"][0]["change_id"]
            
        # 5. Detail
        resp = client.get(f"/api/v1/regulatory-intelligence/changes/{change_id}")
        assert resp.status_code == 200, f"Detail failed: {resp.text}"
        detail_a = resp.json()
        print(f"Detail OK for {change_id}, status: {detail_a['review_status']}")
        
        # 7. Acknowledge
        print("Submitting ACKNOWLEDGE...")
        resp = client.post(f"/api/v1/regulatory-intelligence/changes/{change_id}/review", json={"decision": "ACKNOWLEDGE", "review_notes": "test"})
        assert resp.status_code == 200, f"Review failed: {resp.text}"
        
        # 8. Retrieve detail again
        resp = client.get(f"/api/v1/regulatory-intelligence/changes/{change_id}")
        detail_a2 = resp.json()
        print(f"Detail after ACKNOWLEDGE, status: {detail_a2['review_status']}")
        assert detail_a2['review_status'] in ["ACKNOWLEDGED", "REVIEWED"], f"State did not change correctly: {detail_a2['review_status']}"
        
        # 10. Idempotent check
        resp = client.post(f"/api/v1/regulatory-intelligence/changes/{change_id}/review", json={"decision": "ACKNOWLEDGE", "review_notes": "test 2"})
        assert resp.status_code == 200, "Idempotent request failed"
        
        # 11. Resolve
        resp = client.post(f"/api/v1/regulatory-intelligence/changes/{change_id}/review", json={"decision": "RESOLVE", "review_notes": "done"})
        assert resp.status_code == 200, f"Resolve failed: {resp.text}"
        
        resp = client.get(f"/api/v1/regulatory-intelligence/changes/{change_id}")
        detail_a3 = resp.json()
        assert detail_a3['review_status'] == "RESOLVED", "State did not change to RESOLVED"
        print("Resolve OK.")
        
        # Tenant Isolation Check
        print("\n--- Authenticated as Org B ---")
        app.dependency_overrides[get_current_user] = lambda: user_b
        
        resp = client.get(f"/api/v1/regulatory-intelligence/changes/{change_id}")
        assert resp.status_code == 200
        detail_b = resp.json()
        
        print(f"Org B sees review status for the same change as: {detail_b['review_status']}")
        assert detail_b['review_status'] == "REQUIRES_REVIEW", "Org B leaked Org A's review state!"
        
        print("\nSUCCESS: All Phase 21B API endpoints validated securely with tenant isolation.")
        return 0
    except Exception as e:
        print(f"\nERROR: {e}")
        return 1
    finally:
        app.dependency_overrides.clear()
        db.close()

if __name__ == "__main__":
    sys.exit(run_validation())
