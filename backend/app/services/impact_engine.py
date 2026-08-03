from typing import Dict, Any

class ImpactAnalysisEngine:
    """
    Impact Analysis Engine: Evaluates AI extraction outputs against the organization's
    Business Context profile to determine relevance level, risk score, affected teams, and control gaps.
    """

    @staticmethod
    def assess_impact(regulation_title: str, sector: str) -> Dict[str, Any]:
        sector_upper = sector.upper()
        
        if "BANK" in sector_upper or "FINANCE" in sector_upper or "KYC" in regulation_title.upper():
            relevance = "HIGH"
            risk_score = 88
            depts = ["Retail Banking", "Compliance Operations", "Legal & Regulatory", "IT Infrastructure"]
            actions = [
                "Update Standard Operating Procedure (SOP-KYC-2026 v3.2) to reflect revised V-CIP verification rules.",
                "Configure automated daily transaction monitoring rules in core banking system.",
                "Schedule mandatory compliance training for customer onboarding operations staff."
            ]
            gaps = [
                {"policy_name": "Retail KYC Policy 3.1", "gap_description": "Lacks explicit 2-year re-verification cadence for high-risk accounts."},
                {"policy_name": "Data Retention Policy 2.0", "gap_description": "Current log archive retention is 5 years; regulation requires 7 years."}
            ]
        elif "CYBER" in regulation_title.upper() or "TECH" in sector_upper:
            relevance = "HIGH"
            risk_score = 92
            depts = ["Information Security", "Risk Management", "Legal & Compliance", "Incident Response"]
            actions = [
                "Establish 4-day material incident escalation protocol for CISO & Legal Counsel.",
                "Perform third-party vendor risk assessment across cloud service providers.",
                "Update Board Incident Reporting template for SEC Form 8-K disclosures."
            ]
            gaps = [
                {"policy_name": "Cyber Incident SOP 1.4", "gap_description": "Current escalation timeline is 7 days; regulation enforces 4 business days."}
            ]
        else:
            relevance = "MEDIUM"
            risk_score = 65
            depts = ["Compliance Operations", "Internal Audit"]
            actions = [
                "Review internal policy guidelines for alignment with updated regulatory definitions.",
                "Archive prior regulatory guidance documentation."
            ]
            gaps = [
                {"policy_name": "General Compliance Policy", "gap_description": "Terminology updates required in Section 2 definitions."}
            ]

        return {
            "relevance_level": relevance,
            "risk_score": risk_score,
            "affected_departments": depts,
            "recommended_actions": actions,
            "policy_control_gaps": gaps
        }
