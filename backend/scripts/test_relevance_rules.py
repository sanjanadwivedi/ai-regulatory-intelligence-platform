import re

# Test sample paragraphs from in.nec.com/en_IN/solutions_services/intelligent_transport_solutions/ev_charging.html
ev_charging_snippet_1 = "Payment method: Support payment with smart card, RFID card, credit card and QR code."
ev_charging_snippet_2 = "NEC EV Charger management system provides asset management and charger status monitoring for charging station operators."
true_nec_snippet_1 = "NEC India provides AI and Video Analytics solutions for smarter, safer urban spaces across India."
true_nec_snippet_2 = "Our Digital ID and biometric verification solutions empower seamless travel experiences."

# Attribution validator logic
def classify_fact_relevance(fact_type: str, fact_value: str, snippet: str) -> str:
    s_lower = snippet.lower()
    
    # 1. Negative / Incidental patterns
    if fact_value in ["Card Issuance & Credit Cards"]:
        # Only accept if company explicitly issues credit cards
        if not re.search(r"\b(?:issue|issuance of|apply for|our|we issue)\s+(?:credit|co-branded)\s+cards?\b", s_lower):
            if any(term in s_lower for term in ["payment with", "pay with", "pay via", "accepts", "payment method", "credit card payment"]):
                return "INCIDENTAL_MENTION"
            return "INCIDENTAL_MENTION"

    if fact_value in ["Wealth & Asset Management"]:
        # Only accept if company provides wealth / asset management as a financial service
        if not re.search(r"\b(?:wealth management|portfolio management|private wealth|asset management services?)\b", s_lower) or any(tech in s_lower for tech in ["it asset", "charger", "fleet", "hardware", "device", "physical asset"]):
            if "charger" in s_lower or "fleet" in s_lower or "device" in s_lower or "it asset" in s_lower:
                return "INCIDENTAL_MENTION"
            if not re.search(r"\b(?:we provide|our|advisory|investment|wealth management)\b", s_lower):
                return "INCIDENTAL_MENTION"

    # 2. General Customer / Partner check
    if re.search(r"\b(?:customers? use|clients? use|partners? provide|third[- ]party)\b", s_lower):
        if not re.search(r"\b(?:we|our|nec|the company|developed by|offered by)\b", s_lower):
            return "CUSTOMER_REFERENCE"

    # 3. Direct attribution check
    if any(p in s_lower for p in ["we provide", "we offer", "our solutions", "our services", "nec india provides", "nec provides", "developed by", "specializes in", "solution for"]):
        return "DIRECT_ORGANIZATION_FACT"

    return "DIRECT_ORGANIZATION_FACT"

print("EV Credit card snippet:", classify_fact_relevance("BUSINESS_ACTIVITY", "Card Issuance & Credit Cards", ev_charging_snippet_1))
print("EV Asset management snippet:", classify_fact_relevance("BUSINESS_ACTIVITY", "Wealth & Asset Management", ev_charging_snippet_2))
print("True AI Video Analytics:", classify_fact_relevance("BUSINESS_ACTIVITY", "AI & Video Analytics Solutions", true_nec_snippet_1))
print("True Digital ID:", classify_fact_relevance("BUSINESS_ACTIVITY", "Digital Identity & Biometrics", true_nec_snippet_2))
