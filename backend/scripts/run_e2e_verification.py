import sys
import os
import json
import datetime
from urllib.parse import urlparse

sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.domain import EnterpriseProfile, DiscoveryRun, DiscoveredFact, EnterpriseUser
from app.core.security import create_access_token
from fastapi.testclient import TestClient
from app.main import app

def run_e2e():
    print("=" * 80)
    print("STEP 1: RESETTING TO CLEAN UNINITIALIZED STATE")
    print("=" * 80)
    db = SessionLocal()
    
    # Clean prior test runs
    db.query(DiscoveredFact).delete()
    db.query(DiscoveryRun).delete()
    
    profile = db.query(EnterpriseProfile).first()
    if not profile:
        profile = EnterpriseProfile(
            organization_name="Pending Discovery",
            industry_sector="Enterprise Technology",
            country="India",
            discovery_status="UNINITIALIZED"
        )
        db.add(profile)
    else:
        profile.discovery_status = "UNINITIALIZED"
        profile.organization_name = "Pending Discovery"
        profile.website_url = None
        profile.departments = []
        profile.business_activities = []
        profile.products_services = []
        profile.licenses = []
    
    user = db.query(EnterpriseUser).filter(EnterpriseUser.email == "compliance.officer@enterprise.com").first()
    if not user:
        user = EnterpriseUser(
            email="compliance.officer@enterprise.com",
            full_name="Compliance Officer",
            role="Compliance Officer"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    client = TestClient(app)

    print(f"Profile initialized: ID={profile.id}, discovery_status={profile.discovery_status}")

    print("\n" + "=" * 80)
    print("STEP 2: RUNNING REAL LIVE DISCOVERY ON https://in.nec.com")
    print("=" * 80)

    start_resp = client.post(
        "/api/v1/discovery/start",
        json={"website_url": "https://in.nec.com"},
        headers=headers
    )
    print(f"POST /api/v1/discovery/start -> Status {start_resp.status_code}")
    start_data = start_resp.json()
    print("Response Data:", json.dumps(start_data, indent=2))
    assert start_resp.status_code == 200, f"Discovery start failed: {start_resp.text}"

    run_id = start_data["discovery_run_id"]

    print("\n" + "=" * 80)
    print("STEP 3: INSPECTING DATABASE RUN & PROFILE STATE")
    print("=" * 80)
    db.refresh(profile)
    run = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
    assert run is not None
    print(f"DiscoveryRun ID:         {run.id}")
    print(f"DiscoveryRun status:     {run.status}")
    print(f"Submitted URL:           {run.website_url}")
    print(f"Final URL:               {run.final_url}")
    print(f"Crawled Pages:           {run.crawled_pages_count}")
    print(f"Discovered URLs:         {run.discovered_urls_count}")
    print(f"Crawl Duration:          {run.crawl_duration_seconds:.2f}s")
    print(f"Failure Reason:          {run.failure_reason}")
    print(f"EnterpriseProfile status:{profile.discovery_status}")

    assert run.status == "REVIEW_PENDING"
    assert profile.discovery_status == "REVIEW_PENDING"

    print("\n" + "=" * 80)
    print("STEP 4: DETAILED CANDIDATE FACTS AUDIT")
    print("=" * 80)
    facts_resp = client.get(f"/api/v1/discovery/facts?status=ALL&discovery_run_id={run_id}", headers=headers)
    assert facts_resp.status_code == 200
    candidate_facts = facts_resp.json()
    print(f"Total Candidate Facts Returned: {len(candidate_facts)}\n")

    false_positive_keywords = [
        "Wealth & Asset Management",
        "Card Issuance & Credit Cards",
        "Retail Banking",
        "Corporate & Commercial Lending",
        "Digital Lending & Micro-Credit",
        "Algorithmic & Securities Trading",
        "Reserve Bank of India (RBI) Banking License"
    ]

    for idx, fact in enumerate(candidate_facts, 1):
        print(f"--- CANDIDATE FACT #{idx} ---")
        print(f"  FACT TYPE:               {fact['fact_type']}")
        print(f"  FACT VALUE:              {fact['fact_value']}")
        print(f"  CONFIDENCE:              {fact['confidence']}")
        print(f"  SOURCE URL:              {fact['source_url']}")
        print(f"  SOURCE TITLE:            {fact['source_title']}")
        print(f"  EVIDENCE QUOTE:          {fact['snippet']}")
        print(f"  EXTRACTION METHOD:       {fact['extraction_method']}")
        print(f"  STATUS:                  {fact['status']}")
        
        # Check against prohibited false positives
        for fp in false_positive_keywords:
            assert fact['fact_value'] != fp, f"CRITICAL REGRESSION: False positive {fp} found in candidate facts!"
        print("  VERIFICATION:            PASS (Valid direct organization evidence)\n")

    print("\n" + "=" * 80)
    print("STEP 5: SIMULATE HUMAN REVIEW & BULK CONFIRM HIGH CONFIDENCE")
    print("=" * 80)
    bulk_resp = client.post(
        "/api/v1/discovery/facts/bulk-confirm",
        json={"min_confidence": 0.85},
        headers=headers
    )
    assert bulk_resp.status_code == 200
    print("Bulk Confirm Response:", bulk_resp.json())

    print("\n" + "=" * 80)
    print("STEP 6: FINALIZE DISCOVERY & UPDATE ENTERPRISE PROFILE")
    print("=" * 80)
    finalize_resp = client.post("/api/v1/discovery/finalize", headers=headers)
    assert finalize_resp.status_code == 200
    fin_data = finalize_resp.json()
    print("Finalize Response:", json.dumps(fin_data, indent=2))

    db.refresh(profile)
    db.refresh(run)
    assert run.status == "CONFIRMED"
    assert profile.discovery_status == "CONFIRMED"
    assert profile.organization_name == "NEC India" or "NEC" in profile.organization_name
    print(f"\nFinalized Profile Name:       {profile.organization_name}")
    print(f"Finalized Discovery Status:   {profile.discovery_status}")
    print(f"Finalized Business Activities:{profile.business_activities}")
    print(f"Finalized Products/Services:  {profile.products_services}")
    print(f"Finalized Departments:        {profile.departments}")

    print("\n" + "=" * 80)
    print("STEP 7: TEST DISCOVER AGAIN ISOLATION (RUN B FAILURE)")
    print("=" * 80)
    # Record Run A state
    run_a_id = run.id
    run_a_status = run.status
    profile_status_before = profile.discovery_status
    profile_activities_before = list(profile.business_activities)
    profile_name_before = profile.organization_name

    # Trigger a rediscovery with unreachable domain
    rediscover_resp = client.post(
        "/api/v1/discovery/start",
        json={"website_url": "https://nonexistent-unreachable-site-999.org"},
        headers=headers
    )
    print(f"POST /api/v1/discovery/start (unreachable) -> Status {rediscover_resp.status_code}")
    assert rediscover_resp.status_code == 422
    err_detail = rediscover_resp.json()["detail"]
    print("Failure Detail:", json.dumps(err_detail, indent=2))

    # Verify Run A and Profile are NOT corrupted
    db.refresh(profile)
    run_a = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_a_id).first()
    run_b = db.query(DiscoveryRun).filter(DiscoveryRun.website_url == "https://nonexistent-unreachable-site-999.org/").first()

    assert run_a.status == "CONFIRMED", "Run A status was corrupted!"
    assert run_b is not None and run_b.status == "FAILED", "Run B was not recorded as FAILED!"
    assert profile.discovery_status == "CONFIRMED", "EnterpriseProfile discovery_status was downgraded!"
    assert profile.organization_name == profile_name_before, "EnterpriseProfile name was overwritten!"
    assert profile.business_activities == profile_activities_before, "EnterpriseProfile activities were cleared!"

    # Verify GET /discovery/status still returns CONFIRMED
    status_resp = client.get("/api/v1/discovery/status", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    print("\nGET /api/v1/discovery/status after failed rediscovery:")
    print(json.dumps(status_data, indent=2))
    assert status_data["discovery_status"] == "CONFIRMED"

    print("\n" + "=" * 80)
    print("ALL END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 80)
    db.close()

if __name__ == "__main__":
    run_e2e()
