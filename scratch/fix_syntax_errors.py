import re

# 1. test_compliance_intelligence.py: repeated keyword argument
with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_intelligence.py", 'r') as f:
    content = f.read()

# I patched `organization_id=profile.id` blindly, it probably had `organization_id=org_id` already
content = re.sub(r'organization_id=profile\.id,\s*organization_id=', 'organization_id=', content)
content = re.sub(r'organization_id=org_id,\s*organization_id=profile\.id,', 'organization_id=org_id,', content)
content = re.sub(r'organization_id=profile\.id,\s*organization_id=org_id,', 'organization_id=org_id,', content)

with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_intelligence.py", 'w') as f:
    f.write(content)

# 2. test_compliance_monitoring.py: IndentationError: unexpected indent
with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_monitoring.py", 'r') as f:
    content = f.read()

# We need to fix the indentation in the fixture
content = content.replace("    _active_prof = db_session.query(EnterpriseProfile).first()\n    if _active_prof and user.organization_id != _active_prof.id:\n        user.organization_id = _active_prof.id\n        db_session.commit()\n        db_session.refresh(user)\n    return user", 
                          "    _active_prof = db_session.query(EnterpriseProfile).first()\n    if _active_prof and user.organization_id != _active_prof.id:\n        user.organization_id = _active_prof.id\n        db_session.commit()\n        db_session.refresh(user)\n    return user")

# Wait, `test_compliance_monitoring.py` was at line 53
# Let's just restore compliance_officer_user in monitoring and write it properly
new_monitoring_fixture = """@pytest.fixture(scope="function")
def compliance_officer_user(db_session: Session, setup_org_profile):
    user = db_session.query(EnterpriseUser).filter(EnterpriseUser.role == "Compliance Officer").first()
    if not user:
        user = EnterpriseUser(
            organization_id=setup_org_profile.id, 
            full_name="Monitoring Officer",
            role="Compliance Officer",
            email="ciso@enterprise.com"
        )
        db_session.add(user)
    else:
        user.organization_id = setup_org_profile.id
    db_session.commit()
    db_session.refresh(user)
    return user"""

content = re.sub(r'@pytest\.fixture\(scope="function"\)\ndef compliance_officer_user\(db_session: Session, setup_org_profile\):.*?return user', new_monitoring_fixture, content, flags=re.DOTALL)

with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_monitoring.py", 'w') as f:
    f.write(content)


# 3. test_compliance_readiness_audit.py: return return user
with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_readiness_audit.py", 'r') as f:
    content = f.read()

content = content.replace("return return user", "return user")

with open(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_readiness_audit.py", 'w') as f:
    f.write(content)
