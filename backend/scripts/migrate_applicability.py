import sys
sys.path.insert(0, '.')
from app.core.database import engine, Base
from app.models.domain import RegulatoryApplicabilityAssessment

def migrate():
    Base.metadata.create_all(bind=engine, tables=[RegulatoryApplicabilityAssessment.__table__])
    print("Migrated: regulatory_applicability_assessments table created successfully.")

if __name__ == "__main__":
    migrate()
