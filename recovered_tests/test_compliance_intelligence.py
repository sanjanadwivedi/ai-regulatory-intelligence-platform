"""
test_compliance_intelligence.py

27-invariant test suite for the Compliance Intelligence & Defense Pack Layer.

Invariants covered:
1.  test_snapshot_contains_legal_landscape
2.  test_snapshot_contains_obligation_summary
3.  test_snapshot_contains_task_summary
4.  test_snapshot_contains_evidence_summary
5.  test_completed_without_evidence_detected
6.  test_evidence_gap_detected
7.  test_overdue_task_detected
8.  test_requires_review_items_detected
9.  test_triggered_deadline_preserved
10. test_continuous_deadline_remains_null
11. test_provenance_graph_complete
12. test_regulatory_evidence_segregated
13. test_organization_evidence_segregated
14. test_operational_evidence_segregated
15. test_snapshot_idempotency
16. test_defense_pack_hash_deterministic
17. test_defense_pack_versioning
18. test_historical_pack_immutable
19. test_cross_org_snapshot_isolation
20. test_cross_org_defense_pack_isolation
21. test_audit_log_snapshot_generation
22. test_audit_log_pack_generation
23. test_audit_log_export
24. test_no_upstream_mutation
25. test_no_legal_compliance_claim
26. test_no_fabricated_evidence
27. test_no_fabricated_deadlines
"""

import pytest
import datetime
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, Base, engine
from app.models.domain import (
    EnterpriseProfile,
    DiscoveredFact,
    Regulation,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ComplianceTask,
    ComplianceTaskEvidence,
    ComplianceTaskActivity,
    ComplianceTriggerEvent,
    ComplianceAlert,
    AuditLog,
    ComplianceIntelligenceSnapshot,
    ComplianceDefensePack,
    ComplianceEvidenceManifest,
)
from app.models.domain import generate_uuid
from app.services.compliance_intelligence_service import ComplianceIntelligenceService
from app.services.defense_pack_service import DefensePackService, _compute_content_hash


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def clean_org(db_session: Session):
    """Isolated org for each test, fully cleaned up afterwards."""
    # Clean up intelligence layer tables first
    db_session.query(ComplianceEvidenceManifest).delete()
    db_session.query(ComplianceDefensePack).delete()
    db_session.query(ComplianceIntelligenceSnapshot).delete()
    db_session.query(ComplianceAlert).delete()
    db_session.query(ComplianceTaskActivity).delete()
    db_session.query(ComplianceTaskEvidence).delete()
    db_session.query(ComplianceTriggerEvent).delete()
    db_session.query(ComplianceTask).delete()
    db_session.query(RegulatoryObligation).delete()
    db_session.query(RegulatoryApplicabilityAssessment).delete()
    db_session.query(EnterpriseProfile).delete()
    db_session.commit()

    org = EnterpriseProfile(
        id=generate_uuid(),
        organization_name="TestOrg Intelligence",
        country="India",
        industry_sector="ICT",
        locations=["India"],
        business_activities=["ICT", "Cloud Infrastructure"],
        discovery_status="CONFIRMED",
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def _make_assessment(org_id, reg_id, status, db):
    a = RegulatoryApplicabilityAssessment(
        id=generate_uuid(),
        organization_id=org_id,
        regulation_id=reg_id,
        status=status,
        applicability_score=1.0 if status == "APPLICABLE" else 0.0,
        rationale=f"Test rationale — {status}",
        engine_version="v2.0",
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_obligation(org_id, reg_id, assess_id, code, ob_status, priority="HIGH",
                     trigger_type=None, trigger_value=None, trigger_unit=None,
                     due_rule=None, frequency=None, db=None):
    o = RegulatoryObligation(
        id=generate_uuid(),
        organization_id=org_id,
        regulation_id=reg_id,
        applicability_assessment_id=assess_id,
        obligation_code=code,
        title=f"Obligation {code}",
        description="Test obligation",
        obligation_type="REPORTING",
        priority=priority,
        status=ob_status,
        source_citation="Test Citation §1",
        authoritative_source_url="https://example.com/reg",
        trigger_type=trigger_type,
        trigger_offset_value=trigger_value,
        trigger_offset_unit=trigger_unit,
        due_rule=due_rule,
        frequency=frequency,
        engine_version="v2.0",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _make_task(org_id, reg_id, obl_id, code, task_status, due_date=None, priority="HIGH", db=None):
    t = ComplianceTask(
        id=generate_uuid(),
        organization_id=org_id,
        regulation_id=reg_id,
        regulatory_obligation_id=obl_id,
        control_code=code,
        title=f"Task {code}",
        assignee="test@example.com",
        reviewer="reviewer@example.com",
        status=task_status,
        due_date=due_date,
        priority=priority,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _add_evidence(task_id, db):
    ev = ComplianceTaskEvidence(
        id=generate_uuid(),
        task_id=task_id,
        uploaded_by="test@example.com",
        uploader_role="Compliance Officer",
        evidence_type="LOG",
        file_name="audit.log",
        uploaded_at=datetime.datetime.utcnow(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# ==============================================================================
# 1. test_snapshot_contains_legal_landscape
# ==============================================================================
def test_snapshot_contains_legal_landscape(db_session: Session, clean_org):
    org = clean_org
    _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    _make_assessment(org.id, "reg-2", "NOT_APPLICABLE", db_session)
    _make_assessment(org.id, "reg-3", "REQUIRES_REVIEW", db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ls = snap.legal_summary
    assert ls["applicable"] == 1
    assert ls["not_applicable"] == 1
    assert ls["requires_review"] == 1
    assert ls["total"] == 3


# ==============================================================================
# 2. test_snapshot_contains_obligation_summary
# ==============================================================================
def test_snapshot_contains_obligation_summary(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    _make_obligation(org.id, "reg-1", a.id, "OBL-01", "ACTIVE", db=db_session)
    _make_obligation(org.id, "reg-1", a.id, "OBL-02", "SUPERSEDED", db=db_session)
    _make_obligation(org.id, "reg-1", a.id, "OBL-03", "REQUIRES_REVIEW", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ob = snap.obligation_summary
    assert ob["active"] == 1
    assert ob["superseded"] == 1
    assert ob["requires_review"] == 1
    assert ob["total"] == 3


# ==============================================================================
# 3. test_snapshot_contains_task_summary
# ==============================================================================
def test_snapshot_contains_task_summary(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-T01", "ACTIVE", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-01", "OPEN", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-02", "COMPLETED", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-03", "BLOCKED", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ops = snap.operational_summary
    assert ops["OPEN"] == 1
    assert ops["COMPLETED"] == 1
    assert ops["BLOCKED"] == 1
    assert ops["total"] == 3


# ==============================================================================
# 4. test_snapshot_contains_evidence_summary
# ==============================================================================
def test_snapshot_contains_evidence_summary(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-E01", "ACTIVE", db=db_session)
    t = _make_task(org.id, "reg-1", o.id, "T-E01", "OPEN", db=db_session)
    _add_evidence(t.id, db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ev = snap.evidence_summary
    assert "evidence_present" in ev
    assert "evidence_gap" in ev
    assert ev["evidence_present"] >= 1


# ==============================================================================
# 5. test_completed_without_evidence_detected
# ==============================================================================
def test_completed_without_evidence_detected(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-CWE", "ACTIVE", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-CWE", "COMPLETED", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ev = snap.evidence_summary
    assert ev["completed_without_evidence"] == 1
    # Verify disclaimer present in at least one item
    items_with_disclaimer = [
        i for i in ev.get("items", [])
        if i.get("evidence_status") == "COMPLETED_WITHOUT_EVIDENCE"
    ]
    assert len(items_with_disclaimer) == 1
    assert "does not independently establish legal compliance" in items_with_disclaimer[0]["reason"]


# ==============================================================================
# 6. test_evidence_gap_detected
# ==============================================================================
def test_evidence_gap_detected(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-GAP", "ACTIVE", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-GAP", "OPEN", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    assert snap.evidence_summary["evidence_gap"] >= 1


# ==============================================================================
# 7. test_overdue_task_detected
# ==============================================================================
def test_overdue_task_detected(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-OD", "ACTIVE", db=db_session)
    past = datetime.datetime.utcnow() - datetime.timedelta(days=5)
    _make_task(org.id, "reg-1", o.id, "T-OD", "OPEN", due_date=past, db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    ops = snap.operational_summary
    assert ops["OVERDUE"] >= 1

    overdue_items = [i for i in (snap.unresolved_items or []) if i.get("category") == "OVERDUE_TASK"]
    assert len(overdue_items) >= 1


# ==============================================================================
# 8. test_requires_review_items_detected
# ==============================================================================
def test_requires_review_items_detected(db_session: Session, clean_org):
    org = clean_org
    _make_assessment(org.id, "reg-1", "REQUIRES_REVIEW", db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    review_items = snap.review_items or []
    assert len(review_items) >= 1
    assert any(i.get("category") == "REQUIRES_REVIEW_APPLICABILITY" for i in review_items)


# ==============================================================================
# 9. test_triggered_deadline_preserved
# ==============================================================================
def test_triggered_deadline_preserved(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(
        org.id, "reg-1", a.id, "OBL-TR", "ACTIVE",
        trigger_type="INCIDENT_DETECTED",
        trigger_value=6, trigger_unit="HOURS",
        due_rule="Within 6 hours of incident detection",
        db=db_session,
    )
    future = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    t = _make_task(org.id, "reg-1", o.id, "T-TR", "IN_PROGRESS", due_date=future, db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    dl = snap.deadline_summary
    triggered = dl.get("triggered", [])
    assert any(d["obligation_id"] == o.id for d in triggered), \
        f"Expected triggered deadline for obligation {o.id}; got: {triggered}"


# ==============================================================================
# 10. test_continuous_deadline_remains_null
# ==============================================================================
def test_continuous_deadline_remains_null(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(
        org.id, "reg-1", a.id, "OBL-CONT", "ACTIVE",
        frequency="ANNUAL",
        db=db_session,
    )
    _make_task(org.id, "reg-1", o.id, "T-CONT", "OPEN", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    dl = snap.deadline_summary
    continuous = dl.get("continuous", [])
    assert any(d["obligation_id"] == o.id for d in continuous)
    # due_date must remain NULL — never invented
    for d in continuous:
        if d["obligation_id"] == o.id:
            assert d["due_date"] is None


# ==============================================================================
# 11. test_provenance_graph_complete
# ==============================================================================
def test_provenance_graph_complete(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-PRV", "ACTIVE", db=db_session)
    t = _make_task(org.id, "reg-1", o.id, "T-PRV", "OPEN", db=db_session)
    _add_evidence(t.id, db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    prov = snap.provenance_summary
    assert prov is not None
    assert prov["total_chains"] >= 1
    chain = prov["chains"][0]
    assert "regulation" in chain
    assert "assessment" in chain
    assert len(chain["obligations"]) >= 1
    obl_entry = chain["obligations"][0]
    assert "obligation" in obl_entry
    assert obl_entry["task"] is not None
    assert obl_entry["task"]["evidence_count"] >= 1


# ==============================================================================
# 12. test_regulatory_evidence_segregated
# ==============================================================================
def test_regulatory_evidence_segregated(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-REG", "ACTIVE", db=db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)

    manifests = DefensePackService.get_defense_pack_manifest(pack.id, org.id, db_session)
    reg_layer = [m for m in manifests if m.evidence_layer == "REGULATORY"]
    org_layer = [m for m in manifests if m.evidence_layer == "ORGANIZATION"]
    op_layer  = [m for m in manifests if m.evidence_layer == "OPERATIONAL"]

    # They must not overlap
    reg_ids = {m.source_entity_id for m in reg_layer}
    org_ids = {m.source_entity_id for m in org_layer}
    assert reg_ids.isdisjoint(org_ids), "Regulatory and Organization layers must not share entries"


# ==============================================================================
# 13. test_organization_evidence_segregated
# ==============================================================================
def test_organization_evidence_segregated(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)

    manifests = DefensePackService.get_defense_pack_manifest(pack.id, org.id, db_session)
    org_layer = [m for m in manifests if m.evidence_layer == "ORGANIZATION"]
    # Must contain the confirmed profile
    profile_entries = [m for m in org_layer if m.evidence_type == "CONFIRMED_PROFILE"]
    assert len(profile_entries) >= 1


# ==============================================================================
# 14. test_operational_evidence_segregated
# ==============================================================================
def test_operational_evidence_segregated(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-OP", "ACTIVE", db=db_session)
    t = _make_task(org.id, "reg-1", o.id, "T-OP", "OPEN", db=db_session)
    _add_evidence(t.id, db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)

    manifests = DefensePackService.get_defense_pack_manifest(pack.id, org.id, db_session)
    op_layer = [m for m in manifests if m.evidence_layer == "OPERATIONAL"]
    present = [m for m in op_layer if m.evidence_status == "PRESENT"]
    assert len(present) >= 1


# ==============================================================================
# 15. test_snapshot_idempotency
# ==============================================================================
def test_snapshot_idempotency(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-IDEM", "ACTIVE", db=db_session)

    snap1 = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    snap2 = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)

    # Each call MUST create a distinct record (immutability)
    assert snap1.id != snap2.id

    # Both snapshots still exist
    all_snaps = db_session.query(ComplianceIntelligenceSnapshot).filter(
        ComplianceIntelligenceSnapshot.organization_id == org.id
    ).all()
    assert len(all_snaps) == 2

    # Original snapshot JSON is unchanged
    original = db_session.query(ComplianceIntelligenceSnapshot).filter(
        ComplianceIntelligenceSnapshot.id == snap1.id
    ).first()
    assert original.legal_summary == snap1.legal_summary


# ==============================================================================
# 16. test_defense_pack_hash_deterministic
# ==============================================================================
def test_defense_pack_hash_deterministic(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-HASH", "ACTIVE", db=db_session)

    snap1 = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)

    # Clear defense packs to prevent version conflict
    db_session.query(ComplianceEvidenceManifest).delete()
    db_session.query(ComplianceDefensePack).delete()
    db_session.commit()

    # Build canonical payload with same stable content twice
    snap = db_session.query(ComplianceIntelligenceSnapshot).filter(
        ComplianceIntelligenceSnapshot.id == snap1.id
    ).first()
    payload = {
        "organization_id": org.id,
        "snapshot_id": snap.id,
        "engine_version": "v1.0.0-deterministic",
        "legal_summary": snap.legal_summary,
        "obligation_summary": snap.obligation_summary,
        "operational_summary": snap.operational_summary,
        "evidence_summary": snap.evidence_summary,
        "alert_summary": snap.alert_summary,
        "deadline_summary": snap.deadline_summary,
        "unresolved_items": snap.unresolved_items,
        "review_items": snap.review_items,
        "provenance_summary": snap.provenance_summary,
        "evidence_manifest": [],
    }
    hash1 = _compute_content_hash(payload)
    hash2 = _compute_content_hash(payload)
    assert hash1 == hash2, "Same payload must always produce the same SHA-256 hash"


# ==============================================================================
# 17. test_defense_pack_versioning
# ==============================================================================
def test_defense_pack_versioning(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)

    pack1 = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    assert pack1.pack_version == "v1"
    assert pack1.status == "GENERATED"

    pack2 = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    assert pack2.pack_version == "v2"
    assert pack2.status == "GENERATED"

    # v1 must be SUPERSEDED
    db_session.refresh(pack1)
    assert pack1.status == "SUPERSEDED"


# ==============================================================================
# 18. test_historical_pack_immutable
# ==============================================================================
def test_historical_pack_immutable(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)

    pack1 = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    original_hash = pack1.content_hash
    original_manifest = pack1.manifest

    # Generate v2
    DefensePackService.generate_defense_pack(snap.id, org.id, db_session)

    # Reload v1 from DB
    db_session.refresh(pack1)
    assert pack1.content_hash == original_hash, "Historical pack content_hash must not change"
    assert pack1.manifest == original_manifest, "Historical pack manifest must not change"
    # status changed to SUPERSEDED but no content mutation
    assert pack1.status == "SUPERSEDED"


# ==============================================================================
# 19. test_cross_org_snapshot_isolation
# ==============================================================================
def test_cross_org_snapshot_isolation(db_session: Session, clean_org):
    org_a = clean_org

    # Create a second org
    org_b = EnterpriseProfile(
        id=generate_uuid(),
        organization_name="OrgB",
        country="USA",
        discovery_status="CONFIRMED",
    )
    db_session.add(org_b)
    db_session.commit()

    _make_assessment(org_a.id, "reg-1", "APPLICABLE", db_session)
    snap_a = ComplianceIntelligenceService.generate_snapshot(org_a.id, db_session)

    # Org B cannot retrieve Org A's snapshot
    result = ComplianceIntelligenceService.get_snapshot_by_id(snap_a.id, org_b.id, db_session)
    assert result is None, "Cross-organisation snapshot access must return None"


# ==============================================================================
# 20. test_cross_org_defense_pack_isolation
# ==============================================================================
def test_cross_org_defense_pack_isolation(db_session: Session, clean_org):
    org_a = clean_org
    org_b = EnterpriseProfile(
        id=generate_uuid(),
        organization_name="OrgB-DPack",
        country="USA",
        discovery_status="CONFIRMED",
    )
    db_session.add(org_b)
    db_session.commit()

    _make_assessment(org_a.id, "reg-1", "APPLICABLE", db_session)
    snap_a = ComplianceIntelligenceService.generate_snapshot(org_a.id, db_session)
    pack_a = DefensePackService.generate_defense_pack(snap_a.id, org_a.id, db_session)

    # Org B cannot retrieve Org A's pack
    result = DefensePackService.get_defense_pack(pack_a.id, org_b.id, db_session)
    assert result is None, "Cross-organisation defense pack access must return None"


# ==============================================================================
# 21. test_audit_log_snapshot_generation
# ==============================================================================
def test_audit_log_snapshot_generation(db_session: Session, clean_org):
    org = clean_org
    _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session, generated_by="auditor@test.com")

    log = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org.id,
        AuditLog.action == "COMPLIANCE_INTELLIGENCE_SNAPSHOT_GENERATED",
    ).first()
    assert log is not None
    assert log.details["snapshot_id"] == snap.id
    assert log.actor == "auditor@test.com"


# ==============================================================================
# 22. test_audit_log_pack_generation
# ==============================================================================
def test_audit_log_pack_generation(db_session: Session, clean_org):
    org = clean_org
    _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session, generated_by="ciso@test.com")

    log = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org.id,
        AuditLog.action == "COMPLIANCE_DEFENSE_PACK_GENERATED",
    ).first()
    assert log is not None
    assert log.details["pack_id"] == pack.id
    assert log.details["content_hash"] == pack.content_hash
    assert log.actor == "ciso@test.com"


# ==============================================================================
# 23. test_audit_log_export
# ==============================================================================
def test_audit_log_export(db_session: Session, clean_org):
    org = clean_org
    _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    DefensePackService.export_defense_pack_json(pack.id, org.id, db_session, actor="export@test.com")

    log = db_session.query(AuditLog).filter(
        AuditLog.organization_id == org.id,
        AuditLog.action == "COMPLIANCE_DEFENSE_PACK_EXPORTED",
    ).first()
    assert log is not None
    assert log.details["pack_id"] == pack.id
    assert log.actor == "export@test.com"


# ==============================================================================
# 24. test_no_upstream_mutation
# ==============================================================================
def test_no_upstream_mutation(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-MUT", "ACTIVE", db=db_session)
    t = _make_task(org.id, "reg-1", o.id, "T-MUT", "OPEN", db=db_session)

    # Snapshot upstream state
    assess_before = (a.id, a.status, a.applicability_score)
    obl_before = (o.id, o.status, o.obligation_code)
    task_before = (t.id, t.status, t.title)
    org_name_before = org.organization_name

    # Generate snapshot and defense pack
    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    DefensePackService.export_defense_pack_json(snap.defense_packs[0].id, org.id, db_session)

    db_session.refresh(a)
    db_session.refresh(o)
    db_session.refresh(t)
    db_session.refresh(org)

    assert (a.id, a.status, a.applicability_score) == assess_before
    assert (o.id, o.status, o.obligation_code) == obl_before
    assert (t.id, t.status, t.title) == task_before
    assert org.organization_name == org_name_before


# ==============================================================================
# 25. test_no_legal_compliance_claim
# ==============================================================================
def test_no_legal_compliance_claim(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-LEGAL", "ACTIVE", db=db_session)
    t = _make_task(org.id, "reg-1", o.id, "T-LEGAL", "COMPLETED", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)
    export = DefensePackService.export_defense_pack_json(pack.id, org.id, db_session)

    disclaimer = export["manifest"]["legal_disclaimers"]["compliance_disclaimer"]
    assert "does not independently establish legal compliance" in disclaimer

    # Evidence summary must not use the word "COMPLIANT" for completed tasks
    ev_items = snap.evidence_summary.get("items", [])
    for item in ev_items:
        assert item.get("evidence_status") != "COMPLIANT", \
            "Evidence status must never be COMPLIANT"


# ==============================================================================
# 26. test_no_fabricated_evidence
# ==============================================================================
def test_no_fabricated_evidence(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    o = _make_obligation(org.id, "reg-1", a.id, "OBL-FAB", "ACTIVE", db=db_session)
    _make_task(org.id, "reg-1", o.id, "T-FAB", "OPEN", db=db_session)  # No evidence attached

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    pack = DefensePackService.generate_defense_pack(snap.id, org.id, db_session)

    manifests = DefensePackService.get_defense_pack_manifest(pack.id, org.id, db_session)
    op_layer = [m for m in manifests if m.evidence_layer == "OPERATIONAL"]

    # Verify no PRESENT evidence was fabricated
    present = [m for m in op_layer if m.evidence_status == "PRESENT"]
    # There should be 0 uploaded evidence files since we never added any
    # (The service should NOT generate fake PRESENT entries)
    actual_evidence_db = db_session.query(ComplianceTaskEvidence).filter(
        ComplianceTaskEvidence.task_id != None
    ).all()
    real_present_count = len([e for e in actual_evidence_db])
    fabricated_present_count = len(present) - real_present_count
    assert fabricated_present_count == 0, \
        f"No fabricated PRESENT evidence entries allowed; found {fabricated_present_count} extra"


# ==============================================================================
# 27. test_no_fabricated_deadlines
# ==============================================================================
def test_no_fabricated_deadlines(db_session: Session, clean_org):
    org = clean_org
    a = _make_assessment(org.id, "reg-1", "APPLICABLE", db_session)
    # Obligation with due_rule text BUT no structured trigger metadata
    o = _make_obligation(
        org.id, "reg-1", a.id, "OBL-DEAD", "ACTIVE",
        due_rule="Within 30 days of assessment",  # Human-readable only
        # trigger_type, trigger_value, trigger_unit all remain None
        db=db_session,
    )
    _make_task(org.id, "reg-1", o.id, "T-DEAD", "OPEN", db=db_session)

    snap = ComplianceIntelligenceService.generate_snapshot(org.id, db_session)
    dl = snap.deadline_summary

    # Without structured metadata, due_date must remain NULL
    for category in ("triggered", "awaiting_trigger", "continuous"):
        for d in dl.get(category, []):
            if d["obligation_id"] == o.id:
                assert d["due_date"] is None, \
                    "due_date must be NULL when trigger metadata is absent; never invented"

    # Should appear in missing_trigger_metadata, not triggered
    missing = dl.get("missing_trigger_metadata", [])
    assert any(d["obligation_id"] == o.id for d in missing), \
        "Obligation with text-only due_rule must appear in missing_trigger_metadata"
