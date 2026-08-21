import pytest
from app.services.compliance_alert_service import ComplianceAlertService
from app.models.domain import ComplianceAlert
from app.core.database import SessionLocal, Base, engine
from app.models.domain import EnterpriseProfile

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_alert_idempotency(db_session):
    profile = db_session.query(EnterpriseProfile).first()
    org_id = profile.id
    
    # Run monitoring once
    alerts1 = ComplianceAlertService.evaluate_and_sync_alerts(org_id, db_session)
    count1 = len(alerts1)
    
    # Run twice
    alerts2 = ComplianceAlertService.evaluate_and_sync_alerts(org_id, db_session)
    count2 = len(alerts2)
    assert count1 == count2, "Alert count should be idempotent on repeated monitoring"
    
    # Run ten times
    for _ in range(8):
        ComplianceAlertService.evaluate_and_sync_alerts(org_id, db_session)
        
    db_count = db_session.query(ComplianceAlert).filter(
        ComplianceAlert.organization_id == org_id, 
        ComplianceAlert.status == 'ACTIVE'
    ).count()
    assert db_count == count1, "Database active alert count must remain stable"
