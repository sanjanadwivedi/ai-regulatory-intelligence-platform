"""
migrate_compliance_intelligence.py
Phase 1 migration: create compliance_intelligence_snapshots, compliance_defense_packs,
                   and compliance_evidence_manifests tables.

These tables are part of the READ-ONLY intelligence & defense-pack layer.
They never mutate upstream legal records.
"""
import sys
import os

# Allow running from the scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import engine
from sqlalchemy import text

DDL = [
    # ---------------------------------------------------------------
    # 1. Compliance Intelligence Snapshots
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS compliance_intelligence_snapshots (
        id                  TEXT        NOT NULL PRIMARY KEY,
        organization_id     TEXT        NOT NULL REFERENCES enterprise_profile(id) ON DELETE CASCADE,
        snapshot_type       TEXT        NOT NULL DEFAULT 'POINT_IN_TIME',
        generated_by        TEXT,
        generated_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        engine_version      TEXT        NOT NULL DEFAULT 'v1.0.0-deterministic',
        legal_summary       TEXT,           -- JSON
        obligation_summary  TEXT,           -- JSON
        operational_summary TEXT,           -- JSON
        evidence_summary    TEXT,           -- JSON
        alert_summary       TEXT,           -- JSON
        deadline_summary    TEXT,           -- JSON
        unresolved_items    TEXT,           -- JSON
        review_items        TEXT,           -- JSON
        provenance_summary  TEXT,           -- JSON
        created_at          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # ---------------------------------------------------------------
    # 2. Compliance Defense Packs
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS compliance_defense_packs (
        id              TEXT        NOT NULL PRIMARY KEY,
        organization_id TEXT        NOT NULL REFERENCES enterprise_profile(id) ON DELETE CASCADE,
        snapshot_id     TEXT        NOT NULL REFERENCES compliance_intelligence_snapshots(id) ON DELETE CASCADE,
        pack_version    TEXT        NOT NULL,
        generated_by    TEXT,
        generated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status          TEXT        NOT NULL DEFAULT 'GENERATED',
        file_path       TEXT,
        content_hash    TEXT        NOT NULL,
        manifest        TEXT,               -- JSON
        engine_version  TEXT        NOT NULL DEFAULT 'v1.0.0-deterministic',
        created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Unique index: each (organization, version) pair is unique for active packs
    """
    CREATE UNIQUE INDEX IF NOT EXISTS
        uix_defense_pack_org_version
    ON compliance_defense_packs (organization_id, pack_version)
    """,

    # ---------------------------------------------------------------
    # 3. Compliance Evidence Manifests
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS compliance_evidence_manifests (
        id                  TEXT        NOT NULL PRIMARY KEY,
        defense_pack_id     TEXT        NOT NULL REFERENCES compliance_defense_packs(id) ON DELETE CASCADE,
        organization_id     TEXT        NOT NULL,
        evidence_layer      TEXT        NOT NULL,   -- REGULATORY | ORGANIZATION | OPERATIONAL
        evidence_type       TEXT,
        source_entity_type  TEXT,
        source_entity_id    TEXT,
        title               TEXT        NOT NULL,
        description         TEXT,
        source_url          TEXT,
        source_citation     TEXT,
        captured_at         DATETIME,
        content_hash        TEXT,
        provenance_refs     TEXT,                   -- JSON
        evidence_status     TEXT        NOT NULL,   -- PRESENT | MISSING | REQUIRES_REVIEW
        created_at          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

def run():
    with engine.connect() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
        conn.commit()
    print("[OK] Migration complete: compliance_intelligence_snapshots, compliance_defense_packs, compliance_evidence_manifests")

if __name__ == "__main__":
    run()
