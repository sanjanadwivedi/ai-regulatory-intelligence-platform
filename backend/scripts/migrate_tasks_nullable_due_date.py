import sys
sys.path.insert(0, '.')
from app.core.database import engine
from sqlalchemy import text

def make_due_date_nullable():
    with engine.connect() as conn:
        print("Migrating compliance_tasks table to allow NULL due_date...")
        
        # 1. Create temporary table with nullable due_date and all new columns
        conn.execute(text("""
            CREATE TABLE compliance_tasks_new (
                id VARCHAR(36) PRIMARY KEY,
                regulation_id VARCHAR(36) NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
                organization_id VARCHAR(36) REFERENCES enterprise_profile(id) ON DELETE CASCADE,
                regulatory_obligation_id VARCHAR(36) REFERENCES regulatory_obligations(id) ON DELETE CASCADE,
                control_code VARCHAR(64),
                title VARCHAR(256) NOT NULL,
                description TEXT,
                assignee VARCHAR(128) NOT NULL,
                reviewer VARCHAR(128) NOT NULL,
                priority VARCHAR(32) DEFAULT 'HIGH',
                status VARCHAR(64) DEFAULT 'NEEDS_REVIEW',
                due_date DATE,
                responsible_function VARCHAR(128),
                due_rule VARCHAR(256),
                frequency VARCHAR(64),
                source_citation VARCHAR(256),
                authoritative_source_url VARCHAR(1024),
                regulatory_evidence_refs JSON,
                organization_evidence_refs JSON,
                operational_evidence JSON,
                engine_version VARCHAR(32) DEFAULT 'v1.0.0-deterministic',
                legal_signoff_by VARCHAR(128),
                executive_approval_by VARCHAR(128),
                digital_signature_hash VARCHAR(128),
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        
        # 2. Copy all data from existing compliance_tasks into compliance_tasks_new
        conn.execute(text("""
            INSERT INTO compliance_tasks_new (
                id, regulation_id, organization_id, regulatory_obligation_id,
                control_code, title, description, assignee, reviewer,
                priority, status, due_date, responsible_function, due_rule,
                frequency, source_citation, authoritative_source_url,
                regulatory_evidence_refs, organization_evidence_refs,
                operational_evidence, engine_version, legal_signoff_by,
                executive_approval_by, digital_signature_hash, created_at, updated_at
            )
            SELECT 
                id, regulation_id, organization_id, regulatory_obligation_id,
                control_code, title, description, assignee, reviewer,
                priority, status, due_date, responsible_function, due_rule,
                frequency, source_citation, authoritative_source_url,
                regulatory_evidence_refs, organization_evidence_refs,
                operational_evidence, engine_version, legal_signoff_by,
                executive_approval_by, digital_signature_hash, created_at, updated_at
            FROM compliance_tasks
        """))
        
        # 3. Drop old table and rename new table
        conn.execute(text("DROP TABLE compliance_tasks"))
        conn.execute(text("ALTER TABLE compliance_tasks_new RENAME TO compliance_tasks"))
        conn.commit()
        print("Success: compliance_tasks table migrated with due_date NULLABLE and all rows preserved.")

if __name__ == "__main__":
    make_due_date_nullable()
