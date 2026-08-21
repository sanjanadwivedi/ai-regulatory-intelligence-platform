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
    assert canonical.source_authority == "U.S. Securities and Exchange Commission (SEC)"
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
