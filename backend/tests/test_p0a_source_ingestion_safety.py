"""
P0-A Regression Tests: Source Ingestion Must Not Create ComplianceTasks Directly.

These tests verify that the trigger_fetch endpoint in sources.py does NOT create
operational ComplianceTask records from AI-generated recommendations. The only
legitimate task creation path is TaskEngine.generate_tasks, which requires:
  1. Applicability assessment established
  2. Active RegulatoryObligation exists
  3. Required control mapping exists
  4. Tenant organization is known
"""
import pytest
import uuid
import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.domain import (
    EnterpriseProfile, EnterpriseUser, RegulatorySource,
    Regulation, ComplianceTask, RegulatoryObligation,
    KnowledgeGraphChain, AuditLog, ObligationControlMapping,
    InternalControl
)
from app.core.security import create_access_token
from app.services.task_engine import TaskEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def org_a(db_session: Session):
    org = EnterpriseProfile(
        id=f"org-a-{uuid.uuid4().hex[:8]}",
        organization_name="Tenant Alpha Corp",
        industry_sector="Financial Services",
        regulator_region="India",
        discovery_status="CONFIRMED"
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def org_b(db_session: Session):
    org = EnterpriseProfile(
        id=f"org-b-{uuid.uuid4().hex[:8]}",
        organization_name="Tenant Beta Corp",
        industry_sector="Technology",
        regulator_region="US",
        discovery_status="CONFIRMED"
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def user_a(db_session: Session, org_a):
    user = EnterpriseUser(
        id=f"user-a-{uuid.uuid4().hex[:8]}",
        organization_id=org_a.id,
        full_name="Alice Compliance",
        email=f"alice-{uuid.uuid4().hex[:6]}@alpha.com",
        hashed_password="pw",
        role="COMPLIANCE_OFFICER"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def user_b(db_session: Session, org_b):
    user = EnterpriseUser(
        id=f"user-b-{uuid.uuid4().hex[:8]}",
        organization_id=org_b.id,
        full_name="Bob Admin",
        email=f"bob-{uuid.uuid4().hex[:6]}@beta.com",
        hashed_password="pw",
        role="ADMIN"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def auth_headers_a(user_a):
    token = create_access_token(subject=user_a.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_b(user_b):
    token = create_access_token(subject=user_b.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def source_feed(db_session: Session):
    src = RegulatorySource(
        id=f"src-{uuid.uuid4().hex[:8]}",
        authority_name="RBI",
        feed_url="https://rbi.org.in/scripts/NotificationUser.aspx",
        sector="Banking",
        region="India"
    )
    db_session.add(src)
    db_session.commit()
    return src


MOCK_CRAWL_RESULT = {
    "extracted_titles": ["AI Test Directive on Capital Adequacy"],
    "http_status": 200,
    "bytes_scraped": 5000,
    "items_extracted": 1
}

MOCK_AI_PHASE1 = {
    "sections": [{
        "section_number": "Section 1",
        "title": "Capital Requirements",
        "content_text": "Banks must maintain minimum capital.",
        "obligations": [{
            "summary": "Maintain Tier 1 capital ratio above 8%",
            "requirements": [{
                "requirement_text": "All banks shall maintain Tier 1 capital ratio of 8%.",
                "penalty_description": "Statutory penalties under RBI Act.",
                "statutory_reference": "RBI/2026/CAR-01",
                "affected_entities": ["Scheduled Commercial Banks"]
            }]
        }]
    }],
    "classification": {"risk_score": 0.8, "category": "Prudential"},
    "extraction_method": "GEMINI_EXTRACTED"
}

MOCK_AI_PHASE2 = {
    "graph_chains": [{
        "requirement_id": None,
        "control_code": "CTRL-CAP-01",
        "policy_code": "POL-CAP-2026",
        "process_code": "PRC-CAP-MONITOR",
        "department_name": "Treasury",
        "application_code": "APP-RISK-CALC"
    }],
    "recommended_tasks": [{
        "title": "Implement Capital Adequacy Monitoring",
        "description": "Configure automated capital ratio calculation.",
        "control_code": "CTRL-CAP-01",
        "priority": "CRITICAL",
        "assignee": "Treasury Head",
        "reviewer": "CFO"
    }, {
        "title": "Update Capital Reporting Templates",
        "description": "Align quarterly reports with new RBI directive.",
        "control_code": "CTRL-REP-01",
        "priority": "HIGH",
        "assignee": "Reporting Lead",
        "reviewer": "CRO"
    }]
}


def _trigger_fetch(client, source_id, auth_headers):
    """Helper to call trigger_fetch with mocked AI and crawler."""
    with patch("app.api.v1.endpoints.sources.LiveStatutoryCrawlerEngine.scrape_live_source",
               return_value=MOCK_CRAWL_RESULT), \
         patch("app.api.v1.endpoints.sources.MultiAgentAIOrchestrator.process_extraction_only",
               return_value=MOCK_AI_PHASE1), \
         patch("app.api.v1.endpoints.sources.MultiAgentAIOrchestrator.process_impact_and_tasks",
               return_value=MOCK_AI_PHASE2):
        return client.post(f"/api/v1/sources/{source_id}/trigger", headers=auth_headers)


# ---------------------------------------------------------------------------
# A. trigger_fetch with AI recommended_tasks creates ZERO ComplianceTask records
# ---------------------------------------------------------------------------

def test_trigger_fetch_creates_zero_compliance_tasks(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: AI recommended_tasks MUST NOT be persisted as ComplianceTask records."""
    tasks_before = db_session.query(ComplianceTask).count()

    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_regulations_ingested"] == 1

    tasks_after = db_session.query(ComplianceTask).count()
    assert tasks_after == tasks_before, (
        f"trigger_fetch created {tasks_after - tasks_before} ComplianceTask records. "
        "Expected ZERO. AI recommendations must not be persisted as tasks."
    )


# ---------------------------------------------------------------------------
# B. trigger_fetch cannot create a task without an active applicable obligation
# ---------------------------------------------------------------------------

def test_trigger_fetch_requires_obligation_for_tasks(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: No ComplianceTask should exist without an active RegulatoryObligation."""
    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200

    # Verify no ComplianceTask exists at all (since no obligation was created)
    tasks = db_session.query(ComplianceTask).all()
    assert len(tasks) == 0, (
        f"Found {len(tasks)} ComplianceTask record(s) without any RegulatoryObligation."
    )


# ---------------------------------------------------------------------------
# C. AI-generated recommendation remains non-operational if returned to UI
# ---------------------------------------------------------------------------

def test_ai_recommendations_returned_as_non_operational(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: AI recommendations must be clearly labeled as non-operational."""
    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()

    recs = data.get("ai_recommendations", [])
    assert len(recs) == 2, f"Expected 2 AI recommendations, got {len(recs)}"

    for rec in recs:
        assert rec["type"] == "AI_RECOMMENDATION"
        assert rec["status"] == "NON_OPERATIONAL"
        assert "suggested_title" in rec
        assert "note" in rec
        assert "applicability" in rec["note"].lower() or "obligation" in rec["note"].lower()

    # Confirm they are NOT in the database
    tasks = db_session.query(ComplianceTask).count()
    assert tasks == 0


# ---------------------------------------------------------------------------
# D. TaskEngine.generate_tasks remains the legitimate task creation path
# ---------------------------------------------------------------------------

def test_task_engine_is_legitimate_creation_path(
    db_session, org_a
):
    """P0-A: TaskEngine.generate_tasks is the only path that creates operational tasks."""
    # With zero obligations, TaskEngine should create zero tasks
    tasks = TaskEngine.generate_tasks(
        organization_id=org_a.id,
        db=db_session,
        evaluated_by="Test Auditor"
    )
    assert tasks == []
    assert db_session.query(ComplianceTask).count() == 0

    # Create a regulation and an ACTIVE obligation
    reg = Regulation(
        id=f"reg-te-{uuid.uuid4().hex[:8]}",
        title="Test Regulation for TaskEngine",
        authority="TestAuthority",
        doc_number="TA/2026/001",
        sector="Testing",
        region="Global",
        status="ANALYZED",
        publication_date=datetime.date.today(),
        effective_date=datetime.date.today() + datetime.timedelta(days=60),
        content_text="Test content text"
    )
    db_session.add(reg)
    db_session.flush()

    obl = RegulatoryObligation(
        id=f"obl-te-{uuid.uuid4().hex[:8]}",
        organization_id=org_a.id,
        regulation_id=reg.id,
        applicability_assessment_id=f"app-{uuid.uuid4().hex[:8]}",
        title="Test Obligation",
        description="Mandatory test obligation",
        obligation_code="OBL-TEST-001",
        obligation_type="SECURITY_CONTROL",
        status="ACTIVE",
        source_citation="Test Authority Order 2026",
        responsible_function="Compliance"
    )
    db_session.add(obl)
    db_session.commit()

    # Now TaskEngine should create exactly one task
    tasks = TaskEngine.generate_tasks(
        organization_id=org_a.id,
        db=db_session,
        evaluated_by="Test Auditor"
    )
    assert len(tasks) == 1
    created_task = tasks[0]
    assert created_task.organization_id == org_a.id
    assert created_task.regulatory_obligation_id == obl.id
    assert created_task.regulation_id == reg.id


# ---------------------------------------------------------------------------
# E. Any persisted records created by trigger_fetch are tenant-scoped
# ---------------------------------------------------------------------------

def test_trigger_fetch_audit_log_is_tenant_scoped(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: Audit log entries from trigger_fetch must include organization_id."""
    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200

    audits = db_session.query(AuditLog).filter(
        AuditLog.action == "LIVE_STATUTORY_CRAWL_EXECUTED"
    ).all()
    assert len(audits) >= 1

    for audit in audits:
        assert audit.organization_id == org_a.id, (
            f"Audit log entry has organization_id={audit.organization_id}, "
            f"expected {org_a.id}. Audit entries must be tenant-scoped."
        )


# ---------------------------------------------------------------------------
# F. AI recommendations cannot create obligations automatically
# ---------------------------------------------------------------------------

def test_ai_recommendations_do_not_create_obligations(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: AI recommendations must not auto-generate RegulatoryObligation records."""
    obligations_before = db_session.query(RegulatoryObligation).count()

    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200

    obligations_after = db_session.query(RegulatoryObligation).count()
    assert obligations_after == obligations_before, (
        f"trigger_fetch created {obligations_after - obligations_before} RegulatoryObligation "
        "records. AI recommendations must not auto-generate obligations."
    )


# ---------------------------------------------------------------------------
# G. AI recommendations cannot create controls automatically
# ---------------------------------------------------------------------------

def test_ai_recommendations_do_not_create_controls(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: AI recommendations must not auto-generate InternalControl records."""
    controls_before = db_session.query(InternalControl).count()

    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200

    controls_after = db_session.query(InternalControl).count()
    assert controls_after == controls_before, (
        f"trigger_fetch created {controls_after - controls_before} InternalControl records."
    )


# ---------------------------------------------------------------------------
# H. No hardcoded assignee/reviewer is persisted
# ---------------------------------------------------------------------------

def test_no_hardcoded_assignee_reviewer_persisted(
    client, db_session, org_a, user_a, auth_headers_a, source_feed
):
    """P0-A: 'Sanjana' and 'David Vance' must never appear in persisted records."""
    resp = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp.status_code == 200

    tasks = db_session.query(ComplianceTask).all()
    for t in tasks:
        assert t.assignee != "Sanjana", "Hardcoded assignee 'Sanjana' found in persisted task"
        assert t.reviewer != "David Vance", "Hardcoded reviewer 'David Vance' found in persisted task"

    # Also check AI recommendations in response
    data = resp.json()
    for rec in data.get("ai_recommendations", []):
        assert "assignee" not in rec, "AI recommendation should not contain an 'assignee' field"
        assert "reviewer" not in rec, "AI recommendation should not contain a 'reviewer' field"


# ---------------------------------------------------------------------------
# I. Tenant A cannot receive tasks created for Tenant B
# ---------------------------------------------------------------------------

def test_tenant_isolation_no_cross_tenant_tasks(
    client, db_session, org_a, org_b, user_a, user_b,
    auth_headers_a, auth_headers_b, source_feed
):
    """P0-A: Tasks generated via TaskEngine for Org A must not be visible to Org B."""
    # Org A triggers a fetch (creates regulatory knowledge, no tasks)
    resp_a = _trigger_fetch(client, source_feed.id, auth_headers_a)
    assert resp_a.status_code == 200

    # Create an obligation for Org A so TaskEngine can generate tasks
    reg = db_session.query(Regulation).filter(
        Regulation.title == "AI Test Directive on Capital Adequacy"
    ).first()
    assert reg is not None

    obl = RegulatoryObligation(
        id=f"obl-iso-{uuid.uuid4().hex[:8]}",
        organization_id=org_a.id,
        regulation_id=reg.id,
        applicability_assessment_id=f"app-{uuid.uuid4().hex[:8]}",
        title="Capital Adequacy Obligation",
        description="Tenant A specific obligation",
        obligation_code="OBL-ISO-001",
        obligation_type="REPORTING",
        status="ACTIVE",
        source_citation="RBI Act 2026",
        responsible_function="Treasury"
    )
    db_session.add(obl)
    db_session.commit()

    # Generate tasks for Org A via the legitimate path
    tasks = TaskEngine.generate_tasks(
        organization_id=org_a.id,
        db=db_session,
        evaluated_by="Alice Compliance"
    )
    assert len(tasks) >= 1
    org_a_task = tasks[0]
    assert org_a_task.organization_id == org_a.id

    # Org B should have zero tasks
    org_b_tasks = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == org_b.id
    ).all()
    assert len(org_b_tasks) == 0, (
        f"Org B has {len(org_b_tasks)} tasks. Expected 0. "
        "Cross-tenant task leakage detected."
    )

    # Global (org_id=None) tasks must not exist
    global_tasks = db_session.query(ComplianceTask).filter(
        ComplianceTask.organization_id == None  # noqa: E711
    ).all()
    assert len(global_tasks) == 0, (
        f"Found {len(global_tasks)} global (organization_id=None) tasks. "
        "All tasks must be tenant-scoped."
    )
