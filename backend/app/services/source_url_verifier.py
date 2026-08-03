"""
Source-URL Live Grounding Verifier
===================================
Fetches the live source_url of a regulation and computes text overlap
against the stored content_text to detect:
  - Content drift (regulation was amended but stored text not updated)
  - Wrong source URL (URL links to a different document entirely)
  - JavaScript-rendered pages (fetch returns HTML shell with no content)
  - Fetch failures (network errors, timeouts, 404s)

This is the structural fix for the circularity problem:
  existing checks: "does extracted claim match content_text?"
  this check:      "does content_text match the actual live source?"

Result codes (stored in source_url_verified):
  0  = unchecked
  1  = VERIFIED (overlap >= threshold)
 -1  = MISMATCH (drift detected, wrong source, or unrenderable page)
"""

import re
import logging
import datetime
import html.parser
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("compliance_platform.source_url_verifier")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
# Key-phrase overlap: what fraction of distinctive stored phrases found live
PHRASE_VERIFIED_THRESHOLD = 0.25    # >= 25% of key phrases found → VERIFIED
PHRASE_DRIFT_THRESHOLD    = 0.10    # 10-25% → CONTENT_DRIFT_DETECTED
# N-gram overlap fallback
NGRAM_VERIFIED_THRESHOLD  = 0.15    # trigram Jaccard >= 15% → VERIFIED (generous: live pages have navigation text)

# Pages where raw HTML contains <script> but almost no readable text
JS_RENDER_MIN_TEXT_RATIO  = 0.05    # if readable text < 5% of total bytes → JS_RENDER_REQUIRED


# ---------------------------------------------------------------------------
# HTML text extractor (no external libraries required)
# ---------------------------------------------------------------------------
class _TextExtractor(html.parser.HTMLParser):
    """Strip HTML tags, returning plain text."""
    SKIP_TAGS = {"script", "style", "noscript", "head", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self._buf: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._buf.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._buf)


def _html_to_text(html_content: str) -> str:
    extractor = _TextExtractor()
    try:
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception:
        # Fallback: crude tag strip
        return re.sub(r"<[^>]+>", " ", html_content)


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------
def fetch_url_text(url: str, timeout: int = 12, authority: str = "RBI") -> Tuple[Optional[str], str]:
    """
    Fetch URL and extract clean regulation text (stripping navigation chrome).
    Routes FINRA requests to FINRAOfficialAdapter (RSS / Data API / Manual upload).
    Returns (text_or_None, status_code)
    Status codes: OK | FETCH_FAILED | JS_RENDER_REQUIRED | HTTP_ERROR_{code}
    """
    try:
        from app.acl.adapters import _validate_url
        _validate_url(url)
    except Exception as ssrf_err:
        logger.warning("SSRF validation blocked URL %s: %s", url, ssrf_err)
        return None, "FETCH_FAILED"

    # Route FINRA authorities to official legal adapter
    if "FINRA" in (authority or "").upper() or "finra.org" in url.lower():
        from app.services.regulation_content_extractor import FINRAOfficialAdapter, RegulationContentExtractor

        # 1. Try official RSS feed or Data API
        rss_res = FINRAOfficialAdapter.fetch_regulatory_notices(rss_url=url if "rss" in url.lower() else FINRAOfficialAdapter.FINRA_RSS_URL)
        if rss_res.get("status") == "SUCCESS" and rss_res.get("content_text"):
            return RegulationContentExtractor.extract_clean_text(rss_res["content_text"]), "OK"


        # 2. Try manual upload directory fallback
        manual_res = FINRAOfficialAdapter.load_manual_upload()
        if manual_res.get("status") == "SUCCESS" and manual_res.get("content_text"):
            return manual_res["content_text"], "OK"

        return None, "FETCH_FAILED"


    raw_bytes = None
    content_type = ""

    # Standard clean HTTP request
    try:
        import urllib.request
        headers = {
            "User-Agent": "ReguGuardAI-CompliancePlatform/1.0 (compliance@reguguard.ai)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as e:
        logger.warning("Source URL fetch failed for %s: %s", url, e)
        return None, "FETCH_FAILED"



    # Handle binary PDF documents (e.g. RBI/SEBI/SEC PDF downloads)
    if raw_bytes.startswith(b"%PDF") or "application/pdf" in content_type.lower() or url.lower().split("?")[0].endswith(".pdf"):
        try:
            import io
            import pypdf
            pdf_file = io.BytesIO(raw_bytes)
            reader = pypdf.PdfReader(pdf_file)
            pages_text = []
            for page in reader.pages:
                t = page.extract_text()
                if t and t.strip():
                    pages_text.append(t.strip())
            if pages_text:
                pdf_clean = "\n\n".join(pages_text)
                return pdf_clean, "OK"
        except Exception as pdf_err:
            logger.warning("pypdf text extraction failed for %s: %s", url, pdf_err)

    # Detect encoding for HTML/Text content
    encoding = "utf-8"
    if "charset=" in content_type:
        try:
            encoding = content_type.split("charset=")[-1].strip().split(";")[0]
        except Exception:
            pass

    try:
        raw_text = raw_bytes.decode(encoding, errors="replace")
    except Exception:
        raw_text = raw_bytes.decode("utf-8", errors="replace")


    # Extract clean content using RegulationContentExtractor
    try:
        from app.services.regulation_content_extractor import RegulationContentExtractor
        plain_text = RegulationContentExtractor.extract_clean_text(raw_text, authority=authority)
    except Exception as exc:
        logger.warning("ContentExtractor failed, using fallback _html_to_text: %s", exc)
        plain_text = _html_to_text(raw_text)

    readable_chars = len(plain_text.strip())
    total_chars = len(raw_text)

    if total_chars > 0 and readable_chars / total_chars < JS_RENDER_MIN_TEXT_RATIO and total_chars > 2000:
        logger.info("Source URL %s appears JS-rendered (readable ratio=%.2f)", url, readable_chars / total_chars)
        return plain_text if plain_text.strip() else None, "JS_RENDER_REQUIRED"

    return plain_text, "OK"



# ---------------------------------------------------------------------------
# N-gram overlap (trigrams)
# ---------------------------------------------------------------------------
def _trigram_jaccard(text_a: str, text_b: str) -> float:
    """Jaccard similarity of character trigrams between two texts."""
    def trigrams(t: str) -> set:
        t = re.sub(r"\s+", " ", t.lower().strip())
        return {t[i:i+3] for i in range(len(t) - 2)} if len(t) >= 3 else set()

    a, b = trigrams(text_a), trigrams(text_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Key-phrase extraction from stored content_text
# ---------------------------------------------------------------------------
def _extract_key_phrases(stored_text: str, n: int = 15) -> List[str]:
    """
    Extract distinctive phrases from stored content_text:
    - Section/clause numbers (e.g. "Section 70B", "Regulation 7(1)")
    - Numeric deadlines (e.g. "6 hours", "180 days", "two years")
    - Quoted statutory references
    - Document numbers (e.g. "CERT-In Directions No. 20(3)/2022")
    """
    patterns = [
        r"\b(?:Section|Clause|Regulation|Article|Para|Sub-section)\s+[\d\w()./-]+",
        r"\b\d+[\s-]*(?:hours?|days?|years?|months?)\b",
        r"\b(?:RBI|CERT-In|SEBI|IRDAI|FEMA|IT Act|BR Act|PMLA|HIPAA|SEC|FINRA)\s+[\w/.()-]+",
        r"\b\d{4}-\d{2}-\d{2}\b",  # dates
        r"(?:No\.|Number)\s+[\w/.()-]+",
        r"[A-Z]{2,}\.?\s+\d+/\d+",  # doc numbers
    ]
    phrases = []
    for pattern in patterns:
        matches = re.findall(pattern, stored_text, re.IGNORECASE)
        phrases.extend(m.strip() for m in matches if len(m.strip()) >= 4)

    # Deduplicate and return top n
    seen = set()
    unique = []
    for p in phrases:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:n]


# ---------------------------------------------------------------------------
# Main overlap computation
# ---------------------------------------------------------------------------
def compute_text_overlap(stored_text: str, live_text: str) -> Dict[str, Any]:
    """
    Compute overlap between stored content_text and freshly fetched live_text.
    Returns:
      overlap_score: float 0.0-1.0 (primary signal)
      ngram_jaccard: float (secondary)
      key_phrases_total: int
      key_phrases_matched: int
      matched_phrases: list of matched phrases
    """
    if not stored_text or not live_text:
        return {
            "overlap_score": 0.0, "ngram_jaccard": 0.0,
            "key_phrases_total": 0, "key_phrases_matched": 0,
            "matched_phrases": []
        }

    live_lower = live_text.lower()
    key_phrases = _extract_key_phrases(stored_text)
    matched = [p for p in key_phrases if p.lower() in live_lower]
    phrase_score = len(matched) / max(1, len(key_phrases))
    ngram_score = _trigram_jaccard(stored_text[:3000], live_text[:6000])

    # Primary score: weighted combination favouring key-phrase hits
    # (key phrases are far more distinctive than raw trigrams for legal text)
    overlap_score = (phrase_score * 0.70) + (ngram_score * 0.30)

    return {
        "overlap_score": round(overlap_score, 3),
        "phrase_score": round(phrase_score, 3),
        "ngram_jaccard": round(ngram_score, 3),
        "key_phrases_total": len(key_phrases),
        "key_phrases_matched": len(matched),
        "matched_phrases": matched[:8],  # return up to 8 for display
    }


# ---------------------------------------------------------------------------
# Orchestrator: verify + persist to Regulation row
# ---------------------------------------------------------------------------
def verify_regulation_source_url(reg, db=None) -> Dict[str, Any]:
    """
    Full source-URL verification for a Regulation ORM object.
    Fetches source_url, computes overlap, writes result back to reg.
    Persists via db if provided.

    Returns the verification result dict.
    """
    now = datetime.datetime.utcnow()

    if not reg.source_url:
        result = {
            "source_url_verified": 0,
            "source_url_verification_note": "NO_SOURCE_URL",
            "source_url_verification_score": None,
            "source_url_last_verified_at": now,
        }
        _apply_result(reg, result, db)
        return result

    logger.info("Verifying source URL for %s: %s", reg.id, reg.source_url)
    
    # Resolve index pages to direct document URLs
    from app.services.source_url_resolver import resolve_source_url
    target_url = reg.source_url
    try:
        resolved_url, was_index, reason = resolve_source_url(reg.source_url, reg.title or "", reg.doc_number or "")
        if was_index and resolved_url and resolved_url != reg.source_url:
            reg.resolved_source_url = resolved_url
            target_url = resolved_url
            logger.info("Resolved index page URL to direct link for %s: %s", reg.id, resolved_url)
    except Exception as exc:
        logger.warning("URL resolution failed for %s: %s", reg.id, exc)

    live_text, fetch_status = fetch_url_text(target_url, authority=reg.authority or "RBI")



    if fetch_status == "FETCH_FAILED" or live_text is None:
        result = {
            "source_url_verified": 0,
            "source_url_verification_note": "FETCH_FAILED",
            "source_url_verification_score": None,
            "source_url_last_verified_at": now,
            "possible_amendment_detected": reg.possible_amendment_detected or 0,
        }
        _apply_result(reg, result, db)
        return result

    overlap = compute_text_overlap(reg.content_text or "", live_text)
    score = overlap["overlap_score"]

    if fetch_status == "JS_RENDER_REQUIRED" and score < PHRASE_DRIFT_THRESHOLD:
        note = "JS_RENDER_REQUIRED"
        verified = 0
    elif score >= PHRASE_VERIFIED_THRESHOLD:
        note = "VERIFIED"
        verified = 1
    elif score >= PHRASE_DRIFT_THRESHOLD:
        note = "CONTENT_DRIFT_DETECTED"
        verified = -1
    else:
        # Very low overlap — either wrong URL or JS-rendered
        note = "POSSIBLE_WRONG_SOURCE_OR_JS_RENDERED" if fetch_status == "JS_RENDER_REQUIRED" else "LOW_OVERLAP_UNVERIFIED"
        verified = -1

    # Amendment drift: check if matched phrases are significantly fewer than at first ingestion
    # (rough heuristic: if score drops below 50% of verified threshold = possible amendment)
    possible_amendment = 1 if (verified == -1 and reg.source_url_verified == 1) else (reg.possible_amendment_detected or 0)

    result = {
        "source_url_verified": verified,
        "source_url_verification_note": note,
        "source_url_verification_score": score,
        "source_url_last_verified_at": now,
        "possible_amendment_detected": possible_amendment,
        # Diagnostic detail (not stored on model, returned in API response)
        "fetch_status": fetch_status,
        "key_phrases_total": overlap["key_phrases_total"],
        "key_phrases_matched": overlap["key_phrases_matched"],
        "matched_phrases": overlap["matched_phrases"],
        "phrase_score": overlap["phrase_score"],
        "ngram_jaccard": overlap["ngram_jaccard"],
    }

    if verified == -1:
        reg.needs_human_review = 1
        if possible_amendment:
            logger.warning(
                "POSSIBLE_AMENDMENT detected for %s (%s): source URL content changed since last verification",
                reg.id, reg.title
            )

    _apply_result(reg, result, db)

    logger.info(
        "Source URL verification for %s: %s (score=%.3f, phrases=%d/%d)",
        reg.id, note, score,
        overlap["key_phrases_matched"], overlap["key_phrases_total"]
    )
    return result


def _apply_result(reg, result: Dict[str, Any], db=None):
    """Write verification fields back to the ORM object and optionally persist."""
    for field in ["source_url_verified", "source_url_verification_note",
                  "source_url_verification_score", "source_url_last_verified_at",
                  "possible_amendment_detected"]:
        if field in result:
            setattr(reg, field, result[field])
    if db:
        db.commit()
