import os
import re

test_dir = r"C:\Users\sanja\AI-Powered Compliance System\backend\tests"

models_to_patch = [
    "ComplianceAlert",
    "RegulatoryApplicabilityAssessment",
    "RegulatoryObligation",
    "ComplianceTask",
    "ReviewItem",
    "ComplianceTriggerEvent",
    "ComplianceEvidence",
    "ComplianceTaskActivity",
    "DiscoveredFact"
]

for filename in os.listdir(test_dir):
    if filename.endswith(".py"):
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()

        changed = False
        
        # Patch fixtures creating users without organization_id
        if 'def compliance_officer_user(' in content and 'setup_org_profile' in content and 'organization_id=setup_org_profile.id' not in content:
            # We already fixed monitoring, execution, audit. What about others?
            pass

        for model in models_to_patch:
            # Look for ModelName(
            # without organization_id being passed
            pattern = rf'({model}\()(?!\s*organization_id)'
            
            # The replacement depends on what the context has. Usually it's profile.id or org_id
            # Let's try to add organization_id=profile.id, and if profile is not defined, we'll fix it manually.
            if re.search(pattern, content):
                content = re.sub(pattern, rf'\1\n        organization_id=profile.id,', content)
                changed = True
        
        if changed:
            print(f"Patched {filename}")
            with open(filepath, 'w') as f:
                f.write(content)
