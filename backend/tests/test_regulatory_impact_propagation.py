import pytest
import datetime
import uuid
from sqlalchemy.orm import Session

from app.models.domain import (
    Base,
    EnterpriseProfile,
    EnterpriseUser,
    Regulation,
    RegulatoryChange,
    DocumentVersion,
    RegulatoryApplicabilityAssessment,
    RegulatoryObligation,
    ObligationControlMapping,
    InternalControl,
    ComplianceTask,
    RegulatoryObligationImpact
)
from app.services.regulatory_impact_service import propagate_change_impact



@pytest.fixture
def test_org(db_session: Session):
    org_id = str(uuid.uuid4())
    org = EnterpriseProfile(id=org_id, organization_name="Test Org", industry_sector="Finance")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture
def other_org(db_session: Session):
    org_id = str(uuid.uuid4())
    org = EnterpriseProfile(id=org_id, organization_name="Other Org", industry_sector="Healthcare")
    db_session.add(org)
    db_session.commit()
    return org

@pytest.fixture
def setup_regulation(db_session: Session):
    reg_id = str(uuid.uuid4())
    reg = Regulation(
        id=reg_id,
        title="Test Reg", authority="Authority",
        publication_date=datetime.date.today(), sector="Finance", region="US",
        content_text="Content"
    )
    db_session.add(reg)
    db_session.commit()

    ver1 = DocumentVersion(regulation_id=reg.id, version_no=1, content_text="Content")
    db_session.add(ver1)
    db_session.commit()

    ver2 = DocumentVersion(regulation_id=reg.id, version_no=2, content_text="New Content")
    db_session.add(ver2)
    db_session.commit()

    change = RegulatoryChange(
        regulation_id=reg.id, previous_version_id=ver1.id, new_version_id=ver2.id,
        change_type="UPDATED", detected_by="system", content_hash_after="123"
    )
    db_session.add(change)
    db_session.commit()

    return reg, change

def test_non_applicable_regulation(db_session: Session, test_org, setup_regulation):
    reg, change = setup_regulation

    assessment = RegulatoryApplicabilityAssessment(
        organization_id=test_org.id,
        regulation_id=reg.id,
        status="NOT_APPLICABLE",
        rationale="Not applicable"
    )
    db_session.add(assessment)
    db_session.commit()

    result = propagate_change_impact(db_session, change.id, test_org.id, "System")
    assert result["impact_status"] == "NOT_AFFECTED"
    assert result["summary"]["obligations_affected"] == 0

    impacts = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts) == 0

    db_session.refresh(assessment)
    assert assessment.status == "NOT_APPLICABLE"

def test_applicable_zero_obligations(db_session: Session, test_org, setup_regulation):
    reg, change = setup_regulation

    assessment = RegulatoryApplicabilityAssessment(
        organization_id=test_org.id,
        regulation_id=reg.id,
        status="APPLICABLE",
        rationale="Applicable"
    )
    db_session.add(assessment)
    db_session.commit()

    result = propagate_change_impact(db_session, change.id, test_org.id, "System")
    
    assert result["impact_status"] == "REQUIRES_HUMAN_REVIEW"
    assert result["mapping_gap"] is True
    assert result["summary"]["obligations_affected"] == 0
    assert result["summary"]["human_review_required"] == 1
    assert "no actionable obligations" in result["reason"]

    impacts = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts) == 0

    db_session.refresh(assessment)
    assert assessment.status == "APPLICABLE"

def test_applicable_with_obligations(db_session: Session, test_org, setup_regulation):
    reg, change = setup_regulation

    assessment = RegulatoryApplicabilityAssessment(
        organization_id=test_org.id,
        regulation_id=reg.id,
        status="APPLICABLE",
        rationale="Applicable"
    )
    db_session.add(assessment)
    db_session.commit()

    ob1 = RegulatoryObligation(
        regulation_id=reg.id,
        organization_id=test_org.id,
        applicability_assessment_id=assessment.id,
        obligation_code="OBL-1",
        title="Ob 1",
        description="Desc",
        obligation_type="REPORTING",
        source_citation="Section 1",
        status="ACTIVE"
    )
    db_session.add(ob1)
    db_session.commit()
    
    ctrl = InternalControl(
        organization_id=test_org.id,
        control_code="CTRL-1",
        name="Control",
        description="Desc",
        category="Tech",
        owner_department="IT",
        status="IMPLEMENTED"
    )
    db_session.add(ctrl)
    db_session.commit()
    
    mapping = ObligationControlMapping(
        organization_id=test_org.id,
        obligation_id=ob1.id,
        control_id=ctrl.id,
        active=1
    )
    db_session.add(mapping)
    db_session.commit()
    
    task = ComplianceTask(
        regulation_id=reg.id,
        organization_id=test_org.id,
        regulatory_obligation_id=ob1.id,
        control_id=ctrl.id,
        title="Task",
        assignee="User",
        reviewer="Manager",
        status="OPEN"
    )
    db_session.add(task)
    db_session.commit()

    result = propagate_change_impact(db_session, change.id, test_org.id, "System")
    assert result["impact_status"] == "POTENTIALLY_AFFECTED"
    assert result["summary"]["obligations_affected"] == 1
    assert result["summary"]["controls_affected"] == 1
    assert result["summary"]["tasks_affected"] == 1
    assert result["mapping_gap"] is False

    impacts = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts) == 1
    assert impacts[0].obligation_id == ob1.id
    assert impacts[0].impact_status == "POTENTIALLY_AFFECTED"

    db_session.refresh(ob1)
    assert ob1.status == "ACTIVE"
    db_session.refresh(ctrl)
    assert ctrl.status == "IMPLEMENTED"
    db_session.refresh(task)
    assert task.status == "OPEN"

def test_tenant_isolation_propagation(db_session: Session, test_org, other_org, setup_regulation):
    reg, change = setup_regulation
    
    assessment = RegulatoryApplicabilityAssessment(
        organization_id=test_org.id,
        regulation_id=reg.id,
        status="APPLICABLE",
        rationale="Applicable"
    )
    db_session.add(assessment)
    db_session.commit()
    
    ob1 = RegulatoryObligation(
        regulation_id=reg.id,
        organization_id=test_org.id,
        applicability_assessment_id=assessment.id,
        obligation_code="OBL-1",
        title="Ob 1",
        description="Desc",
        obligation_type="REPORTING",
        source_citation="Section 1",
        status="ACTIVE"
    )
    db_session.add(ob1)
    db_session.commit()
    
    result = propagate_change_impact(db_session, change.id, other_org.id, "System")
    assert result["impact_status"] == "NOT_AFFECTED" 
    
    impacts = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=other_org.id).all()
    assert len(impacts) == 0

    impacts = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts) == 0

def test_idempotency_propagation(db_session: Session, test_org, setup_regulation):
    reg, change = setup_regulation

    assessment = RegulatoryApplicabilityAssessment(
        organization_id=test_org.id,
        regulation_id=reg.id,
        status="APPLICABLE",
        rationale="Applicable"
    )
    db_session.add(assessment)
    db_session.commit()

    ob1 = RegulatoryObligation(
        regulation_id=reg.id,
        organization_id=test_org.id,
        applicability_assessment_id=assessment.id,
        obligation_code="OBL-1",
        title="Ob 1",
        description="Desc",
        obligation_type="REPORTING",
        source_citation="Section 1",
        status="ACTIVE"
    )
    db_session.add(ob1)
    db_session.commit()
    
    propagate_change_impact(db_session, change.id, test_org.id, "System")
    impacts1 = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts1) == 1
    
    propagate_change_impact(db_session, change.id, test_org.id, "System")
    impacts2 = db_session.query(RegulatoryObligationImpact).filter_by(organization_id=test_org.id).all()
    assert len(impacts2) == 1
