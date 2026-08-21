import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.core.database import SessionLocal
from app.models.domain import Regulation, Section

db = SessionLocal()
regs = db.query(Regulation).all()
for r in regs:
    print(f'=== {r.id} ===')
    print(f'  Title: {r.title}')
    print(f'  Authority: {r.authority}')
    print(f'  Region: {r.region}')
    print(f'  Sector: {r.sector}')
    print(f'  Status: {r.status}')
    print(f'  Effective: {r.effective_date}')
    source = r.source_url or 'None'
    print(f'  Source URL: {source}')
    content = r.content_text or ''
    print(f'  Content length: {len(content)} chars')
    # Key: check if scope/applicability language is in content
    scope_keywords = ['applies to', 'applicable to', 'covered entity', 'shall apply', 'this direction', 'scope', 'every body corporate', 'service provider', 'intermediary']
    found_scope = [kw for kw in scope_keywords if kw.lower() in content.lower()]
    print(f'  Scope keywords found: {found_scope}')
    # Number of extracted sections
    sections = [s for s in r.sections]
    print(f'  Sections in DB: {len(sections)}')
    print()
db.close()
