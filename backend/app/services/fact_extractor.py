import logging
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple
from app.services.discovery_crawler import DiscoveredPage

logger = logging.getLogger("compliance_platform.fact_extractor")

# High-precision entity and domain dictionaries
COMPANY_NAME_PATTERNS = [
    r"([A-Z][A-Za-z0-9\s&]+(?:Bank|Financial Services|Securities|Technologies|Technology|Corporation|Corp|India|Solutions|Systems|Ltd|Limited|LLC|Inc|PLC))",
    r"Welcome to ([A-Z][A-Za-z0-9\s&]+)",
    r"About ([A-Z][A-Za-z0-9\s&]+)"
]

BUSINESS_ACTIVITIES = {
    "ICT & Digital Transformation Solutions": [
        r"\bict services?\b", r"\bdigital transformation\b", r"\bit consulting\b",
        r"\bsystems integration\b", r"\benterprise it solutions\b"
    ],
    "AI & Video Analytics Solutions": [
        r"\bai video analytics\b", r"\bvideo analytics\b", r"\bartificial intelligence solutions\b",
        r"\bmachine learning solutions\b", r"\bcomputer vision solutions\b"
    ],
    "Smart Cities & IoT Infrastructure": [
        r"\bsmart factory\b", r"\biot solutions\b", r"\bsmart cities?\b",
        r"\bindustrial iot\b", r"\bconnected infrastructure\b"
    ],
    "Digital Identity & Biometrics": [
        r"\bdigital identity\b", r"\bdigital id\b", r"\bbiometrics?\b",
        r"\bbiometric identification\b", r"\bface recognition\b",
        r"\bidentity verification\b", r"\bbiometric onboarding\b"
    ],
    "Cloud & Technology Infrastructure": [
        r"\bcloud infrastructure\b", r"\bsaas platform\b", r"\benterprise software\b",
        r"\bcybersecurity services?\b", r"\bdata center solutions\b", r"\bsoftware-defined networking\b"
    ],
    "Retail Banking": [
        r"\bretail bank(?:ing)?\b", r"\bconsumer bank(?:ing)?\b", r"\bchecking account", r"\bsavings account"
    ],
    "Corporate & Commercial Lending": [
        r"\bcorporate lending\b", r"\bcommercial lending\b", r"\bwholesale bank(?:ing)?\b", r"\bworking capital loans\b"
    ],
    "Digital Lending & Micro-Credit": [
        r"\bdigital lending\b", r"\binstant personal loan", r"\bfintech lending\b"
    ],
    "Payment Aggregation & Gateways": [
        r"\bpayment gateway operator\b", r"\bpayment aggregator\b", r"\bmerchant acquire\b"
    ],
    "Wealth & Asset Management": [
        r"\bwealth management services?\b", r"\bprivate wealth management\b",
        r"\bportfolio management services?\b", r"\bmutual funds distribution\b"
    ],
    "Card Issuance & Credit Cards": [
        r"\bcredit card issuance\b", r"\bissue credit cards?\b", r"\bco-branded credit card"
    ],
    "Algorithmic & Securities Trading": [
        r"\balgorithmic trading\b", r"\bmarket making\b", r"\bequity brokerage\b", r"\bsecurities brokerage\b"
    ],
    "Insurance & Bancassurance": [
        r"\blife insurance underwriting\b", r"\bgeneral insurance provider\b", r"\bbancassurance distributor\b"
    ]
}

PRODUCTS_SERVICES = {
    "AI Video Analytics & Urban Monitoring": [
        r"\bvideo analytics\b", r"\burban monitoring\b", r"\bsurveillance analytics\b", r"\bmi-eye\b"
    ],
    "Digital ID & Biometric Verification Portal": [
        r"\bdigital id\b", r"\bbiometric verification\b", r"\bidentity platform\b", r"\bbiometric authentication\b"
    ],
    "Intelligent ERP & Smart Factory Systems": [
        r"\bintelligent erp\b", r"\bsmart factory journey\b", r"\berp solutions\b"
    ],
    "Video KYC / V-CIP Customer Onboarding": [
        r"\bvideo kyc\b", r"\bv-cip customer onboarding\b", r"\bvideo identification\b"
    ],
    "Core NetBanking & Mobile Banking App": [
        r"\bnetbanking portal\b", r"\bmobile banking app\b", r"\bonline banking platform\b"
    ],
    "Instant Personal & Digital Loans": [
        r"\binstant personal loan\b", r"\bpaperless digital loan\b"
    ],
    "Merchant Payment Terminal & UPI Gateway": [
        r"\bpos terminal provider\b", r"\bupi merchant gateway\b"
    ],
    "Automated Transaction Monitoring System": [
        r"\btransaction monitoring system\b", r"\bfraud detection engine\b", r"\baml screening engine\b"
    ],
    "Electronic Health Records (EHR) Portal": [
        r"\behr portal\b", r"\bpatient health records platform\b"
    ]
}

LOCATIONS = {
    "India": [r"\bindia\b", r"\bmumbai\b", r"\bbengaluru\b", r"\bdelhi\b", r"\bchennai\b", r"\bhyderabad\b", r"\bnoida\b", r"\bgurgaon\b"],
    "Japan": [r"\bjapan\b", r"\btokyo\b", r"\bosaka\b"],
    "United States": [r"\bunited states\b", r"\bu\.s\.\b", r"\bnew york\b", r"\bcalifornia\b", r"\bdelaware\b"],
    "United Kingdom": [r"\bunited kingdom\b", r"\bu\.k\.\b", r"\blondon\b"],
    "Singapore": [r"\bsingapore\b", r"\bapac regional\b"],
    "European Union": [r"\beuropean union\b", r"\bfrankfurt\b", r"\bparis\b", r"\bamsterdam\b"]
}

DEPARTMENTS = {
    "Information Security (CISO) & SecOps": [
        r"\binformation security\b", r"\bciso\b", r"\bcybersecurity (?:team|department|unit)\b", r"\bsecops\b"
    ],
    "Compliance & Regulatory Affairs": [
        r"\bcompliance (?:department|team|office|unit)\b", r"\bregulatory affairs\b", r"\bchief compliance officer\b"
    ],
    "Internal Audit & Governance": [
        r"\binternal audit (?:department|team)\b", r"\baudit committee\b", r"\bgovernance committee\b"
    ],
    "Risk & Business Continuity Management": [
        r"\brisk management\b", r"\bbusiness continuity\b", r"\bbcp\b", r"\bchief risk officer\b"
    ],
    "Legal Counsel & General Counsel": [
        r"\blegal (?:department|counsel|team)\b", r"\bgeneral counsel\b"
    ],
    "Data Protection Office (DPO)": [
        r"\bdata protection officer\b", r"\bdpo\b", r"\bprivacy office\b"
    ],
    "IT & DevOps Infrastructure": [
        r"\bdevops team\b", r"\bit infrastructure\b", r"\bcloud engineering\b"
    ],
    "Retail Banking Operations": [
        r"\bretail operations\b", r"\bbranch operations\b", r"\bcustomer service unit\b"
    ]
}

LICENSES = {
    "ISO 27001 Information Security Certified": [r"\biso 27001\b", r"\biso\/iec 27001 certified\b", r"\biso certified\b"],
    "SOC2 Type II Certified": [r"\bsoc\s?2 type ii\b", r"\bsoc\s?2 certified\b", r"\bsoc 2 compliance\b"],
    "Reserve Bank of India (RBI) Banking License": [r"\brbi licensed bank\b", r"\bscheduled commercial bank\b", r"\blicensed by the reserve bank of india\b"],
    "Payment Aggregator (PA/PG) Authorization": [r"\bpayment aggregator authorization\b", r"\bauthorized by rbi as payment aggregator\b"],
    "SEC Registered Broker-Dealer": [r"\bsec registered\b", r"\bmember finra\b", r"\bbroker-dealer registered with sec\b"],
    "SEBI Registered Intermediary": [r"\bsebi registered\b", r"\bmerchant banker registered with sebi\b"]
}

REGULATORY_SIGNALS = {
    "Digital Personal Data Protection (DPDP) Act": [
        r"\bdpdp\b", r"\bdata protection act\b", r"\bpersonal data protection\b", r"\bpii de-identification\b"
    ],
    "CERT-In Cyber Security Directions": [
        r"\bcert-in\b", r"\bcyber security directions\b", r"\bincident reporting\b"
    ],
    "RBI KYC & Master Directions": [
        r"\brbi kyc\b", r"\bmaster direction on kyc\b", r"\bv-cip guidelines\b"
    ],
    "RBI Cyber Security Framework": [
        r"\brbi cyber security framework\b", r"\bcsf baseline controls\b"
    ],
    "SEC Rule 15c3-5 Market Access": [
        r"\brule 15c3-5\b", r"\bmarket access rule\b"
    ],
    "HIPAA Security & PHI Rules": [
        r"\bhipaa compliant\b", r"\bphi protection\b", r"\b45 cfr part 164\b"
    ],
    "GDPR & Data Privacy Directives": [
        r"\bgdpr compliance\b", r"\beu data protection regulation\b", r"\bgdpr & data privacy\b"
    ]
}

class ExtractedFactCandidate:
    def __init__(
        self,
        fact_type: str,
        fact_value: str,
        source_url: str,
        source_title: str,
        source_tier: int,
        snippet: str,
        extraction_method: str,
        confidence: float,
        page_relevance: str = "HIGH_VALUE",
        fact_relevance: str = "DIRECT_ORGANIZATION_FACT"
    ):
        self.fact_type = fact_type
        self.fact_value = fact_value
        self.source_url = source_url
        self.source_title = source_title
        self.source_tier = source_tier
        self.snippet = snippet
        self.extraction_method = extraction_method
        self.confidence = confidence
        self.page_relevance = page_relevance
        self.fact_relevance = fact_relevance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_type": self.fact_type,
            "fact_value": self.fact_value,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_tier": self.source_tier,
            "snippet": self.snippet,
            "extraction_method": self.extraction_method,
            "confidence": round(self.confidence, 2),
            "status": "PENDING",
            "page_relevance": self.page_relevance,
            "fact_relevance": self.fact_relevance
        }

class FactExtractor:
    """
    Evidence-driven semantic fact extractor for public corporate intelligence.
    Enforces a strict Fact-Evidence Contract:
      1. Page Relevance Classification (High/Medium/Low/Exclude)
      2. Subject-Predicate-Object (S-P-O) Attribution Validation
      3. Strict Disqualification of Customer, Partner, and Incidental Mentions
    """

    @classmethod
    def classify_page_relevance(cls, page: DiscoveredPage) -> str:
        """Classify evidentiary value of the page based on URL and title."""
        path = urlparse(page.url).path.lower()
        title = page.title.lower()

        if path in ["", "/"] or any(k in path for k in [
            "/about", "/company", "/who-we-are", "/overview", "/solutions",
            "/products", "/services", "/industries", "/technology", "/security",
            "/governance", "/corporate", "/profile", "/locations", "/contact"
        ]):
            return "HIGH_VALUE"

        if any(k in path for k in ["/news", "/press", "/report", "/announcement", "/whitepaper"]):
            return "MEDIUM_VALUE"

        if any(k in path for k in ["/blog", "/article", "/case-study", "/story", "/event"]):
            return "LOW_VALUE"

        return "HIGH_VALUE"

    @classmethod
    def classify_fact_relevance(
        cls,
        fact_type: str,
        fact_value: str,
        snippet: str,
        page: DiscoveredPage
    ) -> str:
        """
        Determine if the extracted fact is a DIRECT_ORGANIZATION_FACT or an incidental mention.
        Rejects: CUSTOMER_REFERENCE, PARTNER_REFERENCE, THIRD_PARTY_REFERENCE, INCIDENTAL_MENTION, UNKNOWN.
        """
        s_lower = snippet.lower()
        p_title = page.title.lower()

        # ─── 1. Disqualify Incidental Banking / Payment / Asset Keywords on Tech Pages ───
        if fact_value == "Card Issuance & Credit Cards":
            # Only valid if the organization itself issues credit cards as a core financial product
            if not re.search(r"\b(?:we issue|our credit card|apply for a credit card|credit card products?)\b", s_lower):
                return "INCIDENTAL_MENTION"

        if fact_value == "Wealth & Asset Management":
            # Disqualify IT/device/hardware asset management or EV charger management
            if any(t in s_lower for t in ["charger", "fleet", "hardware", "device", "it asset", "asset tracking", "infrastructure asset"]):
                return "INCIDENTAL_MENTION"
            if not re.search(r"\b(?:wealth management|private wealth|portfolio management|investment advisory)\b", s_lower):
                return "INCIDENTAL_MENTION"

        if fact_value in ["Retail Banking", "Corporate & Commercial Lending", "Digital Lending & Micro-Credit"]:
            if not re.search(r"\b(?:we are a bank|our banking services|commercial bank|banking operations|savings account|we lend|our lending)\b", s_lower):
                if not any(k in p_title for k in ["bank", "banking", "finance"]):
                    return "INCIDENTAL_MENTION"

        # ─── 2. Disqualify Customer & Industry References ───
        if re.search(r"\b(?:for (?:our )?customers|customers? (?:using|use)|clients? (?:using|use)|client's|customer's|used by banks)\b", s_lower):
            if fact_value in ["Retail Banking", "Wealth & Asset Management", "Card Issuance & Credit Cards", "Corporate & Commercial Lending"]:
                return "CUSTOMER_REFERENCE"
            if not re.search(r"\b(?:we provide|we offer|our product|our solution|our platform|developed by|specializes in)\b", s_lower):
                return "CUSTOMER_REFERENCE"

        # Disqualify "Retail Banking" if it's referenced as an industry/solution target
        if fact_value in ["Retail Banking", "Wealth & Asset Management", "Card Issuance & Credit Cards", "Corporate & Commercial Lending", "Digital Lending & Micro-Credit"]:
            if re.search(r"\b(?:solutions?(?: for)?|software(?: for)?|platform(?: for)?|empowering|infrastructure(?: for)?|technology(?: for)?|services(?: for)?)\s+" + re.escape(fact_value.lower()) + r"\b", s_lower) or \
               re.search(r"\b" + re.escape(fact_value.lower()) + r"\s+(?:solutions?|software|platform|infrastructure|technology|services?)\b", s_lower):
                return "INDUSTRY_REFERENCE"

        # ─── 3. Disqualify Partner & Third-Party References ───
        if re.search(r"\b(?:partner(?:s|'s)? (?:provide|provides|offer|offers|distributes?)|partnered with|third[- ]party|external vendor)\b", s_lower):
            return "PARTNER_REFERENCE"

        # ─── 4. Location Verification ───
        if fact_type == "LOCATION":
            # Must have presence indicator
            if not re.search(r"\b(?:headquarter|office|presence|in india|in japan|subsidiary|operating in|across|wholly-owned|branches|centers?|centre)\b", s_lower):
                if not any(loc_kw in p_title for loc_kw in ["india", "japan", "singapore", "global"]):
                    return "INCIDENTAL_MENTION"

        # ─── 5. Department Verification ───
        if fact_type == "DEPARTMENT":
            if not any(k in s_lower for k in ["team", "department", "unit", "office", "committee", "ciso", "dpo", "audit", "governance", "security", "competency"]):
                return "INCIDENTAL_MENTION"

        # ─── 6. Regulatory Signal Verification ───
        if fact_type == "REGULATORY_SIGNAL":
            if not any(k in s_lower for k in ["compliant", "compliance", "regulation", "framework", "adhere", "dpdp", "cert-in", "gdpr", "policy", "security", "privacy", "protection"]):
                return "INCIDENTAL_MENTION"
            return "REGULATORY_SIGNAL"

        # ─── 7. Direct Attribution Acceptance ───
        return "DIRECT_ORGANIZATION_FACT"

    @classmethod
    def _find_snippet_for_regex(
        cls,
        patterns: List[str],
        text_paragraphs: List[str]
    ) -> Optional[str]:
        """Find the best paragraph and sentence matching any regex pattern."""
        for pattern in patterns:
            rx = re.compile(pattern, re.IGNORECASE)
            for p in text_paragraphs:
                if rx.search(p):
                    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]
                    for i, s in enumerate(sentences):
                        if rx.search(s):
                            snippet_candidate = s
                            if i + 1 < len(sentences):
                                snippet_candidate += " " + sentences[i + 1]
                            return snippet_candidate[:320]
                    return p[:320]
        return None

    @classmethod
    def extract_from_pages(
        cls,
        pages: List[DiscoveredPage],
        root_domain: str
    ) -> List[ExtractedFactCandidate]:
        """
        Extract organizational facts from crawled pages adhering to the strict Fact Evidence Contract.
        Filters out incidental mentions, customer features, and weak third-party references.
        """
        candidates: List[ExtractedFactCandidate] = []
        seen_facts = set()

        if not pages:
            return []

        # 1. Company Name Identification
        company_name = None
        company_evidence = ""
        company_page = pages[0]

        for page in pages:
            # Check title pattern e.g. "... | NEC India" or "... - NEC India"
            if "|" in page.title:
                parts = [p.strip() for p in page.title.split("|") if p.strip()]
                for part in reversed(parts):
                    if len(part) >= 2 and not any(j in part.lower() for j in ["home", "solutions", "services", "products", "overview", "portal", "index", "welcome"]):
                        company_name = part
                        company_evidence = f"Identified official brand '{company_name}' from corporate page title: {page.title}"
                        company_page = page
                        break
            elif "-" in page.title:
                parts = [p.strip() for p in page.title.split("-") if p.strip()]
                for part in reversed(parts):
                    if len(part) >= 2 and not any(j in part.lower() for j in ["home", "solutions", "services", "products", "overview", "portal", "index", "welcome"]):
                        company_name = part
                        company_evidence = f"Identified official brand '{company_name}' from corporate page title: {page.title}"
                        company_page = page
                        break

            if company_name:
                break

            for p in page.paragraphs[:3]:
                for pattern in COMPANY_NAME_PATTERNS:
                    m = re.search(pattern, p)
                    if m:
                        name_cand = m.group(1).strip()
                        if len(name_cand) > 3 and not any(junk in name_cand.lower() for junk in ["home", "login", "cookie", "page", "solutions"]):
                            company_name = name_cand
                            company_evidence = p[:280]
                            company_page = page
                            break
                if company_name:
                    break

        if company_name:
            candidates.append(ExtractedFactCandidate(
                fact_type="COMPANY",
                fact_value=company_name,
                source_url=company_page.url,
                source_title=company_page.title,
                source_tier=2,
                snippet=company_evidence or f"Derived from public corporate endpoint {company_page.url}",
                extraction_method="RULE_MATCHED",
                confidence=0.96,
                page_relevance="HIGH_VALUE",
                fact_relevance="DIRECT_ORGANIZATION_FACT"
            ))
            seen_facts.add(("COMPANY", company_name.strip().lower()))
        else:
            domain_name = root_domain.split(".")[0].upper() if len(root_domain.split(".")[0]) <= 3 else root_domain.split(".")[0].capitalize() + " Enterprise"
            candidates.append(ExtractedFactCandidate(
                fact_type="COMPANY",
                fact_value=domain_name,
                source_url=pages[0].url,
                source_title=pages[0].title,
                source_tier=2,
                snippet=f"Derived from public corporate endpoint {pages[0].url}",
                extraction_method="RULE_MATCHED",
                confidence=0.85,
                page_relevance="HIGH_VALUE",
                fact_relevance="DIRECT_ORGANIZATION_FACT"
            ))
            seen_facts.add(("COMPANY", domain_name.strip().lower()))

        # Helper to scan and validate catalog entries with S-P-O rules
        def scan_catalog(catalog: Dict[str, List[str]], fact_type: str, base_confidence: float):
            for label, patterns in catalog.items():
                dedup_key = (fact_type, label.strip().lower())
                if dedup_key in seen_facts:
                    continue

                for page in pages:
                    page_rel = cls.classify_page_relevance(page)
                    if page_rel == "LOW_VALUE" and fact_type in ["BUSINESS_ACTIVITY", "LICENSE"]:
                        continue

                    snippet = cls._find_snippet_for_regex(patterns, page.paragraphs)
                    if snippet:
                        # Perform S-P-O & Incidental Mentions Classification
                        fact_rel = cls.classify_fact_relevance(fact_type, label, snippet, page)

                        # Reject customer, partner, third-party, and incidental mentions
                        if fact_rel not in ["DIRECT_ORGANIZATION_FACT", "RELATED_ORGANIZATION_FACT", "REGULATORY_SIGNAL"]:
                            logger.debug("Rejected false-positive candidate [%s: %s] as %s", fact_type, label, fact_rel)
                            continue

                        # Compute confidence based on explicit evidence
                        conf = base_confidence
                        if any(term in snippet.lower() for term in ["we provide", "our services", "our department", "licensed by", "we offer", "division", "wholly-owned"]):
                            conf = min(0.98, conf + 0.06)

                        candidates.append(ExtractedFactCandidate(
                            fact_type=fact_type,
                            fact_value=label,
                            source_url=page.url,
                            source_title=page.title,
                            source_tier=2,
                            snippet=snippet,
                            extraction_method="RULE_MATCHED",
                            confidence=conf,
                            page_relevance=page_rel,
                            fact_relevance=fact_rel
                        ))
                        seen_facts.add(dedup_key)
                        break

        # 2. Extract Business Activities
        scan_catalog(BUSINESS_ACTIVITIES, "BUSINESS_ACTIVITY", 0.88)

        # 3. Extract Products & Services
        scan_catalog(PRODUCTS_SERVICES, "PRODUCT_SERVICE", 0.85)

        # 4. Extract Locations / Jurisdictions
        scan_catalog(LOCATIONS, "LOCATION", 0.90)

        # 5. Extract Departments
        scan_catalog(DEPARTMENTS, "DEPARTMENT", 0.86)

        # 6. Extract Licenses & Certifications
        scan_catalog(LICENSES, "LICENSE", 0.92)

        # 7. Extract Regulatory Signals
        scan_catalog(REGULATORY_SIGNALS, "REGULATORY_SIGNAL", 0.84)

        # Sort candidate facts by confidence descending
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates
