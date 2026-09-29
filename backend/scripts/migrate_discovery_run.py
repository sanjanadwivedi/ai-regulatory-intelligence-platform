import sqlite3
import os
import sys
from typing import Optional
from app.core.config import settings

PROTECTED_DATABASES = {"compliance_platform.db", "compliance_platform_browser_audit.db"}


def get_target_db_path(db_path: Optional[str] = None) -> Optional[str]:
    if db_path:
        return db_path
    db_url = getattr(settings, "DATABASE_URL", "")
    if "sqlite" in db_url:
        clean = db_url.split(":///")[-1]
        if clean.startswith("./"):
            clean = clean[2:]
        return clean
    return None


def migrate_db(db_path: Optional[str] = None):
    target = get_target_db_path(db_path)
    if not target or not os.path.exists(target):
        return

    # In test mode or when running tests, never mutate protected databases
    is_testing = "pytest" in sys.modules or os.getenv("ENVIRONMENT") in ("test", "testing")
    base_name = os.path.basename(target)
    if is_testing and base_name in PROTECTED_DATABASES:
        return

    conn = sqlite3.connect(target)
    cursor = conn.cursor()

    # 1. Create discovery_runs table if missing
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_runs'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE discovery_runs (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                website_url VARCHAR(512) NOT NULL,
                final_url VARCHAR(512),
                root_domain VARCHAR(256) NOT NULL,
                status VARCHAR(64) DEFAULT 'DISCOVERING',
                failure_reason VARCHAR(64),
                error_message TEXT,
                crawled_pages_count INTEGER DEFAULT 0,
                discovered_urls_count INTEGER DEFAULT 0,
                crawl_duration_seconds FLOAT DEFAULT 0.0,
                created_by VARCHAR(256),
                started_at DATETIME,
                completed_at DATETIME,
                FOREIGN KEY (organization_id) REFERENCES enterprise_profile (id) ON DELETE CASCADE
            )
        """)
    else:
        cursor.execute("PRAGMA table_info(discovery_runs)")
        rcols = [row[1] for row in cursor.fetchall()]
        for col_name, col_type in [
            ("final_url", "VARCHAR(512)"),
            ("failure_reason", "VARCHAR(64)"),
            ("discovered_urls_count", "INTEGER DEFAULT 0"),
            ("crawl_duration_seconds", "FLOAT DEFAULT 0.0")
        ]:
            if col_name not in rcols:
                cursor.execute(f"ALTER TABLE discovery_runs ADD COLUMN {col_name} {col_type}")

    # 2. Add discovery_run_id to discovered_facts if table exists and column missing
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovered_facts'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(discovered_facts)")
        cols = [row[1] for row in cursor.fetchall()]
        if cols and "discovery_run_id" not in cols:
            cursor.execute("ALTER TABLE discovered_facts ADD COLUMN discovery_run_id VARCHAR(36)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    migrate_db()
    print("DiscoveryRun schema migration completed.")
