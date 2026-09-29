import logging
import urllib.request
import urllib.error
import urllib.parse
import re
from typing import Dict, Any

from app.models.domain import Regulation
from app.acl.adapters import _validate_url

logger = logging.getLogger("compliance_platform.human_verification_service")

class HumanVerificationService:
    @staticmethod
    def verify_source(regulation: Regulation, url: str) -> Dict[str, Any]:
        """
        Deterministically verifies if a human-supplied URL matches the exact identity
        of the target regulation.
        """
        checks = {
            "https": False,
            "authoritative_domain": False,
            "reachable": False,
            "document_type": False,
            "reference_match": False,
            "title_match": False
        }
        
        # 1. Check HTTPS
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme == "https":
            checks["https"] = True
            
        # 2. Check authoritative domain
        authority = (regulation.authority or "RBI").upper()
        
        domain = parsed.netloc.lower()
        if authority == "RBI":
            if domain in ("rbi.org.in", "www.rbi.org.in", "rbidocs.rbi.org.in"):
                checks["authoritative_domain"] = True
        elif authority == "SEBI":
            if "sebi.gov.in" in domain:
                checks["authoritative_domain"] = True
        elif authority == "FINRA":
            if "finra.org" in domain:
                checks["authoritative_domain"] = True
        else:
            checks["authoritative_domain"] = True

        try:
            _validate_url(url)
        except Exception:
            return {
                "valid": False,
                "status": "INVALID_URL_SCHEME",
                "canonical_url": None,
                "checks": checks,
                "reason": "URL validation blocked (SSRF check failed)."
            }

        if not checks["https"] or not checks["authoritative_domain"]:
            return {
                "valid": False,
                "status": "DOMAIN_VALIDATION_FAILED",
                "canonical_url": None,
                "checks": checks,
                "reason": "URL must use HTTPS and belong to the authoritative domain."
            }

        # 3. Reachability & Document Type & Extraction
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AegisAI-CompliancePlatform/1.0 (compliance@aegis.ai)", "Accept": "text/html,application/xhtml+xml,application/pdf,*/*"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "").lower()
                content = resp.read()

                if status == 200:
                    checks["reachable"] = True

                # ------------------------------------------------------------------
                # Anti-bot / challenge-page detection
                # Runs BEFORE document_type is evaluated.
                # Checks three independent signals in the actual response bytes:
                #   Signal A – URL claims to be a PDF but server returned text/html
                #   Signal B – Imperva/TSPD bot-protection JavaScript markers
                #   Signal C – Non-empty content with no PDF magic bytes for a .pdf URL
                # Any one signal is sufficient to declare retrieval blocked.
                # This does NOT verify identity – it reports a transparent fetch failure.
                # ------------------------------------------------------------------
                url_path_lower = url.lower().split("?")[0]
                url_is_pdf = url_path_lower.endswith(".pdf")

                # Signal A: PDF URL served HTML
                signal_a = url_is_pdf and "text/html" in content_type

                # Signal B: Known Imperva / TSPD / SiteLock challenge markers in body
                _bot_markers = (
                    b"TSPD_101",           # Imperva ThreatStopper session cookie prefix
                    b"window[\"bobcmn\"",  # Imperva client-side challenge bootstrap
                    b"window[\"failureConfig\"",  # Imperva failure handler
                    b"tsmd=",              # ThreatStopper metadata cookie
                    b"_tfa_",             # Additional Imperva tracking token
                )
                _sample = content[:16384]  # inspect first 16 KB only
                signal_b = any(marker in _sample for marker in _bot_markers)

                # Signal C: URL looks like a PDF but content has no %PDF header
                signal_c = url_is_pdf and len(content) > 512 and not content.startswith(b"%PDF")

                if signal_a or signal_b or signal_c:
                    logger.warning(
                        "Anti-bot/challenge page detected for %s "
                        "(signal_a=%s signal_b=%s signal_c=%s content_type=%s)",
                        url, signal_a, signal_b, signal_c, content_type
                    )
                    checks["reachable"] = True   # server was reachable; the block is retrieval, not network
                    checks["document_type"] = False  # not a retrievable regulatory document
                    return {
                        "valid": False,
                        "status": "SOURCE_RETRIEVAL_BLOCKED",
                        "canonical_url": None,
                        "checks": checks,
                        "reason": (
                            "The authoritative domain is reachable and the URL is domain-eligible, "
                            "but the server returned a bot-protection/challenge page instead of the "
                            "actual regulatory document. Deterministic verification cannot be "
                            "completed against a challenge interstitial. Please confirm the direct "
                            "document URL bypasses any access gateway, or contact the document host."
                        )
                    }

                # document_type: PDF must be confirmed by magic bytes or content-type.
                # A .pdf URL extension alone is NOT sufficient if the body is HTML.
                is_real_pdf = "application/pdf" in content_type or content.startswith(b"%PDF")
                is_html = "text/html" in content_type
                if is_real_pdf or is_html:
                    checks["document_type"] = True

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return {
                "valid": False,
                "status": "UNREACHABLE",
                "canonical_url": None,
                "checks": checks,
                "reason": "The URL could not be fetched or returned an error."
            }

        if not checks["reachable"] or not checks["document_type"]:
            return {
                "valid": False,
                "status": "UNSUPPORTED_DOCUMENT",
                "canonical_url": None,
                "checks": checks,
                "reason": "The URL must be reachable and return a supported document type (PDF/HTML)."
            }

        extracted_text = ""
        is_pdf = False
        # Use the same strict PDF test: magic bytes or explicit content-type.
        # URL extension alone is excluded to match the tightened document_type gate above.
        if "application/pdf" in content_type or content.startswith(b"%PDF"):
            is_pdf = True
            import io, pypdf
            try:
                reader = pypdf.PdfReader(io.BytesIO(content))
                pages = []
                for p in reader.pages:
                    t = p.extract_text()
                    if t: pages.append(t)
                extracted_text = "\n".join(pages)
            except Exception as e:
                logger.warning(f"PDF extraction failed for {url}: {e}")
        
        if not is_pdf or not extracted_text.strip():
            from app.services.regulation_content_extractor import RegulationContentExtractor
            encoding = "utf-8"
            if "charset=" in content_type:
                try: encoding = content_type.split("charset=")[-1].strip().split(";")[0]
                except: pass
            try:
                raw_text = content.decode(encoding, errors="replace")
            except Exception:
                raw_text = content.decode("utf-8", errors="replace")
            
            try:
                extracted_text = RegulationContentExtractor.extract_clean_text(raw_text, authority=authority)
            except Exception:
                extracted_text = raw_text

        # 4. Identity Match
        
        def _normalize_text(t: str) -> str:
            """Aggressively normalizes text by stripping all punctuation and spaces, lowercasing it."""
            return re.sub(r"[\s\W_]+", "", t.lower())

        content_normalized = _normalize_text(extracted_text)
        
        doc_num_raw = regulation.doc_number or ""
        title_raw = regulation.title or ""
        
        # Check Reference Number
        if doc_num_raw:
            # We want to check if the essential parts of doc_num are in the text.
            # RBI/2026-27/203 A.P. (DIR Series) Circular No.19
            # Break down by major segments
            # Often the "RBI/2026-27/203" part is the strongest identifier
            match_part = re.search(r"([a-zA-Z]+/\d{4}-\d{2}/\d+)", doc_num_raw)
            if match_part:
                primary_ref = _normalize_text(match_part.group(1))
                if primary_ref in content_normalized:
                    checks["reference_match"] = True
            
            # If the regex doesn't match or fails, try a fallback of splitting by ' circular ' or similar
            if not checks["reference_match"]:
                # Normalizing the entire doc_number might be too strict if there's a missing space, but let's try
                # removing generic words
                stripped_doc_num = re.sub(r"(?i)\b(circular|series|no|master|direction)\b", "", doc_num_raw)
                if _normalize_text(stripped_doc_num) in content_normalized:
                    checks["reference_match"] = True

        # Check Title Keywords
        if title_raw:
            # Remove generic words
            generic_words = {"master", "direction", "circular", "amendment", "guidelines", "flagged", "scan", "notification", "index", "rules", "accounts", "the", "of", "and", "in", "to", "for"}
            title_clean = re.sub(r"[^\w\s]", " ", title_raw.lower())
            title_keywords = [w for w in title_clean.split() if w not in generic_words and len(w) >= 4]
            
            if len(title_keywords) >= 2:
                # Require 80% match
                min_matches = max(2, int(len(title_keywords) * 0.8))
                
                # Check against extracted_text with word boundaries (not aggressively normalized)
                extracted_text_lower = extracted_text.lower()
                matched_kws = [kw for kw in title_keywords if kw in extracted_text_lower]
                if len(matched_kws) >= min_matches:
                    checks["title_match"] = True
            elif len(title_keywords) == 1:
                # If only 1 strong keyword, require it
                if title_keywords[0] in extracted_text.lower():
                    checks["title_match"] = True
                    
        # Strict Identity Validation
        if doc_num_raw and title_raw:
            if checks["reference_match"] and checks["title_match"]:
                identity_established = True
                reason = "Both reference and strong title matched."
            elif checks["reference_match"]:
                identity_established = True
                reason = "Exact reference number matched."
            else:
                identity_established = False
                reason = "Document did not contain required reference number."
        elif doc_num_raw:
            if checks["reference_match"]:
                identity_established = True
                reason = "Exact reference number matched."
            else:
                identity_established = False
                reason = "Document did not contain the required reference number."
        elif title_raw:
            if checks["title_match"]:
                identity_established = True
                reason = "Strong title identity matched."
            else:
                identity_established = False
                reason = "Document did not contain sufficient title identity keywords."
        else:
            identity_established = False
            reason = "No regulatory metadata available to establish identity."
            
        if not identity_established:
            return {
                "valid": False,
                "status": "SOURCE_IDENTITY_MISMATCH",
                "canonical_url": None,
                "checks": checks,
                "reason": reason
            }
            
        return {
            "valid": True,
            "status": "VERIFIED",
            "canonical_url": url,
            "checks": checks,
            "reason": reason
        }
