import sys
sys.path.insert(0, '.')
from app.core.database import engine
from sqlalchemy import text, inspect

def migrate_compliance_execution():
    with engine.connect() as conn:
        print("Starting Compliance Execution & Monitoring database migration...")
        
        # 1. Check existing columns in compliance_tasks and regulatory_obligations
        inspector = inspect(engine)
        ob_cols = [c["name"] for c in inspector.get_columns("regulatory_obligations")]
        task_cols = [c["name"] for c in inspector.get_columns("compliance_tasks")]
        tables = inspector.get_table_names()

        # Add structured trigger metadata to regulatory_obligations if missing
        if "trigger_type" not in ob_cols:
            print("Adding trigger_type to regulatory_obligations...")
            conn.execute(text("ALTER TABLE regulatory_obligations ADD COLUMN trigger_type VARCHAR(64)"))
        if "trigger_offset_value" not in ob_cols:
            print("Adding trigger_offset_value to regulatory_obligations...")
            conn.execute(text("ALTER TABLE regulatory_obligations ADD COLUMN trigger_offset_value INTEGER"))
        if "trigger_offset_unit" not in ob_cols:
            print("Adding trigger_offset_unit to regulatory_obligations...")
            conn.execute(text("ALTER TABLE regulatory_obligations ADD COLUMN trigger_offset_unit VARCHAR(32)"))

        # Add execution and structured trigger columns to compliance_tasks if missing
        if "completed_at" not in task_cols:
            print("Adding completed_at to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN completed_at DATETIME"))
        if "completed_by" not in task_cols:
            print("Adding completed_by to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN completed_by VARCHAR(128)"))
        if "reopened_at" not in task_cols:
            print("Adding reopened_at to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN reopened_at DATETIME"))
        if "reopened_by" not in task_cols:
            print("Adding reopened_by to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN reopened_by VARCHAR(128)"))
        if "trigger_type" not in task_cols:
            print("Adding trigger_type to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN trigger_type VARCHAR(64)"))
        if "trigger_offset_value" not in task_cols:
            print("Adding trigger_offset_value to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN trigger_offset_value INTEGER"))
        if "trigger_offset_unit" not in task_cols:
            print("Adding trigger_offset_unit to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN trigger_offset_unit VARCHAR(32)"))
        if "trigger_event_id" not in task_cols:
            print("Adding trigger_event_id to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN trigger_event_id VARCHAR(36)"))
        if "trigger_timestamp" not in task_cols:
            print("Adding trigger_timestamp to compliance_tasks...")
            conn.execute(text("ALTER TABLE compliance_tasks ADD COLUMN trigger_timestamp DATETIME"))

        # 2. Create compliance_trigger_events table if not exists
        if "compliance_trigger_events" not in tables:
            print("Creating compliance_trigger_events table...")
            conn.execute(text("""
                CREATE TABLE compliance_trigger_events (
                    id VARCHAR(36) PRIMARY KEY,
                    organization_id VARCHAR(36) NOT NULL REFERENCES enterprise_profile(id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    event_timestamp DATETIME NOT NULL,
                    source VARCHAR(256) NOT NULL,
                    description TEXT NOT NULL,
                    event_metadata JSON,
                    created_by VARCHAR(128) NOT NULL,
                    created_at DATETIME
                )
            """))

        # 3. Create compliance_task_evidence table if not exists
        if "compliance_task_evidence" not in tables:
            print("Creating compliance_task_evidence table...")
            conn.execute(text("""
                CREATE TABLE compliance_task_evidence (
                    id VARCHAR(36) PRIMARY KEY,
                    task_id VARCHAR(36) NOT NULL REFERENCES compliance_tasks(id) ON DELETE CASCADE,
                    organization_id VARCHAR(36) REFERENCES enterprise_profile(id) ON DELETE CASCADE,
                    uploaded_by VARCHAR(128) NOT NULL,
                    uploader_role VARCHAR(64) NOT NULL,
                    evidence_type VARCHAR(64) NOT NULL,
                    file_name VARCHAR(256) NOT NULL,
                    file_url VARCHAR(1024),
                    description TEXT,
                    evidence_date DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

        # 4. Create compliance_task_activities table if not exists
        if "compliance_task_activities" not in tables:
            print("Creating compliance_task_activities table...")
            conn.execute(text("""
                CREATE TABLE compliance_task_activities (
                    id VARCHAR(36) PRIMARY KEY,
                    task_id VARCHAR(36) NOT NULL REFERENCES compliance_tasks(id) ON DELETE CASCADE,
                    organization_id VARCHAR(36) REFERENCES enterprise_profile(id) ON DELETE CASCADE,
                    actor_id VARCHAR(128),
                    actor_name VARCHAR(128) NOT NULL,
                    actor_role VARCHAR(64) NOT NULL,
                    activity_type VARCHAR(64) NOT NULL,
                    message TEXT NOT NULL,
                    activity_metadata JSON,
                    created_at DATETIME
                )
            """))

        conn.commit()
        print("Success: Compliance Execution & Monitoring database schema migrated successfully.")

if __name__ == "__main__":
    migrate_compliance_execution()
