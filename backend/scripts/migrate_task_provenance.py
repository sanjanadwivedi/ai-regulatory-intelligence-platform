import sys
sys.path.insert(0, '.')
from app.core.database import engine
from sqlalchemy import text, inspect

def migrate():
    inspector = inspect(engine)
    existing_cols = {c['name'] for c in inspector.get_columns('compliance_tasks')}
    
    new_columns = [
        ("organization_id", "VARCHAR(36)"),
        ("regulatory_obligation_id", "VARCHAR(36)"),
        ("responsible_function", "VARCHAR(128)"),
        ("due_rule", "VARCHAR(256)"),
        ("frequency", "VARCHAR(64)"),
        ("source_citation", "VARCHAR(256)"),
        ("authoritative_source_url", "VARCHAR(1024)"),
        ("regulatory_evidence_refs", "JSON"),
        ("organization_evidence_refs", "JSON"),
        ("operational_evidence", "JSON"),
        ("engine_version", "VARCHAR(32) DEFAULT 'v1.0.0-deterministic'")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                print(f"Adding column {col_name} to compliance_tasks...")
                conn.execute(text(f"ALTER TABLE compliance_tasks ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            else:
                print(f"Column {col_name} already exists.")
        
    print("Migration complete: ComplianceTask schema upgraded with zero data loss.")

if __name__ == "__main__":
    migrate()
