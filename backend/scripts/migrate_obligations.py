import sys
sys.path.insert(0, '.')
from app.core.database import engine, Base
from app.models.domain import RegulatoryObligation

def migrate():
    Base.metadata.create_all(bind=engine, tables=[RegulatoryObligation.__table__])
    print("Migrated: regulatory_obligations table created successfully.")

if __name__ == "__main__":
    migrate()
