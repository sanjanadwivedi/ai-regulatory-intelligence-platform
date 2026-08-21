import pytest
from app.services.discovery_crawler import DiscoveredPage
from app.services.fact_extractor import FactExtractor

def test_direct_organization_statement_accepted():
    """TEST 1: Direct statement attributing capability to the organization must be ACCEPTED."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/solutions",
            title="AI & IoT Solutions | NEC India",
            text_content="NEC India provides AI and Video Analytics solutions for smarter, safer urban spaces across India.",
            paragraphs=["NEC India provides AI and Video Analytics solutions for smarter, safer urban spaces across India."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "AI & Video Analytics Solutions" in fact_values
    for c in candidates:
        if c.fact_value == "AI & Video Analytics Solutions":
            assert c.fact_relevance == "DIRECT_ORGANIZATION_FACT"

def test_customer_reference_rejected():
    """TEST 2: Mentions describing what customers use or do must be REJECTED as an organization capability."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/case-studies/banking",
            title="Banking Case Study | NEC India",
            text_content="For our customers using core retail banking, we provide hardware server infrastructure.",
            paragraphs=["For our customers using core retail banking and consumer accounts, we provide hardware server infrastructure."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    # NEC itself is NOT a retail bank
    assert "Retail Banking" not in fact_values

def test_partner_reference_rejected():
    """TEST 3: Mentions describing partner capabilities must be REJECTED."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/partners",
            title="Partner Ecosystem | NEC India",
            text_content="Our wealth management partner provides private wealth and mutual funds distribution.",
            paragraphs=["Our wealth management partner provides private wealth and mutual funds distribution."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "Wealth & Asset Management" not in fact_values

def test_incidental_payment_keyword_rejected():
    """TEST 5: Incidental mention of 'credit card' as payment option must be REJECTED as Card Issuance."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/en_IN/solutions_services/intelligent_transport_solutions/ev_charging.html",
            title="EV Charging Solutions | NEC India",
            text_content="EV charging station supports user payment with RFID card, smart card, credit card and QR code.",
            paragraphs=["EV charging station supports user payment with RFID card, smart card, credit card and QR code."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "Card Issuance & Credit Cards" not in fact_values

def test_incidental_hardware_asset_management_rejected():
    """TEST 6: Hardware charger / device / fleet asset management must NOT create Wealth & Asset Management."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/en_IN/solutions_services/intelligent_transport_solutions/ev_charging.html",
            title="EV Charging Solutions | NEC India",
            text_content="NEC EV Charger management system provides hardware charger asset management and device monitoring.",
            paragraphs=["NEC EV Charger management system provides hardware charger asset management and device monitoring."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "Wealth & Asset Management" not in fact_values

def test_product_explicitly_offered_accepted():
    """TEST 7: Product explicitly offered by organization must be ACCEPTED."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/products",
            title="Products | NEC India",
            text_content="NEC Mi-Eye is our flagship AI video analytics and urban monitoring solution.",
            paragraphs=["NEC Mi-Eye is our flagship AI video analytics and urban monitoring solution."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "AI Video Analytics & Urban Monitoring" in fact_values

def test_department_explicitly_belonging_accepted():
    """TEST 8: Department / CISO explicitly belonging to organization must be ACCEPTED."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/security",
            title="Security Governance | NEC India",
            text_content="Our Information Security (CISO) & SecOps unit oversees all cyber defense controls.",
            paragraphs=["Our Information Security (CISO) & SecOps unit oversees all cyber defense controls."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "Information Security (CISO) & SecOps" in fact_values

def test_regulatory_signal_dpdp_accepted():
    """TEST 10: Regulatory Signal with explicit compliance relationship must be ACCEPTED."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/pii-de-identification",
            title="PII De-identification | NEC India",
            text_content="Our PII de-identification platform ensures enterprise compliance with the Digital Personal Data Protection (DPDP) Act.",
            paragraphs=["Our PII de-identification platform ensures enterprise compliance with the Digital Personal Data Protection (DPDP) Act."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    fact_values = {c.fact_value for c in candidates}
    assert "Digital Personal Data Protection (DPDP) Act" in fact_values

def test_deterministic_deduplication():
    """TEST 11: Same fact across multiple pages is deduplicated into exactly one candidate with highest confidence."""
    pages = [
        DiscoveredPage(
            url="https://in.nec.com/page1",
            title="Page 1 | NEC India",
            text_content="We provide digital identity and biometric verification.",
            paragraphs=["We provide digital identity and biometric verification."]
        ),
        DiscoveredPage(
            url="https://in.nec.com/page2",
            title="Page 2 | NEC India",
            text_content="Our solutions include digital identity and biometrics across India.",
            paragraphs=["Our solutions include digital identity and biometrics across India."]
        )
    ]
    candidates = FactExtractor.extract_from_pages(pages, "in.nec.com")
    di_facts = [c for c in candidates if c.fact_value == "Digital Identity & Biometrics"]
    assert len(di_facts) == 1
