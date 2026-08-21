import sys
import os
sys.path.insert(0, os.path.abspath("."))

import json
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.domain import EnterpriseUser, EnterpriseProfile, DiscoveryRun, DiscoveredFact
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

db = SessionLocal()
u = db.query(EnterpriseUser).first()
if not u:
    u = EnterpriseUser(full_name="Compliance Officer", role="Compliance Officer")
    db.add(u)
    db.commit()
    db.refresh(u)
token = create_access_token(u.id)
headers = {"Authorization": f"Bearer {token}"}

print("\n" + "="*70)
print("RUNNING END-TO-END TRACE: POST /api/v1/discovery/start for https://in.nec.com")
print("="*70)

resp = client.post("/api/v1/discovery/start", json={"website_url": "https://in.nec.com"}, headers=headers)
print(f"HTTP Status: {resp.status_code}")
print(f"Response JSON:\n{json.dumps(resp.json(), indent=2)}")

print("\n" + "="*70)
print("DATABASE STATE AFTER DISCOVERY RUN:")
print("="*70)

profile = db.query(EnterpriseProfile).first()
if profile:
    print(f"EnterpriseProfile: ID={profile.id} | OrgName={profile.organization_name} | discovery_status={profile.discovery_status} | URL={profile.website_url}")

latest_run = db.query(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).first()
if latest_run:
    print(f"\nLatest DiscoveryRun:")
    print(f" - Run ID: {latest_run.id}")
    print(f" - Status: {latest_run.status}")
    print(f" - Failure Reason: {latest_run.failure_reason}")
    print(f" - Error Message: {latest_run.error_message}")
    print(f" - Crawled Pages: {latest_run.crawled_pages_count}")
    print(f" - Discovered URLs: {latest_run.discovered_urls_count}")
    print(f" - Duration: {latest_run.crawl_duration_seconds}s")
    print(f" - Submitted URL: {latest_run.website_url}")
    print(f" - Final URL: {latest_run.final_url}")
    print(f" - Root Domain: {latest_run.root_domain}")

facts = db.query(DiscoveredFact).filter(DiscoveredFact.discovery_run_id == latest_run.id).all() if latest_run else []
print(f"\nDiscovered Facts for Run ({len(facts)} total):")
for f in facts:
    print(f" - [{f.status}] {f.fact_type:20} | {f.fact_value[:35]:35} | Conf: {f.confidence} | Source: {f.source_url}")

print("\n" + "="*70)
print("STATUS & FACTS ENDPOINT RESPONSES:")
print("="*70)

status_resp = client.get("/api/v1/discovery/status", headers=headers)
print(f"GET /discovery/status (HTTP {status_resp.status_code}):\n{json.dumps(status_resp.json(), indent=2)}")

facts_resp = client.get("/api/v1/discovery/facts?status=ALL", headers=headers)
print(f"GET /discovery/facts?status=ALL (HTTP {facts_resp.status_code}, count={len(facts_resp.json())}):\n{json.dumps(facts_resp.json()[:3], indent=2)} (showing first 3)")

db.close()
