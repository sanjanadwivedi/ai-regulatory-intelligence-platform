import os
import re

test_dir = r"C:\Users\sanja\AI-Powered Compliance System\backend\tests"

for filename in os.listdir(test_dir):
    if not filename.endswith(".py"):
        continue
    filepath = os.path.join(test_dir, filename)
    with open(filepath, 'r') as f:
        content = f.read()

    changed = False

    # Fix auth_headers
    if "def auth_headers(" in content:
        if "user.organization_id = _active_prof.id" not in content:
            new_code = """    _active_prof = db_session.query(EnterpriseProfile).first()
    if _active_prof and user.organization_id != _active_prof.id:
        user.organization_id = _active_prof.id
        db_session.commit()
        db_session.refresh(user)
    token = create_access_token(user.id)"""
            content = re.sub(r'token\s*=\s*create_access_token\(user\.id\)', new_code, content)
            changed = True

    # Fix compliance_officer_user
    if "def compliance_officer_user(" in content:
        if "user.organization_id = _active_prof.id" not in content:
            # We want to replace the `return user` inside `compliance_officer_user` but it's hard with regex.
            # Let's replace the whole `return user` but ONLY the ones that have standard indentation.
            # Actually, `return user` is simple. Let's just do a blanket replace of `return user` with the sync code
            sync_code = """    _active_prof = db_session.query(EnterpriseProfile).first()
    if _active_prof and user.organization_id != _active_prof.id:
        user.organization_id = _active_prof.id
        db_session.commit()
        db_session.refresh(user)
    return user"""
            content = re.sub(r'(\s+)return user', r'\1' + sync_code.replace('\n', '\n\\1')[:-4] + 'return user', content)
            changed = True
            
    if changed:
        print(f"Patched users/auth in {filename}")
        with open(filepath, 'w') as f:
            f.write(content)
