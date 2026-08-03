import pytest
from app.shared_kernel.primitives import RegulationId, RiskLevel, ImpactAssessedEvent
from app.acl.adapters import RBIFeedAdapter, SECFeedAdapter
from app.services.graph_service import KnowledgeGraphEngine
from app.services.diff_service import RegulationDeltaAnalyzer

def test_shared_kernel_primitives():
    reg_id = RegulationId()
    assert reg_id.value is not None
    
    risk = RiskLevel(score=85, label="HIGH")
    assert risk.score == 85
    assert risk.label == "HIGH"

def test_acl_rbi_adapter():
    raw_feed = {
        "circular_no": "RBI/2026-27/104",
        "subject": "Master Direction - KYC Amendment 2026",
        "body": "Mandatory 2-year high-risk cadence..."
    }
    canonical = RBIFeedAdapter.translate_feed(raw_feed)
    assert canonical.source_authority == "Reserve Bank of India (RBI)"
    assert canonical.external_doc_id == "RBI/2026-27/104"
    assert canonical.region == "India"

def test_acl_sec_adapter():
    raw_json = {
        "release_no": "Release No. 33-11216",
        "title": "Cybersecurity Incident Disclosure Rules",
        "text": "Disclosure guidelines..."
    }
    canonical = SECFeedAdapter.translate_feed(raw_json)
    assert canonical.source_authority == "U.S. Securities and Exchange Commission (SEC / FINRA)"

    assert canonical.external_doc_id == "Release No. 33-11216"

def test_knowledge_graph_engine():
    graph = KnowledgeGraphEngine.get_regulation_graph("reg-rbi-kyc-2026")
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) == 9
    assert len(graph["edges"]) == 8
    
    types = [n["type"] for n in graph["nodes"]]
    assert "REGULATION" in types
    assert "REQUIREMENT" in types
    assert "CONTROL" in types
    assert "POLICY" in types
    assert "TASK" in types

def test_delta_analyzer_engine():
    delta = RegulationDeltaAnalyzer.compare_versions("reg-rbi-kyc-2026", v1=1, v2=2)
    assert "added_requirements" in delta
    assert "modified_requirements" in delta
    assert "repealed_requirements" in delta
    assert len(delta["added_requirements"]) >= 1
    assert len(delta["modified_requirements"]) >= 1
    assert len(delta["repealed_requirements"]) >= 1


def test_re_extract_validation():
    from app.core.database import SessionLocal
    from app.models.domain import Regulation, AuditLog
    from app.api.v1.endpoints.regulations import re_extract_regulation

    db = SessionLocal()
    try:
        # Test 1: Non-existent regulation_id
        res_missing = re_extract_regulation("reg-non-existent-999", db=db, current_user=None)
        assert res_missing["status"] == "FAILED"
        assert "not found" in res_missing["error_message"]

        # Test 2: Regulation with empty source_url
        import datetime
        empty_reg = Regulation(
            id="reg-test-empty-url",
            title="Empty Source Regulation",
            doc_number="TEST-001",
            authority="RBI",
            sector="Banking",
            region="India",
            publication_date=datetime.date.today(),
            effective_date=datetime.date.today(),
            source_url="",
            content_text="Short content"

        )

        db.add(empty_reg)
        db.commit()

        res_empty = re_extract_regulation("reg-test-empty-url", db=db, current_user=None)
        assert res_empty["status"] == "FAILED"
        assert "source_url is empty" in res_empty["error_message"]

        # Clean up test empty reg
        db.delete(empty_reg)
        db.commit()

    finally:
        db.close()


def test_batch_re_extract_endpoint():
    from app.core.database import SessionLocal
    from app.api.v1.endpoints.regulations import batch_re_extract_regulations
    from app.models.domain import AuditLog

    db = SessionLocal()
    try:
        payload = {
            "filters": {"authority": "RBI"},
            "auto_resolve": True,
            "parallel_workers": 4,
            "dry_run": True
        }

        res = batch_re_extract_regulations(payload, db=db, current_user=None)

        assert res["status"] == "COMPLETED"
        assert res["total_regulations_found"] >= 1
        assert "summary" in res
        assert res["summary"]["dry_run"] is True
        assert res["summary"]["batch_audit_id"] is not None

        # Verify AuditLog created
        audit = db.query(AuditLog).filter(AuditLog.id == res["summary"]["batch_audit_id"]).first()
        assert audit is not None
        assert audit.action == "BATCH_RE_EXTRACTION"
    finally:
        db.close()


def test_strict_authentication_enforcement():

    from app.core.security import get_current_user
    from fastapi import HTTPException

    # Passing no token must raise 401 Unauthorized
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=None, token=None)
    assert exc_info.value.status_code == 401
    assert "token missing" in exc_info.value.detail.lower()


def test_ssrf_protection_validator():
    from app.acl.adapters import _validate_url

    # Malicious/Internal URLs must raise ValueError
    blocked_urls = [
        "http://127.0.0.1/admin",
        "http://localhost:8000/api/v1/audit",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/router",
        "ftp://example.com/file.txt",
        "file:///etc/passwd"
    ]
    for url in blocked_urls:
        with pytest.raises(ValueError):
            _validate_url(url)

    # Valid public HTTPS URLs must pass without raising ValueError
    valid_urls = [
        "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566",
        "https://www.sec.gov/rules/final/2023/33-11216.pdf",
        "https://www.finra.org/rules-guidance/rulebooks/finra-rules"
    ]
    for url in valid_urls:
        _validate_url(url)



