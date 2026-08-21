"""
Development-only script to set the organization to any test state.

Usage:
  python scripts/reset_organization.py

Modes:
  1. SETUP_REQUIRED    - profile row exists, discovery_status=UNINITIALIZED
  2. SETUP_IN_PROGRESS - profile row exists, discovery_status=REVIEW_PENDING
  3. SETUP_COMPLETE    - profile row exists, discovery_status=CONFIRMED
  4. NO PROFILE (404)  - no row in DB, API returns 404

WARNING: Development tool only. Never expose in production.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.domain import EnterpriseProfile

MODES = {
    '1': ('SETUP_REQUIRED    — shows Discover Your Organization (UNINITIALIZED)', 'UNINITIALIZED'),
    '2': ('SETUP_IN_PROGRESS — shows Discover Your Organization (REVIEW_PENDING)', 'REVIEW_PENDING'),
    '3': ('SETUP_COMPLETE    — shows Compliance Overview         (CONFIRMED)',      'CONFIRMED'),
    '4': ('NO PROFILE (404)  — shows Discover Your Organization  (no DB row)',      None),
}

def set_org_state(discovery_status):
    db = SessionLocal()
    try:
        if discovery_status is None:
            deleted = 0
            for p in db.query(EnterpriseProfile).all():
                db.delete(p)
                deleted += 1
            db.commit()
            print(f"Deleted {deleted} profile(s). GET /enterprise/profile now returns 404.")
        else:
            profile = db.query(EnterpriseProfile).first()
            if profile:
                profile.discovery_status = discovery_status
                db.commit()
                print(f"Updated profile '{profile.organization_name}': discovery_status = {discovery_status}")
            else:
                import datetime
                profile = EnterpriseProfile(
                    organization_name='Test Organization',
                    industry_sector='General Compliance',
                    discovery_status=discovery_status,
                    created_at=datetime.datetime.utcnow(),
                    updated_at=datetime.datetime.utcnow(),
                )
                db.add(profile)
                db.commit()
                print(f"Created placeholder profile: discovery_status = {discovery_status}")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("\nDevelopment Organization State Tester")
    print("======================================")
    for key, (label, _) in MODES.items():
        print(f"  {key}. {label}")
    print()
    choice = input("Select state to set (1-4): ").strip()

    if choice not in MODES:
        print("Invalid choice. Exiting.")
        sys.exit(1)

    label, discovery_status = MODES[choice]
    confirm = input(f"Set organization to: '{label}' ? (y/n): ")
    if confirm.lower() == 'y':
        set_org_state(discovery_status)
    else:
        print("Cancelled.")
