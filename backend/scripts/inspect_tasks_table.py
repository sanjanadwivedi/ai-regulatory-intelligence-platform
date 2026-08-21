import sys
sys.path.insert(0, '.')
from app.core.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
cols = inspector.get_columns('compliance_tasks')
print('=== COMPLIANCE_TASKS TABLE COLUMNS ===')
for c in cols:
    print(f"  {c['name']}: {c['type']} (nullable={c['nullable']})")
