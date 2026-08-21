import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find instantiations of RegulatoryApplicabilityAssessment(
    # and add organization_id=profile.id if not present
    content = re.sub(
        r'(RegulatoryApplicabilityAssessment\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )

    # Same for RegulatoryObligation
    content = re.sub(
        r'(RegulatoryObligation\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )

    # Same for ComplianceTask
    content = re.sub(
        r'(ComplianceTask\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )

    # Same for ComplianceTaskEvidence
    content = re.sub(
        r'(ComplianceTaskEvidence\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )

    with open(filepath, 'w') as f:
        f.write(content)

fix_file(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_monitoring.py")
fix_file(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_readiness_audit.py")
fix_file(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_discovery_isolation.py")
