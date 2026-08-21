import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find instantiations of ComplianceAlert(
    # and add organization_id=profile.id if not present
    content = re.sub(
        r'(ComplianceAlert\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )
    
    # Also for ComplianceTriggerEvent
    content = re.sub(
        r'(ComplianceTriggerEvent\()(?!\s*organization_id)',
        r'\1\n        organization_id=profile.id,',
        content
    )

    with open(filepath, 'w') as f:
        f.write(content)

fix_file(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_monitoring.py")
fix_file(r"C:\Users\sanja\AI-Powered Compliance System\backend\tests\test_compliance_execution.py")
