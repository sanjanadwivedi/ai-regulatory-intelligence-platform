import logging
import time
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, urlunparse
from urllib.robotparser import RobotFileParser
from typing import List, Dict, Set, Optional, Tuple
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("compliance_platform.discovery_crawler")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

PRIORITY_KEYWORDS = [
    "about", "company", "who-we-are", "overview", "corporate",
    "business", "businesses", "what-we-do", "industries",
    "products", "services", "solutions", "offerings", "technology",
    "locations", "global-presence", "branches", "offices",
    "leadership", "management", "board", "organization",
    "investor", "annual-report", "filings", "governance",
    "compliance", "regulatory", "licenses", "security", "privacy", "sustainability", "careers"
]

EXCLUDE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".zip", ".tar", ".gz", ".exe", ".dmg", ".apk",
    ".mp4", ".mp3", ".wav", ".avi", ".mov",
    ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf"
}

EXCLUDE_PATHS = [
    "/login", "/signin", "/signup", "/auth", "/cart", "/checkout",
    "/logout", "/search", "/wp-json", "/api/", "/track", "/cookie",
    "/ru/", "/es/", "/pt/", "/cn/", "/tw/", "/ja/", "/de/", "/fr/"
]

class DiscoveredPage:
    def __init__(self, url: str, title: str, text_content: str, paragraphs: List[str]):
        self.url = url
        self.title = title
        self.text_content = text_content
        self.paragraphs = paragraphs

class CrawlResult:
    def __init__(
        self,
        pages: List[DiscoveredPage],
        submitted_url: str,
        final_url: str,
        root_domain: str,
        allowed_domains: Set[str],
        discovered_urls_count: int,
        duration_seconds: float,
        failure_reason: Optional[str] = None
    ):
        self.pages = pages
        self.submitted_url = submitted_url
        self.final_url = final_url
        self.root_domain = root_domain
        self.allowed_domains = allowed_domains
        self.discovered_urls_count = discovered_urls_count
        self.duration_seconds = duration_seconds
        self.failure_reason = failure_reason

class PoliteDiscoveryCrawler:
    """
    Polite, domain-scoped crawler for public corporate data discovery.
    Implements a 4-level discovery strategy:
      Level 1: Direct HTML retrieval with redirect & family domain tracking
      Level 2: Sitemap discovery (robots.txt sitemaps, /sitemap.xml, /sitemap_index.xml)
      Level 3: Internal corporate navigation discovery
      Level 4: Resilient content extraction
    """

    def __init__(
        self,
        max_pages: int = 8,
        delay_seconds: float = 0.1,
        timeout_seconds: int = 4,
        max_bytes: int = 3 * 1024 * 1024  # 3MB
    ):
        self.max_pages = max_pages
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    @staticmethod
    def normalize_url(raw_input: str) -> Tuple[str, str]:
        """
        Normalize website input into canonical URL and base domain.
        Handles bare domains (e.g. 'in.nec.com' -> 'https://in.nec.com').
        """
        raw = raw_input.strip()
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = "https://" + raw

        parsed = urlparse(raw)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower().split(":")[0]  # remove port if present
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        canonical = urlunparse((scheme, netloc, path, "", "", ""))
        # Root domain for scoping
        root_domain = netloc[4:] if netloc.startswith("www.") else netloc
        return canonical, root_domain

    def check_robots_txt(self, base_url: str) -> Tuple[Optional[RobotFileParser], List[str]]:
        """Fetch and parse robots.txt if available, returning (parser, sitemap_urls)."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rfp = RobotFileParser()
        rfp.set_url(robots_url)
        sitemaps: List[str] = []

        try:
            resp = self.session.get(robots_url, timeout=3)
            if resp.status_code == 200 and resp.text:
                lines = resp.text.splitlines()
                rfp.parse(lines)
                for line in lines:
                    if line.strip().lower().startswith("sitemap:"):
                        sm_url = line.split(":", 1)[1].strip()
                        if sm_url.startswith("http"):
                            sitemaps.append(sm_url)
                logger.info("Parsed robots.txt for %s (found %d sitemaps)", parsed.netloc, len(sitemaps))
                return rfp, sitemaps
        except Exception as e:
            logger.debug("Could not fetch robots.txt for %s: %s", parsed.netloc, e)
        return None, sitemaps

    def fetch_sitemap_urls(self, sitemap_url: str, allowed_domains: Set[str], max_urls: int = 50) -> List[str]:
        """Fetch XML sitemap and extract relevant prioritized URLs."""
        discovered: List[str] = []
        try:
            resp = self.session.get(sitemap_url, timeout=4)
            if resp.status_code == 200 and ("xml" in resp.headers.get("Content-Type", "") or "text" in resp.headers.get("Content-Type", "")):
                root = ET.fromstring(resp.content)
                namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

                for sitemap in root.findall(".//sm:sitemap/sm:loc", namespaces) or root.findall(".//sitemap/loc"):
                    if len(discovered) >= max_urls:
                        break
                    sub_sm = sitemap.text.strip() if sitemap.text else ""
                    if sub_sm and any(kw in sub_sm.lower() for kw in PRIORITY_KEYWORDS):
                        sub_urls = self.fetch_sitemap_urls(sub_sm, allowed_domains, max_urls - len(discovered))
                        discovered.extend(sub_urls)

                for url_elem in root.findall(".//sm:url/sm:loc", namespaces) or root.findall(".//url/loc"):
                    if len(discovered) >= max_urls:
                        break
                    loc = url_elem.text.strip() if url_elem.text else ""
                    if loc and self.is_in_allowed_domains(loc, allowed_domains):
                        score = self.score_url(loc)
                        if score > 0:
                            discovered.append(loc)
        except Exception as e:
            logger.debug("Error parsing sitemap %s: %s", sitemap_url, e)
        return discovered

    def is_in_allowed_domains(self, target_url: str, allowed_domains: Set[str]) -> bool:
        """Check if target_url belongs to any of the allowed family domains."""
        try:
            parsed = urlparse(target_url)
            netloc = parsed.netloc.lower().split(":")[0]
            for dom in allowed_domains:
                if netloc == dom or netloc.endswith("." + dom) or dom.endswith("." + netloc):
                    return True
        except Exception:
            pass
        return False

    def score_url(self, url: str, primary_domain: str = "") -> int:
        """Score URL relevance for corporate discovery prioritization."""
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        netloc_lower = parsed.netloc.lower()

        score = 0
        # Boost exact primary domain
        if primary_domain and primary_domain in netloc_lower:
            score += 40

        for kw in PRIORITY_KEYWORDS:
            if kw in path_lower:
                score += 15
        if path_lower in ["", "/"]:
            score += 50  # homepage is top priority
        return score

    def crawl_website(self, root_url: str) -> CrawlResult:
        """
        Execute layered polite discovery crawl up to max_pages.
        Returns CrawlResult containing pages, allowed domains, and metrics.
        """
        start_time = time.time()
        canonical_start, root_domain = self.normalize_url(root_url)
        allowed_domains: Set[str] = {root_domain}

        # Check if root_domain has a parent corporate domain (e.g. 'in.nec.com' -> also allow 'nec.com')
        domain_parts = root_domain.split(".")
        if len(domain_parts) >= 3:
            parent_domain = ".".join(domain_parts[-2:])
            allowed_domains.add(parent_domain)

        robots, declared_sitemaps = self.check_robots_txt(canonical_start)

        visited: Set[str] = set()
        queue: List[Tuple[int, str]] = []
        discovered_pages: List[DiscoveredPage] = []
        discovered_urls: Set[str] = {canonical_start}
        final_canonical_url = canonical_start
        failure_reason = None

        # LEVEL 2: Sitemaps discovery
        sitemap_candidates = declared_sitemaps + [
            f"{urlparse(canonical_start).scheme}://{urlparse(canonical_start).netloc}/sitemap.xml",
            f"{urlparse(canonical_start).scheme}://{urlparse(canonical_start).netloc}/sitemap_index.xml"
        ]

        for sm_url in sitemap_candidates[:3]:
            try:
                sm_urls = self.fetch_sitemap_urls(sm_url, allowed_domains, max_urls=30)
                for u in sm_urls:
                    if u not in discovered_urls:
                        discovered_urls.add(u)
                        queue.append((self.score_url(u, root_domain), u))
            except Exception:
                pass

        # Always ensure homepage is in queue at highest priority
        queue.append((self.score_url(canonical_start, root_domain) + 50, canonical_start))

        logger.info("Starting crawl for %s (allowed domains: %s, initial queue: %d)", root_domain, allowed_domains, len(queue))

        while queue and len(discovered_pages) < self.max_pages:
            # Sort by priority score descending
            queue.sort(key=lambda x: x[0], reverse=True)
            _, current_url = queue.pop(0)

            # Clean and normalize URL
            parsed_current = urlparse(current_url)
            clean_url = urlunparse((parsed_current.scheme, parsed_current.netloc, parsed_current.path.rstrip("/") or "/", "", "", ""))

            if clean_url in visited:
                continue
            visited.add(clean_url)

            # Check exclusions
            path_lower = parsed_current.path.lower()
            if any(path_lower.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue
            if any(ex in path_lower for ex in EXCLUDE_PATHS):
                continue

            # Respect robots.txt
            if robots and not robots.can_fetch(USER_AGENT, clean_url):
                logger.info("Skipping URL disallowed by robots.txt: %s", clean_url)
                continue

            # Domain restriction check
            if not self.is_in_allowed_domains(clean_url, allowed_domains):
                continue

            # Polite host delay
            time.sleep(self.delay_seconds)

            try:
                resp = self.session.get(
                    clean_url,
                    timeout=self.timeout_seconds,
                    allow_redirects=True
                )

                if clean_url == canonical_start:
                    final_canonical_url = resp.url
                    # Update allowed domains if redirected to official domain
                    final_domain = urlparse(resp.url).netloc.lower().split(":")[0]
                    clean_final_dom = final_domain[4:] if final_domain.startswith("www.") else final_domain
                    allowed_domains.add(clean_final_dom)

                # HTTP Access Controls / Blocking check
                if resp.status_code in [401, 403]:
                    logger.warning("Access restricted on %s (HTTP %d)", clean_url, resp.status_code)
                    if len(discovered_pages) == 0 and clean_url == canonical_start:
                        failure_reason = "ACCESS_RESTRICTED"
                    continue

                if resp.status_code != 200:
                    continue

                content_type = resp.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    continue

                content = resp.content[:self.max_bytes]
                soup = BeautifulSoup(content, "html.parser")

                # Remove non-content tags
                for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form", "iframe"]):
                    tag.decompose()

                title = soup.title.string.strip() if soup.title and soup.title.string else parsed_current.netloc

                # Extract meaningful paragraphs and section headings
                paragraphs: List[str] = []
                for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "td"]):
                    text = p.get_text(separator=" ", strip=True)
                    if len(text) > 25 and not any(junk in text.lower() for junk in ["cookie", "all rights reserved", "terms of use", "privacy policy", "javascript is disabled"]):
                        paragraphs.append(text)

                full_text = " ".join(paragraphs)
                if len(paragraphs) >= 1 or len(full_text) > 40:
                    page = DiscoveredPage(
                        url=resp.url,
                        title=title[:200],
                        text_content=full_text,
                        paragraphs=paragraphs[:35]
                    )
                    discovered_pages.append(page)

                # LEVEL 3: Extract and queue internal navigation links
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:") or href.startswith("#"):
                        continue
                    full_link = urljoin(resp.url, href)
                    parsed_link = urlparse(full_link)
                    link_clean = urlunparse((parsed_link.scheme, parsed_link.netloc, parsed_link.path.rstrip("/") or "/", "", "", ""))

                    if (
                        link_clean not in visited
                        and link_clean not in discovered_urls
                        and self.is_in_allowed_domains(link_clean, allowed_domains)
                        and not any(parsed_link.path.lower().endswith(ext) for ext in EXCLUDE_EXTENSIONS)
                    ):
                        discovered_urls.add(link_clean)
                        score = self.score_url(link_clean, root_domain)
                        if score > 0 or len(queue) < 20:
                            queue.append((score, link_clean))

            except requests.exceptions.ConnectionError:
                if len(discovered_pages) == 0:
                    failure_reason = "UNREACHABLE_HOST"
            except requests.exceptions.Timeout:
                if len(discovered_pages) == 0:
                    failure_reason = "UNREACHABLE_HOST"
            except Exception as e:
                logger.debug("Fetch error on %s: %s", clean_url, e)

        duration = round(time.time() - start_time, 2)

        if not discovered_pages and not failure_reason:
            failure_reason = "INSUFFICIENT_PUBLIC_INFORMATION"

        logger.info(
            "Crawl finished for %s: %d pages extracted, %d discovered URLs, duration %.2fs, status=%s",
            root_domain, len(discovered_pages), len(discovered_urls), duration, "SUCCESS" if discovered_pages else failure_reason
        )

        return CrawlResult(
            pages=discovered_pages,
            submitted_url=canonical_start,
            final_url=final_canonical_url,
            root_domain=root_domain,
            allowed_domains=allowed_domains,
            discovered_urls_count=len(discovered_urls),
            duration_seconds=duration,
            failure_reason=failure_reason
        )
