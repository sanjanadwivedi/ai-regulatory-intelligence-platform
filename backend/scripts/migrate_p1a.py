import sqlite3
import os
import sys

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} - not found.")
        return

    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Idempotency Check
    c.execute("PRAGMA table_info(compliance_tasks)")
    columns = [row['name'] for row in c.fetchall()]
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # 3. Add Columns
        if "assignee_id" not in columns:
            print("  Adding assignee_id...")
            c.execute("ALTER TABLE compliance_tasks ADD COLUMN assignee_id VARCHAR(36)")
            
        if "reviewer_id" not in columns:
            print("  Adding reviewer_id...")
            c.execute("ALTER TABLE compliance_tasks ADD COLUMN reviewer_id VARCHAR(36)")
            
        if "completion_signature" not in columns:
            print("  Adding completion_signature...")
            c.execute("ALTER TABLE compliance_tasks ADD COLUMN completion_signature VARCHAR(256)")
            
        # 4. Deterministic Mapping
        # We only update if there is exactly 1 match in the same organization
        print("  Backfilling assignee_id where deterministic match exists...")
        c.execute("""
            UPDATE compliance_tasks
            SET assignee_id = (
                SELECT id 
                FROM enterprise_users 
                WHERE full_name = compliance_tasks.assignee 
                  AND organization_id = compliance_tasks.organization_id
            )
            WHERE assignee_id IS NULL 
              AND (
                SELECT COUNT(*) 
                FROM enterprise_users 
                WHERE full_name = compliance_tasks.assignee 
                  AND organization_id = compliance_tasks.organization_id
              ) = 1
        """)
        
        # 5. Check mapping results
        c.execute("SELECT COUNT(*) FROM compliance_tasks WHERE assignee_id IS NOT NULL")
        mapped = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM compliance_tasks WHERE assignee_id IS NULL")
        unmapped = c.fetchone()[0]
        
        print(f"  Migration successful! Mapped: {mapped}, Unmapped (legacy): {unmapped}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  FAILED: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    dbs = [
        "compliance_platform.db",
        "compliance_platform_browser_audit.db",
        "compliance_platform_test6.db",
        "pytest_test_only.db"
    ]
    for db in dbs:
        migrate_db(db)
