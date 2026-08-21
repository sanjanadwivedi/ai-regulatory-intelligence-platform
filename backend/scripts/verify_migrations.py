import os
import sys

# Change DB URL to an in-memory or isolated DB for testing migrations
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_migrations.db"

# Remove existing test DB if any
if os.path.exists("./test_migrations.db"):
    os.remove("./test_migrations.db")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import Base, engine, SessionLocal
import app.models.domain

import subprocess

def verify_migrations():
    print("Initializing test database...")
    Base.metadata.create_all(bind=engine)
    print("Base metadata created.")

    print("Running migration scripts...")
    scripts = [
        "migrate_discovery_run.py",
        "migrate_applicability.py",
        "migrate_obligations.py",
        "migrate_tasks_nullable_due_date.py",
        "migrate_task_provenance.py",
        "migrate_compliance_execution.py",
        "migrate_compliance_monitoring.py",
        "migrate_compliance_intelligence.py"
    ]
    
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./test_migrations.db"

    for script_name in scripts:
        print(f"Executing {script_name}...")
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        try:
            result = subprocess.run([sys.executable, script_path], env=env, check=True, capture_output=True, text=True)
            print(f"  [OK] {script_name} succeeded.")
        except subprocess.CalledProcessError as e:
            print(f"  [ERROR] {script_name} failed: {e.stderr}")
            return 1
            
    print("[PASS] All migrations executed successfully on a clean database.")
    
    # Cleanup
    engine.dispose()
    if os.path.exists("./test_migrations.db"):
        try:
            os.remove("./test_migrations.db")
        except:
            pass
    return 0

if __name__ == "__main__":
    sys.exit(verify_migrations())
