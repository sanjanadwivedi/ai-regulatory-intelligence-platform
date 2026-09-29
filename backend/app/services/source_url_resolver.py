"""
Intelligent Source URL Resolver Service
=========================================
Detects when a regulation's source_url points to an authority index/catalog page
(e.g., RBI Circular Index, SEBI Circulars list, PIB press list) instead of a direct document.
Parses the index page HTML to locate the specific circular/directive link matching doc_number,
publication_date, or title keywords.

Cache layer: 24-hour in-memory cache to prevent repeated crawls of index pages.
Fallbacks: Returns original URL on network errors, 403, missing matches, or non-index URLs.
"""

import re
import logging
import datetime
import urllib.request
import urllib.parse
import html.parser
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("compliance_platform.source_url_resolver")

# 24-Hour Cache: { cache_key -> (resolved_url, expires_at_timestamp) }
_URL_RESOLUTION_CACHE: Dict[str, Tuple[str, datetime.datetime]] = {}
CACHE_TTL_HOURS = 24

# Index URL patterns & keywords
INDEX_URL_KEYWORDS = [
    "index", "catalog", "list", "browse", "search", "notificationuser.aspx",
    "circularindexdisplay.aspx", "viewmasdirections.aspx", "circulars", "pressreleases"
]


def is_index_page(url: str, html_text: Optional[str] = None) -> bool:
    """
    Determines if a given URL is an authority index/catalog page rather than a direct document.
    """
    if not url:
        return False

    url_lower = url.lower()

    # Direct document extensions or specific document ID query params are NOT index pages
    if any(url_lower.split("?")[0].endswith(ext) for ext in [".pdf", ".doc", ".docx", ".zip"]):
        return False

    if re.search(r"[?&](id|docid|prid|release_id|doc_id)=\d+", url_lower):
        return False

    # Check URL keywords
    if any(kw in url_lower for kw in INDEX_URL_KEYWORDS):
        return True


    # If HTML text is supplied, check HTML structure (high table/link density vs text length)
    if html_text:
        table_count = len(re.findall(r"<table", html_text, re.IGNORECASE))
        tr_count = len(re.findall(r"<tr", html_text, re.IGNORECASE))
        a_count = len(re.findall(r"<a\s", html_text, re.IGNORECASE))
        plain_len = len(re.sub(r"<[^>]+>", " ", html_text).strip())

        if table_count >= 1 and tr_count >= 5 and a_count >= 10 and plain_len < 25000:
            return True

    return False


class _IndexLinkParser(html.parser.HTMLParser):
    """Parses HTML <a> tags and <table> rows to extract (text, href) pairs."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: List[Tuple[str, str]] = []  # (link_text, absolute_href)
        self.current_href: Optional[str] = None
        self.current_text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for name, val in attrs:
                if name.lower() == "href" and val:
                    self.current_href = urllib.parse.urljoin(self.base_url, val)
                    self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            text = data.strip()
            if text:
                self.current_text.append(text)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href:
            link_str = " ".join(self.current_text).strip()
            if link_str:
                self.links.append((link_str, self.current_href))
            self.current_href = None
            self.current_text = []


def resolve_source_url(
    original_url: str,
    regulation_title: str = "",
    doc_number: str = "",
    force_refresh: bool = False
) -> Tuple[str, bool, str]:
    """
    Resolves an index URL to a direct document URL.
    Returns: (resolved_url, was_index_page, resolution_reason)
    """
    if not original_url:
        return "", False, "No URL provided"

    # Enforce SSRF protection check
    try:
        from app.acl.adapters import _validate_url
        _validate_url(original_url)
    except Exception as ssrf_err:
        logger.warning("SSRF validation blocked URL resolution for %s: %s", original_url, ssrf_err)
        return original_url, False, f"SSRF blocked: {str(ssrf_err)}"

    # Step 1: Check cache

    cache_key = f"{original_url}:::{doc_number}:::{regulation_title[:40]}"
    now = datetime.datetime.utcnow()
    if not force_refresh and cache_key in _URL_RESOLUTION_CACHE:
        cached_url, expires_at = _URL_RESOLUTION_CACHE[cache_key]
        if now < expires_at:
            logger.info("Cache hit for URL resolution: %s -> %s", original_url, cached_url)
            return cached_url, (cached_url != original_url), "Cache hit (resolved in last 24h)"

    # Step 2: Check if already a direct document URL
    if not is_index_page(original_url):
        return original_url, False, "Direct document URL (not an index page)"

    # Step 3: Fetch index page raw HTML directly (preserving <a> tags and href attributes)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(original_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_bytes = resp.read()
            html_text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Failed to fetch raw HTML index page for resolution %s: %s", original_url, exc)
        return original_url, True, f"Fetch error: {exc}"

    if not html_text:
        return original_url, True, "Empty index page response. Fallback to original."


    # Step 4: Parse links
    parser = _IndexLinkParser(original_url)
    try:
        parser.feed(html_text)
        links = parser.links
    except Exception:
        # Regex fallback for links
        links = []
        for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.IGNORECASE | re.DOTALL):
            href = urllib.parse.urljoin(original_url, match.group(1))
            text = re.sub(r"<[^>]+>", " ", match.group(2)).strip()
            if text and href:
                links.append((text, href))

    if not links:
        return original_url, True, "Index page contained no parseable document links. Fallback to original."

    # Clean target keywords for matching
    doc_num_clean = doc_number.strip().lower() if doc_number else ""
    title_clean = regulation_title.strip().lower() if regulation_title else ""

    # Clean doc_number variants (e.g., "RBI/2026-27/203" -> "203", "2026-27/203")
    doc_parts = [p for p in re.split(r"[/\s-]+", doc_num_clean) if len(p) >= 2]

    best_match_url = None
    reason = ""

    # Priority 1: Match doc_number in link text or href
    if doc_num_clean:
        # Require substantial match, e.g., the specific reference number like "203" or "RBI/2026-27"
        important_parts = [p for p in doc_parts if len(p) >= 3 and p not in ('circular', 'series', 'no.', 'no')]
        for text, href in links:
            if doc_num_clean in text.lower() or doc_num_clean in href.lower():
                best_match_url = href
                reason = f"Matched exact doc_number '{doc_number}' in index row link"
                break
            # Stricter partial match
            if len(important_parts) >= 2:
                # Require at least 2 distinct important parts to match
                matches = sum(1 for p in important_parts if p in text.lower())
                if matches >= 2:
                    best_match_url = href
                    reason = f"Matched doc_number parts {important_parts} in index row link"
                    break

    # Priority 2: Match title keywords if doc_number failed
    if not best_match_url and title_clean:
        title_keywords = [
            w for w in re.split(r"\W+", title_clean)
            if len(w) >= 4 and w not in {
                "master", "direction", "circular", "amendment", "guidelines",
                "flagged", "scan", "notification", "index", "rules", "accounts"
            }
        ]
        if len(title_keywords) >= 2:
            min_matches = max(2, int(len(title_keywords) * 0.7)) # Require 70% or at least 2 distinct words
            for text, href in links:
                matched_kws = [kw for kw in title_keywords if kw in text.lower()]
                if len(matched_kws) >= min_matches:
                    best_match_url = href
                    reason = f"Matched title keywords {matched_kws} in index link '{text[:40]}...'"
                    break

    if best_match_url:
        expires_at = now + datetime.timedelta(hours=CACHE_TTL_HOURS)
        _URL_RESOLUTION_CACHE[cache_key] = (best_match_url, expires_at)
        logger.info("Successfully resolved index URL %s -> %s (%s)", original_url, best_match_url, reason)
        return best_match_url, True, reason

    return None, True, "Multiple official documents found but exact circular match could not be established."
