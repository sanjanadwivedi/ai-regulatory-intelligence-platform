import sys
import io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.core.database import SessionLocal
from app.models.domain import Regulation

db = SessionLocal()
reg = db.query(Regulation).filter(Regulation.id == 'reg-cyber-2026').first()
if reg:
    print('=== REG-CYBER-2026 CONTENT TEXT ===')
    print(reg.content_text)
    print('\n=== SECTIONS & REQUIREMENTS ===')
    for s in reg.sections:
        print(f'Section: {s.section_number} - {s.title}')
        for ob in s.obligations:
            print(f'  Obligation: {ob.summary}')
            for req in ob.requirements:
                print(f'    Requirement: {req.requirement_text} | Citation: {req.statutory_reference} | Span: {req.source_span}')
db.close()
