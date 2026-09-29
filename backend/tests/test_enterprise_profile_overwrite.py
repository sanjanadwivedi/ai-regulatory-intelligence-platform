import pytest
from sqlalchemy.orm import Session
from app.models.domain import EnterpriseProfile
import uuid

# Replicate the frontend's hardcoded industry mapping
INDUSTRIES = {
    'Technology & Cloud Security (SOC2 / GDPR)': {
        'id': 'Technology & Cloud Security (SOC2 / GDPR)',
        'depts': ['Information Security (CISO)', 'Data Protection Office (DPO)', 'DevOps Infrastructure', 'Legal Counsel']
    },
    'Banking & Financial Services': {
        'id': 'Banking & Financial Services',
        'depts': ['Retail Banking Ops', 'AML & CDD Compliance', 'IT Infrastructure & Security', 'Legal Counsel']
    }
}

def simulate_frontend_payload(current_profile_depts, selected_industry):
    """
    Simulates the fixed frontend logic in EnterpriseSetupModal.tsx:
    const deptsToSave = (currentProfile?.departments && currentProfile.departments.length > 0)
        ? currentProfile.departments
        : currentObj.depts;
    """
    current_obj = INDUSTRIES.get(selected_industry)
    if current_profile_depts and len(current_profile_depts) > 0:
        return current_profile_depts
    return current_obj['depts']

@pytest.fixture
def db_session_mock():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.domain import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_enterprise_profile_edit_preserves_departments(db_session_mock: Session):
    """
    Test that editing an existing profile preserves configured departments
    and does not blindly overwrite them with the industry sector default.
    """
    # 1. Setup existing profile
    org_id = str(uuid.uuid4())
    existing_depts = ["Information Security (CISO)", "Compliance & Risk Management", "Cloud Architecture"]
    
    profile = EnterpriseProfile(
        id=org_id,
        organization_name="HDFC Bank Ltd",
        industry_sector="Banking & Financial Services",
        departments=existing_depts,
        country="India"
    )
    db_session_mock.add(profile)
    db_session_mock.commit()

    # 2. Simulate User opening modal, leaving sector as Banking & Financial Services, and saving
    selected_industry = "Banking & Financial Services"
    payload_depts = simulate_frontend_payload(profile.departments, selected_industry)
    
    # Assert frontend generates the correct payload (preserves existing)
    assert payload_depts == existing_depts
    
    # 3. Apply to database (simulate API endpoint)
    profile.departments = payload_depts
    db_session_mock.commit()
    
    # Assert departments remain exactly the existing ones, not overwritten
    saved_profile = db_session_mock.query(EnterpriseProfile).filter_by(id=org_id).first()
    assert saved_profile.departments == ["Information Security (CISO)", "Compliance & Risk Management", "Cloud Architecture"]

def test_new_enterprise_profile_uses_fallback_mapping(db_session_mock: Session):
    """
    Test that a genuinely new profile with no departments configured
    will correctly use the auto-mapped fallback departments.
    """
    # 1. Setup new profile with no departments
    org_id = str(uuid.uuid4())
    profile = EnterpriseProfile(
        id=org_id,
        organization_name="New Bank",
        industry_sector="Banking & Financial Services",
        departments=[], # Empty
        country="US"
    )
    db_session_mock.add(profile)
    db_session_mock.commit()

    # 2. Simulate User opening modal and saving
    selected_industry = "Banking & Financial Services"
    payload_depts = simulate_frontend_payload(profile.departments, selected_industry)
    
    # Assert frontend generates the fallback payload
    expected_fallback = ['Retail Banking Ops', 'AML & CDD Compliance', 'IT Infrastructure & Security', 'Legal Counsel']
    assert payload_depts == expected_fallback
    
    # 3. Apply to database
    profile.departments = payload_depts
    db_session_mock.commit()
    
    saved_profile = db_session_mock.query(EnterpriseProfile).filter_by(id=org_id).first()
    assert saved_profile.departments == expected_fallback
