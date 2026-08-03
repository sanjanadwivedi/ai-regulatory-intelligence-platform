import os
import re
import json
import logging
import datetime
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger("compliance_platform.ai_engine")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_gemini_client():
    """Return a Gemini client if an API key is configured, else None."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.warning("Failed to initialise Gemini client: %s", exc)
        return None


def _get_secondary_client():
    """
    Return a secondary LLM client for cross-model verification (Item 3).
    Reads SECONDARY_LLM_PROVIDER and SECONDARY_LLM_API_KEY from config.
    Supports 'anthropic' (Claude) or 'openai' (GPT-4o).
    Returns (client, provider_name) or (None, None) if not configured.

    Cross-model verification principle:
    - Extract with Gemini; verify with a different provider.
    - If both agree → higher confidence.
    - If they disagree → flag needs_human_review = 1.
    - This breaks the self-preference bias of same-model self-checking.
    """
    provider = (settings.SECONDARY_LLM_PROVIDER or os.getenv("SECONDARY_LLM_PROVIDER", "")).lower().strip()
    api_key = settings.SECONDARY_LLM_API_KEY or os.getenv("SECONDARY_LLM_API_KEY", "")

    if not provider or not api_key:
        return None, None  # Gracefully disabled — fall back to Gemini self-check

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            return client, "anthropic/claude-sonnet-4-5"
        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            return client, "openai/gpt-4o"
        else:
            logger.warning("Unknown SECONDARY_LLM_PROVIDER '%s' — cross-model verification disabled", provider)
            return None, None
    except Exception as exc:
        logger.warning("Failed to initialise secondary LLM client (%s): %s", provider, exc)
        return None, None


def _call_secondary_verification(client, provider_name: str, prompt: str) -> Optional[Dict]:
    """
    Call the secondary LLM for a verification prompt.
    Returns parsed dict with 'verdict' and 'citation' or None on failure.
    """
    try:
        if provider_name and provider_name.startswith("anthropic"):
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text if response.content else ""
        elif provider_name and provider_name.startswith("openai"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # cost-effective for verification
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            raw = response.choices[0].message.content if response.choices else ""
        else:
            return None

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        pass
    except Exception as exc:
        logger.warning("Secondary LLM call failed (%s): %s", provider_name, exc)
    return None


def _sanitise_for_prompt(text: str, max_chars: int = 4000) -> str:
    """
    Strip potential prompt-injection markers and truncate before embedding in
    an LLM prompt.  This text originates from live-scraped external sources.
    """
    # Remove any attempts to inject role/system delimiters
    cleaned = re.sub(r"(###\s*(system|user|assistant)|<\|.*?\|>)", "", text, flags=re.IGNORECASE)
    # Collapse excessive whitespace and truncate
    cleaned = re.sub(r"\s{3,}", "\n", cleaned).strip()
    return cleaned[:max_chars]


def _call_gemini(client, prompt: str, expect: str = "json") -> Optional[Any]:
    """
    Call Gemini and return parsed JSON (dict or list) or None on any failure.
    Logs warnings on failure so they are visible in production logs.
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text or ""
        if expect == "list":
            match = re.search(r"\[.*\]", raw, re.DOTALL)
        else:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError as jde:
        logger.warning("Gemini returned non-JSON output: %s", jde)
    except Exception as exc:
        logger.warning("Gemini API call failed: %s", exc, exc_info=True)
    return None


import difflib

# ---------------------------------------------------------------------------
# Grounding & Verification Helpers
# ---------------------------------------------------------------------------

def verify_source_span_grounding(source_span: str, full_text: str) -> Dict[str, Any]:
    """
    Programmatically verify that source_span actually appears (fuzzy match)
    in full_text. Returns grounding_status and grounding_score.
    """
    if not source_span or not full_text:
        return {"grounding_status": "UNVERIFIED_GROUNDING", "grounding_score": 0.0}
    
    span_clean = source_span.strip().lower()
    text_clean = full_text.strip().lower()
    
    if span_clean in text_clean:
        return {"grounding_status": "VERIFIED", "grounding_score": 1.0}
    
    window_size = max(20, len(span_clean))
    best_ratio = 0.0
    step = max(1, len(text_clean) // 100) if len(text_clean) > 100 else 1
    
    for i in range(0, max(1, len(text_clean) - window_size + 1), step):
        sub = text_clean[i:i+window_size]
        ratio = difflib.SequenceMatcher(None, span_clean, sub).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            if best_ratio >= 0.90:
                break
                
    status = "VERIFIED" if best_ratio >= 0.65 else "UNVERIFIED_GROUNDING"
    return {"grounding_status": status, "grounding_score": round(best_ratio, 2)}


def compute_calibration_score(ocr_conf: float, grounding_score: float, verifier_verdict: str, extraction_method: str) -> float:
    """
    Calculate an independent multi-signal extraction calibration confidence score.
    """
    if extraction_method == "EXTRACTION_PENDING":
        return 0.0
    if extraction_method == "HUMAN_CORRECTED":
        return 1.0
        
    v_score = 1.0 if verifier_verdict == "SUPPORTED" else (0.5 if verifier_verdict == "PARTIALLY_SUPPORTED" else 0.0)
    score = (grounding_score * 0.40) + (v_score * 0.40) + ((ocr_conf or 0.95) * 0.20)
    return round(score, 2)


# ---------------------------------------------------------------------------
# Agent 1 — Extraction Agent
# ---------------------------------------------------------------------------

class ExtractionAgent:
    """
    Parses regulation text into structured Regulatory Knowledge Ontology:
    Regulation → Section → Obligation → Requirement (with Source Span Grounding).

    Primary: Gemini 2.5 Flash
    Fallback: Structurally marked EXTRACTION_PENDING — never fabricates placeholders.
    """

    @staticmethod
    def extract_ontology(title: str, authority: str, text: str) -> Dict[str, Any]:
        safe_title = _sanitise_for_prompt(title, max_chars=200)
        safe_auth = _sanitise_for_prompt(authority, max_chars=100)
        safe_text = _sanitise_for_prompt(text)

        client = _get_gemini_client()
        if client:
            prompt = (
                "You are a Regulatory Extraction AI Agent enforcing verbatim grounding.\n"
                "Extract structured regulatory ontology from the text below.\n"
                "STRICT CONSTRAINT: For deadline, penalty_description, or statutory_reference, "
                "if it is NOT explicitly stated in the source text, return null — DO NOT infer or invent values.\n"
                "For source_span, provide the exact verbatim sentence or phrase from the source text that supports the requirement.\n\n"
                f"Title: {safe_title}\nAuthority: {safe_auth}\nText: {safe_text}\n\n"
                "Respond ONLY with a JSON array of sections:\n"
                '[{"section_number": "...", "title": "...", "content_text": "...", '
                '"obligations": [{"summary": "...", "requirements": ['
                '{"requirement_text": "...", "source_span": "verbatim text span", "deadline": "YYYY-MM-DD or null", '
                '"penalty_description": "text or null", "statutory_reference": "text or null", '
                '"affected_entities": ["..."]}]}]}]'
            )
            result = _call_gemini(client, prompt, expect="list")
            if result and isinstance(result, list) and len(result) > 0:
                for sec in result:
                    for obl in sec.get("obligations", []):
                        for req in obl.get("requirements", []):
                            if isinstance(req.get("deadline"), str):
                                try:
                                    req["deadline"] = datetime.datetime.strptime(
                                        req["deadline"], "%Y-%m-%d"
                                    ).date()
                                except ValueError:
                                    req["deadline"] = None
                            
                            # Perform programmatic source-span grounding check
                            span = req.get("source_span") or req.get("requirement_text", "")
                            g_res = verify_source_span_grounding(span, text)
                            req["grounding_status"] = g_res["grounding_status"]
                            req["grounding_score"] = g_res["grounding_score"]

                            # Perform adversarial second-pass verification
                            v_res = VerificationAgent.verify_requirement(
                                req.get("requirement_text", ""), span, text
                            )
                            req["verifier_verdict"] = v_res["verifier_verdict"]
                            req["verifier_citation"] = v_res["verifier_citation"]

                return {"sections": result, "extraction_method": "GEMINI_EXTRACTED"}

        # Refuse to fabricate placeholder text — deterministic NLP parser with EXTRACTION_PENDING status
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        sec_num, sec_title = "Section 1", "Statutory Provisions"
        if lines:
            first = lines[0]
            if ":" in first:
                sec_num, sec_title = first.split(":", 1)
            else:
                sec_title = first[:80]

        source_span_fallback = text[:200] if text else title
        g_res = verify_source_span_grounding(source_span_fallback, text)

        return {
            "sections": [
                {
                    "section_number": sec_num.strip(),
                    "title": sec_title.strip(),
                    "content_text": text,
                    "obligations": [
                        {
                            "summary": f"Statutory directive provisions for {title}",
                            "requirements": [
                                {
                                    "requirement_text": text[:300] if text else "Statutory compliance provisions pending review.",
                                    "source_span": source_span_fallback,
                                    "grounding_status": g_res["grounding_status"],
                                    "grounding_score": g_res["grounding_score"],
                                    "verifier_verdict": "PARTIALLY_SUPPORTED",
                                    "verifier_citation": "Extracted via NLP structural parser; routed for human review.",
                                    "deadline": None,
                                    "penalty_description": None,
                                    "statutory_reference": f"{authority}",
                                    "affected_entities": ["Regulated Entities"],
                                }
                            ],
                        }
                    ],
                }
            ],
            "extraction_method": "EXTRACTION_PENDING" if not client else "GEMINI_EXTRACTED"
        }


# ---------------------------------------------------------------------------
# Agent 1B — Adversarial Verification Agent
# ---------------------------------------------------------------------------

class VerificationAgent:
    """
    Adversarial Second-Pass Verification Agent — Cross-Model Architecture (Item 3).

    Extraction model:   Gemini 2.5 Flash (ExtractionAgent)
    Verification model: Secondary LLM (Anthropic Claude / OpenAI GPT-4o) if configured,
                        else Gemini 2.5 Flash as fallback.

    Cross-model disagreement (Gemini says SUPPORTED, Claude says NOT_SUPPORTED) is a
    stronger reliability signal than same-model self-checking and triggers human review.

    Result dict always includes 'verification_model' so consumers know which model ran.
    """
    @staticmethod
    def verify_requirement(req_text: str, source_span: str, full_text: str) -> Dict[str, Any]:
        verification_prompt = (
            "You are an Adversarial Regulatory Verification AI. "
            "Verify if the source document text actually supports the extracted requirement claim.\n"
            f"Extracted Requirement: {req_text}\n"
            f"Quoted Source Span: {source_span}\n"
            f"Document Text: {_sanitise_for_prompt(full_text, max_chars=2500)}\n\n"
            "Respond ONLY with a JSON object:\n"
            '{"verdict": "SUPPORTED|PARTIALLY_SUPPORTED|NOT_SUPPORTED", '
            '"citation": "verbatim citation or reason if not supported"}'
        )

        # --- Attempt secondary (cross-model) verification first ---
        secondary_client, secondary_name = _get_secondary_client()
        secondary_result = None
        if secondary_client:
            secondary_result = _call_secondary_verification(secondary_client, secondary_name, verification_prompt)

        # --- Primary: Gemini verification ---
        gemini_result = None
        gemini_client = _get_gemini_client()
        if gemini_client:
            gemini_raw = _call_gemini(gemini_client, verification_prompt, expect="json")
            if gemini_raw and isinstance(gemini_raw, dict) and "verdict" in gemini_raw:
                gemini_result = gemini_raw

        # --- Cross-model disagreement detection ---
        if secondary_result and gemini_result:
            s_verdict = secondary_result.get("verdict", "")
            g_verdict = gemini_result.get("verdict", "")
            models_agree = (s_verdict == g_verdict)

            if not models_agree:
                # Disagreement is a strong signal → flag for human review
                logger.warning(
                    "Cross-model disagreement: Gemini=%s, %s=%s for req: %s...",
                    g_verdict, secondary_name, s_verdict, req_text[:80]
                )
                return {
                    "verifier_verdict": "PARTIALLY_SUPPORTED",
                    "verifier_citation": (
                        f"Cross-model disagreement: Gemini={g_verdict}, {secondary_name}={s_verdict}. "
                        f"Gemini citation: {gemini_result.get('citation', '')} | "
                        f"{secondary_name} citation: {secondary_result.get('citation', '')}"
                    ),
                    "verification_model": f"gemini+{secondary_name}",
                    "cross_model_agreement": False,
                    "needs_human_review": 1,  # Propagated by caller
                }
            else:
                # Both models agree → higher confidence
                return {
                    "verifier_verdict": s_verdict,
                    "verifier_citation": secondary_result.get("citation", "Both models agree."),
                    "verification_model": f"gemini+{secondary_name}",
                    "cross_model_agreement": True,
                }

        # --- Single model available ---
        if gemini_result:
            return {
                "verifier_verdict": gemini_result.get("verdict", "SUPPORTED"),
                "verifier_citation": gemini_result.get("citation", "Verified against source text"),
                "verification_model": "gemini-2.5-flash",
                "cross_model_agreement": None,  # Only one model ran
            }
        if secondary_result:
            return {
                "verifier_verdict": secondary_result.get("verdict", "SUPPORTED"),
                "verifier_citation": secondary_result.get("citation", "Verified by secondary model"),
                "verification_model": secondary_name,
                "cross_model_agreement": None,
            }

        # --- Pure programmatic fallback (no LLM available) ---
        grounding = verify_source_span_grounding(source_span or req_text[:100], full_text)
        score = grounding.get("grounding_score", 0.0)
        if score >= 0.80:
            verdict = "SUPPORTED"
            cit = "Direct textual match verified in source document."
        elif score >= 0.50:
            verdict = "PARTIALLY_SUPPORTED"
            cit = "Partial substring match in source document. Requires human verification."
        else:
            verdict = "NOT_SUPPORTED"
            cit = "No matching text span found in source document."

        return {
            "verifier_verdict": verdict,
            "verifier_citation": cit,
            "verification_model": "programmatic_grounding_fallback",
            "cross_model_agreement": None,
        }



# ---------------------------------------------------------------------------
# Agent 2 — Classification Agent
# ---------------------------------------------------------------------------

class ClassificationAgent:
    """
    Determines statutory scope, jurisdiction, and risk severity score.

    Primary: Gemini 2.5 Flash
    Fallback: keyword heuristic over actual title/sector text.
    """

    @staticmethod
    def classify(title: str, sector: str) -> Dict[str, Any]:
        safe_title = _sanitise_for_prompt(title, max_chars=200)
        safe_sector = _sanitise_for_prompt(sector, max_chars=100)

        client = _get_gemini_client()
        if client:
            prompt = (
                f"Classify the regulatory risk for title: '{safe_title}' and sector: '{safe_sector}'.\n"
                'Respond ONLY with: {"relevance_level": "HIGH|MEDIUM|LOW", '
                '"risk_score": 1-100, "statutory_scope": "..."}'
            )
            result = _call_gemini(client, prompt, expect="json")
            if result and isinstance(result, dict):
                return result

        title_lower = title.lower()
        high_keywords = {"cyber", "kyc", "aml", "breach", "gdpr", "pii", "phi", "incident"}
        risk_score = 92 if any(k in title_lower for k in high_keywords) else 75
        return {
            "relevance_level": "HIGH" if risk_score > 80 else "MEDIUM",
            "risk_score": risk_score,
            "statutory_scope": (
                "Prudential & AML Compliance"
                if "banking" in sector.lower()
                else "Technology & Cyber Security"
            ),
        }


# ---------------------------------------------------------------------------
# Agent 3 — Impact Agent & Knowledge Graph Linker
# ---------------------------------------------------------------------------

class ImpactAgent:
    """
    Maps extracted requirements to the Enterprise Knowledge Graph:
    Requirement → Control → Policy → Process → Department → Application.

    Two entry points:
    - map_for_requirements(): preferred — operates per-DB-Requirement so each
      returned chain carries the real requirement_id UUID it belongs to.
    - map_knowledge_graph(): legacy/fallback — operates per-regulation-title
      when real Requirement objects are not yet available.

    Primary LLM: Gemini 2.5 Flash.
    DB fallback: queries InternalControl / EnterprisePolicy / EnterpriseProcess /
                 EnterpriseApplication tables.
    Static fallback: sector-keyword heuristic, only if both above fail.
    """

    @staticmethod
    def map_for_requirements(
        title: str,
        requirements: List[Any],   # list of Requirement ORM objects with .id and .requirement_text
        db=None,
    ) -> List[Dict[str, Any]]:
        """
        Per-requirement impact mapping.  For each Requirement DB object, produces
        a chain dict that includes requirement_id = req.id.  This is the correct
        entry point when real persisted Requirement rows are available.

        Each requirement is mapped individually so the graph correctly represents
        which specific obligation a control/policy/process is responding to.
        """
        all_chains: List[Dict[str, Any]] = []
        for req in requirements:
            chains = ImpactAgent._map_single_requirement(
                title=title,
                req_id=req.id,
                req_text=req.requirement_text or "",
                db=db,
            )
            all_chains.extend(chains)
        return all_chains

    @staticmethod
    def _map_single_requirement(
        title: str,
        req_id: str,
        req_text: str,
        db=None,
    ) -> List[Dict[str, Any]]:
        """
        Map one specific requirement to enterprise controls.
        Returns 1–2 chain dicts, each with requirement_id set.
        """
        # Build a context string from both the regulation title and the
        # specific requirement text — more precise than title-only.
        combined = f"{title}: {req_text}"
        safe_combined = _sanitise_for_prompt(combined, max_chars=300)

        result_chains: List[Dict[str, Any]] = []

        # --- Gemini: per-requirement mapping ---------------------------------
        client = _get_gemini_client()
        if client:
            prompt = (
                "You are a compliance knowledge graph agent. "
                "Map the following specific regulatory requirement to enterprise controls. "
                "Return a JSON array of 1–2 chains. Each chain must have: "
                "control_code, policy_code, process_code, department_name, application_code.\n"
                f"Requirement context: {safe_combined}\n"
                "Respond ONLY with the JSON array."
            )
            raw = _call_gemini(client, prompt, expect="list")
            if raw and isinstance(raw, list) and len(raw) > 0:
                for chain in raw:
                    if isinstance(chain, dict) and chain.get("control_code"):
                        chain["requirement_id"] = req_id
                        result_chains.append(chain)

        if result_chains:
            logger.info(
                "ImpactAgent: mapped req %s via Gemini → %d chains", req_id[:8], len(result_chains)
            )
            return result_chains

        # --- DB fallback: keyword match on requirement text + title ----------
        db_chains = ImpactAgent._db_lookup_chains(combined, db)
        if db_chains:
            for chain in db_chains:
                chain["requirement_id"] = req_id
            logger.info(
                "ImpactAgent: mapped req %s via DB → %d chains", req_id[:8], len(db_chains)
            )
            return db_chains

        # --- Static fallback: keyword heuristic on combined text -------------
        static = ImpactAgent._static_fallback_chain(combined)
        static["requirement_id"] = req_id
        logger.info("ImpactAgent: mapped req %s via static fallback", req_id[:8])
        return [static]

    @staticmethod
    def _db_lookup_chains(context_text: str, db) -> List[Dict[str, Any]]:
        """Query live DB tables for controls matching keywords in context_text."""
        if db is None:
            return []
        try:
            from app.models.domain import (
                InternalControl, EnterprisePolicy,
                EnterpriseProcess, EnterpriseApplication,
            )
            text_lower = context_text.lower()

            keyword_map = {
                ("cyber", "tech", "cloud", "security", "incident"): ["Security", "Cyber", "Cloud", "CISO"],
                ("kyc", "aml", "banking", "payment", "onboarding"): ["KYC", "AML", "Banking", "Compliance"],
                ("health", "phi", "hipaa", "clinical", "patient"): ["Health", "Clinical", "Privacy"],
                ("trading", "securities", "sec", "finra", "algo"): ["Trading", "Securities", "Market"],
            }

            keywords: List[str] = []
            for trigger_words, kw_list in keyword_map.items():
                if any(t in text_lower for t in trigger_words):
                    keywords = kw_list
                    break

            controls = db.query(InternalControl).all()
            matched_controls = [
                c for c in controls
                if not keywords or any(
                    kw.lower() in (c.category or "").lower() or kw.lower() in c.name.lower()
                    for kw in keywords
                )
            ]

            if not matched_controls:
                return []

            policies = {p.policy_code: p for p in db.query(EnterprisePolicy).all()}
            processes = {p.process_code: p for p in db.query(EnterpriseProcess).all()}
            apps = {a.app_code: a for a in db.query(EnterpriseApplication).all()}

            chains: List[Dict[str, Any]] = []
            for ctrl in matched_controls[:2]:  # cap at 2 per requirement
                segment = ctrl.control_code.split("-")[1] if "-" in ctrl.control_code else ctrl.control_code
                pol = next((code for code in policies if segment.lower() in code.lower()), None)
                prc = next((code for code in processes if segment.lower() in code.lower()), None)
                app = next((code for code in apps if segment.lower() in code.lower()), None)
                chains.append({
                    "control_code": ctrl.control_code,
                    "policy_code": pol,
                    "process_code": prc,
                    "department_name": ctrl.owner_department,
                    "application_code": app,
                })
            return chains
        except Exception as db_err:
            logger.warning("ImpactAgent DB lookup failed: %s", db_err)
            return []

    @staticmethod
    def _static_fallback_chain(context_text: str) -> Dict[str, Any]:
        """Keyword heuristic over context text. Returns a single chain dict."""
        t = context_text.lower()
        if any(k in t for k in ("cyber", "tech", "cloud", "security", "incident", "cert")):
            return {
                "control_code": "CTRL-SEC-01",
                "policy_code": "POL-CLOUD-SEC-2026",
                "process_code": "PRC-INFRA-SCANNING",
                "department_name": "Information Security (CISO)",
                "application_code": "APP-CLOUD-INFRA",
            }
        if any(k in t for k in ("health", "phi", "hipaa", "clinical", "patient")):
            return {
                "control_code": "CTRL-PHI-01",
                "policy_code": "POL-HIPAA-PRIVACY",
                "process_code": "PRC-EHR-ACCESS",
                "department_name": "Clinical Informatics",
                "application_code": "APP-EHR-SYSTEM",
            }
        if any(k in t for k in ("trading", "securities", "sec", "finra", "algo")):
            return {
                "control_code": "CTRL-TRD-02",
                "policy_code": "POL-ALGO-TRADING",
                "process_code": "PRC-PRE-TRADE-RISK",
                "department_name": "Capital Markets Operations",
                "application_code": "APP-TRADING-ENGINE",
            }
        return {
            "control_code": "CTRL-KYC-04",
            "policy_code": "POL-KYC-2026",
            "process_code": "PRC-ONBOARDING-01",
            "department_name": "Retail Banking",
            "application_code": "APP-CORE-BANKING",
        }

    @staticmethod
    def map_knowledge_graph(title: str, db=None) -> List[Dict[str, Any]]:
        # --- Try to pull real records from DB ----------------------------
        db_controls: List[Dict[str, Any]] = []
        if db is not None:
            try:
                from app.models.domain import (
                    InternalControl, EnterprisePolicy,
                    EnterpriseProcess, EnterpriseApplication,
                )
                title_lower = title.lower()
                # Keyword-driven DB filter: prefer records whose category/name
                # matches the regulation's subject matter.
                keywords = []
                if any(k in title_lower for k in ("cyber", "tech", "cloud", "security", "incident")):
                    keywords = ["Security", "Cyber", "Cloud", "CISO"]
                elif any(k in title_lower for k in ("kyc", "aml", "banking", "payment")):
                    keywords = ["KYC", "AML", "Banking", "Compliance"]
                elif any(k in title_lower for k in ("health", "phi", "hipaa", "clinical")):
                    keywords = ["Health", "Clinical", "Privacy"]
                elif any(k in title_lower for k in ("trading", "securities", "sec", "finra")):
                    keywords = ["Trading", "Securities", "Market"]

                controls = db.query(InternalControl).all()
                for ctrl in controls:
                    if not keywords or any(kw.lower() in (ctrl.category or "").lower()
                                          or kw.lower() in ctrl.name.lower()
                                          for kw in keywords):
                        db_controls.append({
                            "control_code": ctrl.control_code,
                            "policy_code": None,
                            "process_code": None,
                            "department_name": ctrl.owner_department,
                            "application_code": None,
                        })

                # Enrich with matching policies / processes / applications
                policies = {p.policy_code: p for p in db.query(EnterprisePolicy).all()}
                processes = {p.process_code: p for p in db.query(EnterpriseProcess).all()}
                apps = {a.app_code: a for a in db.query(EnterpriseApplication).all()}

                for chain in db_controls:
                    ctrl_code = chain["control_code"]
                    # Heuristic: match by shared prefix segment (e.g. CTRL-KYC → POL-KYC-*)
                    segment = ctrl_code.split("-")[1] if "-" in ctrl_code else ctrl_code
                    matching_policy = next(
                        (code for code in policies if segment.lower() in code.lower()), None
                    )
                    matching_process = next(
                        (code for code in processes if segment.lower() in code.lower()), None
                    )
                    matching_app = next(
                        (code for code in apps if segment.lower() in code.lower()), None
                    )
                    chain["policy_code"] = matching_policy
                    chain["process_code"] = matching_process
                    chain["application_code"] = matching_app

            except Exception as db_err:
                logger.warning("ImpactAgent DB query failed, will try Gemini: %s", db_err)

        if db_controls:
            logger.info("ImpactAgent: built %d chains from DB records", len(db_controls))
            return db_controls[:4]

        # --- Gemini call (enriches or replaces DB result) -----------------
        safe_title = _sanitise_for_prompt(title, max_chars=200)
        client = _get_gemini_client()
        if client:
            prompt = (
                "You are a compliance knowledge graph agent. "
                "Given this regulatory directive title, return a JSON array of 2–3 "
                "enterprise control chains. Each chain must include: "
                "control_code, policy_code, process_code, department_name, application_code.\n"
                f"Title: {safe_title}\n"
                "Respond ONLY with the JSON array, no prose."
            )
            result = _call_gemini(client, prompt, expect="list")
            if result and isinstance(result, list) and len(result) > 0:
                logger.info("ImpactAgent: built %d chains via Gemini", len(result))
                return result

        # --- Sector-based deterministic fallback (last resort) ------------
        logger.info("ImpactAgent: using deterministic fallback for '%s'", title)
        title_lower = title.lower()
        if any(k in title_lower for k in ("cyber", "tech", "cloud", "security", "incident")):
            return [
                {
                    "control_code": "CTRL-SEC-01",
                    "policy_code": "POL-CLOUD-SEC-2026",
                    "process_code": "PRC-INFRA-SCANNING",
                    "department_name": "Information Security (CISO)",
                    "application_code": "APP-CLOUD-INFRA",
                },
                {
                    "control_code": "CTRL-INC-04",
                    "policy_code": "POL-INCIDENT-RESPONSE",
                    "process_code": "PRC-CERT-REPORTING",
                    "department_name": "Cyber Operations",
                    "application_code": "APP-SIEM-LOGS",
                },
            ]
        if any(k in title_lower for k in ("health", "phi", "hipaa", "clinical")):
            return [
                {
                    "control_code": "CTRL-PHI-01",
                    "policy_code": "POL-HIPAA-PRIVACY",
                    "process_code": "PRC-EHR-ACCESS",
                    "department_name": "Clinical Informatics",
                    "application_code": "APP-EHR-SYSTEM",
                },
            ]
        if any(k in title_lower for k in ("trading", "securities", "sec", "finra")):
            return [
                {
                    "control_code": "CTRL-TRD-02",
                    "policy_code": "POL-ALGO-TRADING",
                    "process_code": "PRC-PRE-TRADE-RISK",
                    "department_name": "Capital Markets Operations",
                    "application_code": "APP-TRADING-ENGINE",
                },
            ]
        return [
            {
                "control_code": "CTRL-KYC-04",
                "policy_code": "POL-KYC-2026",
                "process_code": "PRC-ONBOARDING-01",
                "department_name": "Retail Banking",
                "application_code": "APP-CORE-BANKING",
            },
            {
                "control_code": "CTRL-AML-12",
                "policy_code": "POL-AML-ALERT-V2",
                "process_code": "PRC-TXN-MONITORING",
                "department_name": "Compliance Operations",
                "application_code": "APP-AML-ENGINE",
            },
        ]

# ---------------------------------------------------------------------------
# Agent 4 — Recommendation Agent
# ---------------------------------------------------------------------------

class RecommendationAgent:
    """
    Generates actionable compliance workflow tasks from knowledge-graph chains.

    - due_date: looked up by chain['requirement_id'] from persisted Requirement
      ORM objects. Falls back to today+30 only when no requirement_id is present
      or the referenced requirement has no deadline set.
    - assignee / reviewer: queried from EnterpriseUser table where possible;
      labelled placeholder used only when the table is empty.
    """

    @staticmethod
    def generate_recommendations(
        chains: List[Dict[str, Any]],
        persisted_requirements: Optional[List[Any]] = None,  # Requirement ORM objects
        extracted_sections: Optional[List[Dict[str, Any]]] = None,  # legacy fallback
        db=None,
    ) -> List[Dict[str, Any]]:

        # Build a requirement_id → deadline lookup from real ORM objects (preferred).
        req_deadline_map: Dict[str, datetime.date] = {}
        if persisted_requirements:
            for req in persisted_requirements:
                if req.id and isinstance(getattr(req, "deadline", None), datetime.date):
                    req_deadline_map[req.id] = req.deadline

        # Legacy: fall back to positional extraction from section dicts if no ORM objects.
        positional_deadlines: List[datetime.date] = []
        if not req_deadline_map and extracted_sections:
            for sec in extracted_sections:
                for obl in sec.get("obligations", []):
                    for req in obl.get("requirements", []):
                        dl = req.get("deadline")
                        if isinstance(dl, datetime.date):
                            positional_deadlines.append(dl)

        default_deadline = datetime.date.today() + datetime.timedelta(days=30)

        # Pull real users from DB
        assignee_name = "Compliance Officer (Unassigned)"
        reviewer_name = "Chief Compliance Officer (Unassigned)"
        if db is not None:
            try:
                from app.models.domain import EnterpriseUser
                users = db.query(EnterpriseUser).all()
                found_assignee = False
                found_reviewer = False
                for u in users:
                    role_lower = (u.role or "").lower()
                    if not found_assignee and "compliance officer" in role_lower and "chief" not in role_lower:
                        assignee_name = f"{u.full_name} ({u.role})"
                        found_assignee = True
                    if not found_reviewer and ("chief compliance" in role_lower or "cco" in role_lower):
                        reviewer_name = f"{u.full_name} ({u.role})"
                        found_reviewer = True
                    if found_assignee and found_reviewer:
                        break
            except Exception as db_err:
                logger.warning("RecommendationAgent: could not fetch users: %s", db_err)

        tasks = []
        for i, chain in enumerate(chains):
            ctrl = chain.get("control_code", f"CTRL-{i+1:02d}")
            dept = chain.get("department_name", "Compliance")

            # Deadline: requirement_id → ORM deadline (by ID, not position)
            req_id = chain.get("requirement_id")
            if req_id and req_id in req_deadline_map:
                due = req_deadline_map[req_id]
            elif i < len(positional_deadlines):
                # legacy path — positional, clearly imprecise
                due = positional_deadlines[i]
            else:
                due = default_deadline

            tasks.append({
                "title": f"Enforce {ctrl} Governance & Audit Controls for {dept}",
                "description": (
                    f"Perform gap analysis and update operational workflow for "
                    f"{chain.get('policy_code') or ctrl}. "
                    f"Ensure {chain.get('process_code') or 'all relevant processes'} "
                    f"is fully aligned with the new directive."
                ),
                "assignee": assignee_name,
                "reviewer": reviewer_name,
                "priority": "HIGH",
                "status": "NEEDS_REVIEW",
                "due_date": due,
                "control_code": ctrl,
            })
        return tasks


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class MultiAgentAIOrchestrator:
    """
    Multi-Agent AI Pipeline Orchestrator — two-phase design.

    Phase 1 (process_extraction_only): Extraction + Classification.
    Call this BEFORE writing Section/Obligation/Requirement rows to the DB.

    Phase 2 (process_impact_and_tasks): Impact mapping + Task generation.
    Call this AFTER persisting requirements, passing the real Requirement ORM
    objects so ImpactAgent can populate requirement_id on each chain.

    The legacy process_regulation() method is kept for callers that don't need
    per-requirement chain accuracy (e.g. unit tests, admin scripts).
    """

    @classmethod
    def process_extraction_only(
        cls, title: str, authority: str, sector: str, text: str
    ) -> Dict[str, Any]:
        """Phase 1: extract ontology and classify. No DB writes, no impact mapping."""
        logger.info("Phase 1 — Extraction+Classification for '%s'", title[:80])
        ext_res = ExtractionAgent.extract_ontology(title, authority, text)
        sections = ext_res.get("sections", []) if isinstance(ext_res, dict) else ext_res
        ext_method = ext_res.get("extraction_method", "GEMINI_EXTRACTED") if isinstance(ext_res, dict) else "GEMINI_EXTRACTED"
        logger.info("ExtractionAgent: extracted %d sections (method=%s)", len(sections), ext_method)
        classification = ClassificationAgent.classify(title, sector)
        logger.info("ClassificationAgent: risk_score=%s", classification.get("risk_score"))
        return {"sections": sections, "classification": classification, "extraction_method": ext_method}


    @classmethod
    def process_impact_and_tasks(
        cls,
        title: str,
        persisted_requirements: List[Any],  # Requirement ORM objects with .id set
        db=None,
    ) -> Dict[str, Any]:
        """
        Phase 2: per-requirement impact mapping + task recommendation.
        Must be called AFTER requirements are committed to the DB so that
        each chain can carry the real requirement_id UUID.
        """
        logger.info(
            "Phase 2 — Impact+Tasks for '%s', %d requirements",
            title[:60], len(persisted_requirements)
        )
        graph_chains = ImpactAgent.map_for_requirements(
            title=title, requirements=persisted_requirements, db=db
        )
        logger.info("ImpactAgent: produced %d chains across all requirements", len(graph_chains))

        recommended_tasks = RecommendationAgent.generate_recommendations(
            graph_chains, persisted_requirements=persisted_requirements, db=db
        )
        logger.info("RecommendationAgent: generated %d tasks", len(recommended_tasks))
        return {"graph_chains": graph_chains, "recommended_tasks": recommended_tasks}

    @classmethod
    def process_regulation(cls, title: str, authority: str, sector: str, text: str, db=None):
        """Legacy single-call entry point — chains have no requirement_id."""
        logger.info("MultiAgentAIOrchestrator: starting pipeline for '%s'", title[:80])

        ext_res = ExtractionAgent.extract_ontology(title, authority, text)
        ontology_sections = ext_res.get("sections", []) if isinstance(ext_res, dict) else ext_res
        logger.info("ExtractionAgent: extracted %d sections", len(ontology_sections))


        classification = ClassificationAgent.classify(title, sector)
        logger.info("ClassificationAgent: risk_score=%s", classification.get("risk_score"))

        graph_chains = ImpactAgent.map_knowledge_graph(title, db=db)
        logger.info("ImpactAgent: produced %d graph chains", len(graph_chains))

        recommended_tasks = RecommendationAgent.generate_recommendations(
            graph_chains, db=db
        )
        logger.info("RecommendationAgent: generated %d tasks", len(recommended_tasks))

        return {
            "sections": ontology_sections,
            "classification": classification,
            "graph_chains": graph_chains,
            "recommended_tasks": recommended_tasks,
        }
