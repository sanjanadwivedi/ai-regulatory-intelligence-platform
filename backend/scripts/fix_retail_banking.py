import os
import sys
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.database import SessionLocal
from app.models.domain import EnterpriseProfile

def normalize_and_dedup(items):
    if not items:
        return []
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        normalized = re.sub(r'\s+', ' ', item.strip().lower())
        if normalized not in seen:
            seen.add(normalized)
            result.append(item.strip())
    return result

def fix_retail_banking():
    db = SessionLocal()
    try:
        profiles = db.query(EnterpriseProfile).all()
        for profile in profiles:
            changed = False
            
            # Deduplicate fields
            for field in ['business_activities', 'products_services', 'locations', 'departments', 'licenses']:
                val = getattr(profile, field)
                if val:
                    new_val = normalize_and_dedup(val)
                    
                    # Remove Retail Banking from NEC India
                    if field == 'business_activities' and profile.organization_name == 'NEC India':
                        new_val = [x for x in new_val if x.lower() != 'retail banking']
                        
                    if new_val != val:
                        setattr(profile, field, new_val)
                        changed = True
            
            if changed:
                db.commit()
                print(f"Fixed profile: {profile.organization_name}")
                
        print("Data integrity fix completed.")
    finally:
        db.close()

if __name__ == "__main__":
    fix_retail_banking()
