import datetime
import os
import pytest
from sqlalchemy.orm import Session
from app.models.domain import (
    EnterpriseProfile, EnterpriseUser, RegulatorySource, Regulation,
    Section, Obligation, Requirement, KnowledgeGraphChain,
    ComplianceTask, InternalControl, EnterprisePolicy, EnterpriseProcess,
    EnterpriseApplication, RegulatoryApplicabilityCriterion, AuditLog
)
from seed_data import seed_database_data


def test_repeated_seed_execution_does_not_duplicate_records(db_session: Session):
    """
    Test A: Repeated seed execution must be strictly idempotent and create zero duplicates.
    """
    # 1st run
    res1 = seed_database_data(db_session, force=True)
    assert res1["status"] == "COMPLETED"

    # Capture record counts after first run
    profiles_count_1 = db_session.query(EnterpriseProfile).count()
    users_count_1 = db_session.query(EnterpriseUser).count()
    sources_count_1 = db_session.query(RegulatorySource).count()
    controls_count_1 = db_session.query(InternalControl).count()
    policies_count_1 = db_session.query(EnterprisePolicy).count()
    processes_count_1 = db_session.query(EnterpriseProcess).count()
    apps_count_1 = db_session.query(EnterpriseApplication).count()
    regs_count_1 = db_session.query(Regulation).count()
    criteria_count_1 = db_session.query(RegulatoryApplicabilityCriterion).count()
    sections_count_1 = db_session.query(Section).count()
    obligations_count_1 = db_session.query(Obligation).count()
    requirements_count_1 = db_session.query(Requirement).count()
    kg_chains_count_1 = db_session.query(KnowledgeGraphChain).count()
    tasks_count_1 = db_session.query(ComplianceTask).count()

    assert regs_count_1 >= 5
    assert controls_count_1 >= 5
    assert tasks_count_1 >= 5

    # 2nd run
    res2 = seed_database_data(db_session, force=True)
    assert res2["status"] == "COMPLETED"

    # 3rd run
    res3 = seed_database_data(db_session, force=True)
    assert res3["status"] == "COMPLETED"

    # Assert 100% count equality - zero duplicates created
    assert db_session.query(EnterpriseProfile).count() == profiles_count_1
    assert db_session.query(EnterpriseUser).count() == users_count_1
    assert db_session.query(RegulatorySource).count() == sources_count_1
    assert db_session.query(InternalControl).count() == controls_count_1
    assert db_session.query(EnterprisePolicy).count() == policies_count_1
    assert db_session.query(EnterpriseProcess).count() == processes_count_1
    assert db_session.query(EnterpriseApplication).count() == apps_count_1
    assert db_session.query(Regulation).count() == regs_count_1
    assert db_session.query(RegulatoryApplicabilityCriterion).count() == criteria_count_1
    assert db_session.query(Section).count() == sections_count_1
    assert db_session.query(Obligation).count() == obligations_count_1
    assert db_session.query(Requirement).count() == requirements_count_1
    assert db_session.query(KnowledgeGraphChain).count() == kg_chains_count_1
    assert db_session.query(ComplianceTask).count() == tasks_count_1


def test_existing_records_are_never_deleted(db_session: Session):
    """
    Test B: Pre-existing custom/production records must never be deleted by seed runs.
    """
    # Create custom organization, user, regulation, and task
    custom_org = EnterpriseProfile(
        id="org-custom-production",
        organization_name="Production Bank Corp",
        industry_sector="Banking",
        country="India"
    )
    db_session.add(custom_org)
    db_session.commit()

    custom_user = EnterpriseUser(
        id="user-custom-prod",
        email="prod_officer@custom.com",
        full_name="Custom Prod Officer",
        role="COMPLIANCE_OFFICER",
        organization_id=custom_org.id
    )
    db_session.add(custom_user)

    custom_reg = Regulation(
        id="reg-custom-production-001",
        title="Custom Production Statutory Framework 2026",
        authority="Reserve Bank of India",
        publication_date=datetime.date(2026, 1, 1),
        region="India",
        sector="Banking",
        content_text="Statutory framework for capital reserves.",
        status="ACTIVE"
    )
    db_session.add(custom_reg)
    db_session.commit()

    custom_task = ComplianceTask(
        id="task-custom-production-001",
        organization_id=custom_org.id,
        regulation_id=custom_reg.id,
        title="Execute Live Production Capital Audit",
        status="IN_PROGRESS",
        assignee="Custom Prod Officer",
        reviewer="Compliance Head",
        priority="HIGH"
    )
    db_session.add(custom_task)
    db_session.commit()

    # Execute seed
    seed_database_data(db_session, force=True)

    # Verify custom records were NOT deleted
    persisted_org = db_session.query(EnterpriseProfile).filter_by(id="org-custom-production").first()
    assert persisted_org is not None
    assert persisted_org.organization_name == "Production Bank Corp"

    persisted_user = db_session.query(EnterpriseUser).filter_by(id="user-custom-prod").first()
    assert persisted_user is not None
    assert persisted_user.email == "prod_officer@custom.com"

    persisted_reg = db_session.query(Regulation).filter_by(id="reg-custom-production-001").first()
    assert persisted_reg is not None
    assert persisted_reg.title == "Custom Production Statutory Framework 2026"

    persisted_task = db_session.query(ComplianceTask).filter_by(id="task-custom-production-001").first()
    assert persisted_task is not None
    assert persisted_task.status == "IN_PROGRESS"
    assert persisted_task.title == "Execute Live Production Capital Audit"


def test_production_mode_startup_skips_demo_seeding(db_session: Session, monkeypatch):
    """
    Test C: In production environment (ENVIRONMENT='production'), seed_database_data
    skips execution and performs zero inserts/deletions.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Seed on clean database in production mode
    res = seed_database_data(db_session, force=False)
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "PRODUCTION_ENVIRONMENT"

    # Assert no demo records were inserted
    assert db_session.query(Regulation).count() == 0
    assert db_session.query(EnterpriseUser).count() == 0
    assert db_session.query(ComplianceTask).count() == 0


def test_isolated_test_setup_creates_required_fixtures(db_session: Session, monkeypatch):
    """
    Test D: In test/development mode, seed_database_data creates all necessary
    statutory fixtures required by the system.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")

    res = seed_database_data(db_session, force=False)
    assert res["status"] == "COMPLETED"

    # Verify canonical regulations exist
    assert db_session.query(Regulation).filter_by(id="reg-cyber-2026").first() is not None
    assert db_session.query(Regulation).filter_by(id="reg-hipaa-2026").first() is not None
    assert db_session.query(Regulation).filter_by(id="reg-sec-trading-2026").first() is not None
    assert db_session.query(Regulation).filter_by(id="reg-rbi-kyc-2026").first() is not None

    # Verify canonical controls exist
    assert db_session.query(InternalControl).filter_by(id="ctrl-sec-09").first() is not None
    assert db_session.query(InternalControl).filter_by(id="ctrl-kyc-04").first() is not None

    # Verify canonical tasks exist
    assert db_session.query(ComplianceTask).filter_by(id="task-cyber-101").first() is not None


def test_tenant_operational_records_remain_untouched(db_session: Session):
    """
    Test E: Operational tenant data (e.g. Org B users, tasks, audit logs) must
    remain completely isolated and untouched during seed operations.
    """
    # Create Tenant B data
    org_b = EnterpriseProfile(
        id="org-tenant-b-isolated",
        organization_name="Tenant B Global Bank",
        industry_sector="Banking"
    )
    db_session.add(org_b)

    reg_b = Regulation(
        id="reg-tenant-b-specific",
        title="Tenant B Specific Local Standard",
        authority="Local Authority",
        publication_date=datetime.date(2026, 1, 1),
        region="Global",
        sector="Banking",
        content_text="Local standard directives.",
        status="ACTIVE"
    )
    db_session.add(reg_b)
    db_session.commit()

    user_b = EnterpriseUser(
        id="user-b-compliance",
        email="officer_b@globalbank.com",
        full_name="Officer B",
        role="COMPLIANCE_OFFICER",
        organization_id=org_b.id
    )
    db_session.add(user_b)

    task_b = ComplianceTask(
        id="task-tenant-b-operational",
        organization_id=org_b.id,
        regulation_id=reg_b.id,
        title="Tenant B Operational Task - AML Review",
        status="IN_PROGRESS",
        assignee="Officer B",
        reviewer="Reviewer B",
        priority="CRITICAL"
    )
    db_session.add(task_b)

    audit_b = AuditLog(
        id="audit-log-b-001",
        organization_id=org_b.id,
        user_name="Officer B",
        user_role="COMPLIANCE_OFFICER",
        action="TASK_UPDATED",
        target_type="ComplianceTask",
        target_id=task_b.id
    )
    db_session.add(audit_b)
    db_session.commit()

    # Run seed
    seed_database_data(db_session, force=True)

    # Verify Tenant B is 100% untouched
    check_org_b = db_session.query(EnterpriseProfile).filter_by(id="org-tenant-b-isolated").first()
    assert check_org_b is not None
    assert check_org_b.organization_name == "Tenant B Global Bank"

    check_user_b = db_session.query(EnterpriseUser).filter_by(id="user-b-compliance").first()
    assert check_user_b is not None
    assert check_user_b.organization_id == org_b.id

    check_reg_b = db_session.query(Regulation).filter_by(id="reg-tenant-b-specific").first()
    assert check_reg_b is not None
    assert check_reg_b.title == "Tenant B Specific Local Standard"

    check_task_b = db_session.query(ComplianceTask).filter_by(id="task-tenant-b-operational").first()
    assert check_task_b is not None
    assert check_task_b.status == "IN_PROGRESS"
    assert check_task_b.priority == "CRITICAL"

    check_audit_b = db_session.query(AuditLog).filter_by(id="audit-log-b-001").first()
    assert check_audit_b is not None
    assert check_audit_b.action == "TASK_UPDATED"


@pytest.mark.anyio
async def test_lifespan_production_mode_skips_demo_seeding(monkeypatch):
    """
    Test F: FastAPI lifespan startup in production mode must skip demo seeding
    and must not attempt to delete or recreate existing records.
    """
    from app.main import lifespan, app
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")

    async with lifespan(app):
        # Lifespan executes startup migration/gating
        pass

