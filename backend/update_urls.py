import sys
from app.core.database import SessionLocal
from app.models.domain import Regulation

import datetime

sys.stdout.reconfigure(encoding='utf-8')

def update_source_urls():
    db = SessionLocal()
    regs = db.query(Regulation).all()
    print(f"Updating {len(regs)} database regulations...")
    for r in regs:
        auth_lower = (r.authority or '').lower()
        title_lower = (r.title or '').lower()
        sector_lower = (r.sector or '').lower()

        if r.id == 'reg-scan-rbi-2026':
            r.title = '[FLAGGED SCAN] Reserve Bank of India – Special Rupee Vostro Accounts (SRVAs)'
            r.doc_number = 'RBI/2026-2027/203 A.P. (DIR Series) Circular No.19'
            r.publication_date = datetime.date(2026, 7, 17)

        if r.id == 'reg-cyber-2026':
            r.publication_date = datetime.date(2026, 7, 31)

        # 1. Cybersecurity & IT (CERT-In / PIB / MeitY)
        if (
            'cert' in auth_lower or
            'pib' in auth_lower or
            'meity' in auth_lower or
            'cyber' in title_lower
        ):
            r.source_url = 'https://pib.gov.in/PressReleasePage.aspx?PRID=1820904'

        # 2. Reserve Bank of India (RBI) — Title-Specific Notification Links
        elif (
            'rbi' in auth_lower or
            'reserve bank' in auth_lower or
            'kyc' in title_lower or
            'master direction' in title_lower or
            'remittance' in title_lower or
            'banking' in sector_lower
        ):
            if 'communication policy' in title_lower:
                r.source_url = 'https://www.rbi.org.in/Scripts/CommunicationPolicy.aspx'
            elif 'remittance' in title_lower or 'foreign exchange' in title_lower or 'v-cip audit' in title_lower or 'lrs' in title_lower or 'vostro' in title_lower or 'flagged scan' in title_lower or 'srva' in title_lower:
                r.source_url = 'https://www.rbi.org.in/Scripts/NotificationUser.aspx'
            elif 'sources of information' in title_lower or 'circular index' in title_lower:
                r.source_url = 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx'
            elif 'kyc' in title_lower or 'know your customer' in title_lower or 'v-cip' in title_lower:
                r.source_url = 'https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12093'
            else:
                r.source_url = 'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx'


        # 3. Healthcare & Life Sciences (HIPAA / HHS)
        elif (
            'hhs' in auth_lower or
            'hipaa' in auth_lower or
            'hipaa' in title_lower or
            'patient health' in title_lower or
            'phi' in title_lower or
            'health' in sector_lower
        ):
            r.source_url = 'https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164'

        # 4. Capital Markets & Securities (SEC / FINRA)
        elif (
            'sec' in auth_lower or
            'finra' in auth_lower or
            'trading' in title_lower or
            'algorithmic' in title_lower or
            'securities' in sector_lower
        ):
            r.source_url = 'https://www.finra.org/rules-guidance/rulebooks/finra-rules'

        else:
            r.source_url = 'https://pib.gov.in/PressReleasePage.aspx?PRID=1820904'

        print(f"Reg {r.id[:12]} | title='{r.title[:40]}' -> source_url='{r.source_url}'")

    db.commit()
    print("Database source URLs successfully hardened with title-specific links!")

if __name__ == "__main__":
    update_source_urls()
