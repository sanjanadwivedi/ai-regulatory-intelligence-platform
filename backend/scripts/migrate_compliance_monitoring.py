import sqlite3
import os

DB_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "compliance_platform.db"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql_app.db"),
    os.path.join(os.getcwd(), "compliance_platform.db")
]

def run_migration():
    migrated_any = False
    for db_path in DB_PATHS:
        if os.path.exists(db_path):
            print(f"Migrating database at {db_path}...")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 1. Create compliance_alerts table if not exists
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS compliance_alerts (
                id VARCHAR(36) PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                alert_type VARCHAR(64) NOT NULL,
                severity VARCHAR(32) NOT NULL,
                title VARCHAR(256) NOT NULL,
                description TEXT NOT NULL,
                source_entity_type VARCHAR(64) NOT NULL,
                source_entity_id VARCHAR(36) NOT NULL,
                regulation_id VARCHAR(36),
                obligation_id VARCHAR(36),
                task_id VARCHAR(36),
                status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                evidence_refs JSON,
                created_at DATETIME NOT NULL,
                resolved_at DATETIME,
                resolved_by VARCHAR(128),
                resolution_notes TEXT,
                FOREIGN KEY (organization_id) REFERENCES enterprise_profile(id) ON DELETE CASCADE,
                FOREIGN KEY (regulation_id) REFERENCES regulations(id) ON DELETE SET NULL,
                FOREIGN KEY (obligation_id) REFERENCES regulatory_obligations(id) ON DELETE SET NULL,
                FOREIGN KEY (task_id) REFERENCES compliance_tasks(id) ON DELETE SET NULL
            );
            """)

            # 2. Add indexes for performance & idempotency
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_compliance_alerts_org_status 
            ON compliance_alerts(organization_id, status);
            """)

            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_alerts_idempotency
            ON compliance_alerts(organization_id, alert_type, source_entity_type, source_entity_id);
            """)

            conn.commit()
            conn.close()
            migrated_any = True
            print(f"Migration completed for {db_path}.")

    if not migrated_any:
        print("No local database files found to migrate directly; SQLAlchemy will create tables automatically on start.")

if __name__ == "__main__":
    run_migration()
