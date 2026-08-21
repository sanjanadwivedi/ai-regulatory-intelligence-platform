import sys
import os
sys.path.insert(0, os.path.abspath("."))
import urllib.request
import json
from app.core.security import create_access_token
from app.core.database import SessionLocal
from app.models.domain import EnterpriseUser

db = SessionLocal()
u = db.query(EnterpriseUser).first()
token = create_access_token(u.id)

req = urllib.request.Request('http://127.0.0.1:8000/api/v1/discovery/facts?status=ALL', headers={
    'Authorization': f'Bearer {token}'
})

resp = urllib.request.urlopen(req)
facts = json.loads(resp.read().decode())

print(f'Returned {len(facts)} facts for active discovery review:')
for f in facts:
    print(f' - [{f["status"]}] {f["fact_type"]}: {f["fact_value"]} (Conf: {f["confidence"]})')
    print(f'   Source: {f["source_url"]}')
    print(f'   Evidence: "{f["snippet"][:100]}..."')

db.close()
