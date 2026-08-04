"""
Intelligent HTML Content Extractor for Government Regulation Pages
===================================================================
Strips navigation menus, headers, footers, sidebars, disclaimers, and chrome
from government portals (RBI, SEBI, CERT-In, PIB, SEC, HHS/eCFR) to extract
the clean, authentic regulatory document body text.

Preserves:
  - Paragraph & section structure
  - Document headings, circular numbers, dates, statutory references
  - Verbatim clause text

Removes:
  - Header/footer navigation, breadcrumbs, search bars, social sharing widgets
  - Site disclaimers, copyright lines, browser optimization notices
"""

import re
import logging
from html import unescape
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger("compliance_platform.content_extractor")


class RegulationContentExtractor:
    """
    Intelligent HTML content extractor for authority regulation pages.
    """

    # Authority-specific content selectors (ordered by priority)
    CONTENT_SELECTORS: Dict[str, List[str]] = {
        "RBI": [
            ".notification-content",
            "#content",
            "table[width='95%']",
            "div[align='justify']",
            "table#dgvData",
            ".tblContainer",
            "td.tableheader",
            "main",
        ],
        "SEBI": [
            "#content",
            ".sebi-content",
            ".circular-detail",
            "article",
            "main",
        ],
        "CERT-In": [
            ".advisory-body",
            "#advisory",
            ".content-area",
            "main",
        ],
        "PIB": [
            ".pib-content",
            "#content",
            ".release-content",
            "main",
        ],
        "HHS": [
            ".content-container",
            "#main-content",
            "main",
            "article",
        ],
        "SEC": [
            "#main-content",
            ".article-content",
            "main",
            "article",
        ],
        "DEFAULT": [
            "article",
            "main",
            "#content",
            ".content",
            ".main-content",
            "#main-content",
            "body",
        ]
    }

    # Patterns to remove (classes, ids, tags, text)
    CHROME_PATTERNS = {
        "classes": [
            "navbar", "navigation", "sidebar", "footer", "header",
            "breadcrumb", "social", "share", "widget", "advertisement",
            "menu", "pagination", "related", "comment", "cookie",
            "banner", "top-bar", "topbar", "site-footer", "site-header"
        ],
        "ids": [
            "navigation", "nav", "sidebar", "footer", "header",
            "breadcrumb", "social", "share-buttons", "cookie-consent"
        ],
        "tags": ["nav", "script", "style", "iframe", "noscript", "header", "footer"],
        "text_patterns": [
            r"Last Updated On:",
            r"Back to previous page",
            r"Top$",
            r"Disclaimer:",
            r"Copyright",
            r"All rights reserved",
            r"This site is optimized for",
            r"Best viewed in",
            r"Page last modified",
        ]
    }

    @staticmethod
    def extract_clean_text(html: str, authority: str = "RBI") -> str:
        """
        Extracts clean regulation text from government page HTML by eliminating chrome.

        Args:
            html: Raw HTML string from source URL
            authority: Authority name (RBI, SEBI, CERT-In, PIB, HHS, SEC, etc.)

        Returns:
            Clean regulation text with chrome removed.
        """
        if not html or not html.strip():
            return ""

        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as exc:
            logger.warning("BeautifulSoup parsing failed: %s — using crude regex strip", exc)
            return RegulationContentExtractor.normalize_text(re.sub(r"<[^>]+>", " ", html))

        # Step 1: Remove HTML comments
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Step 2: Remove known chrome tags
        for tag_name in RegulationContentExtractor.CHROME_PATTERNS["tags"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Step 3: Remove chrome elements by class or ID
        for cls_pattern in RegulationContentExtractor.CHROME_PATTERNS["classes"]:
            for elem in soup.find_all(class_=lambda x: x and cls_pattern in str(x).lower()):
                elem.decompose()

        for id_pattern in RegulationContentExtractor.CHROME_PATTERNS["ids"]:
            for elem in soup.find_all(id=lambda x: x and id_pattern in str(x).lower()):
                elem.decompose()

        # Step 4: Extract main content block using authority selectors
        content_elem = None
        auth_upper = authority.upper() if authority else "DEFAULT"
        selectors = RegulationContentExtractor.CONTENT_SELECTORS.get(
            auth_upper,
            RegulationContentExtractor.CONTENT_SELECTORS["DEFAULT"]
        )

        for selector in selectors:
            try:
                if selector.startswith("."):
                    elem = soup.find(class_=selector[1:])
                elif selector.startswith("#"):
                    elem = soup.find(id=selector[1:])
                else:
                    elem = soup.select_one(selector)

                if elem and len(elem.get_text(strip=True)) > 200:
                    content_elem = elem
                    break
            except Exception:
                continue

        # Fallback to body or entire soup if selector failed
        if not content_elem or len(content_elem.get_text(strip=True)) < 200:
            content_elem = soup.body or soup

        # Step 5: Remove any remaining internal chrome inside content block
        for cls_pattern in RegulationContentExtractor.CHROME_PATTERNS["classes"]:
            for elem in content_elem.find_all(class_=lambda x: x and cls_pattern in str(x).lower()):
                elem.decompose()

        # Step 6: Extract text preserving line breaks between block elements
        text = content_elem.get_text(separator="\n", strip=True)

        # Step 7: Normalize whitespace and filter out chrome lines
        return RegulationContentExtractor.normalize_text(text)

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalizes extracted text: decodes entities, collapses whitespace, preserves structure.
        """
        if not text:
            return ""

        # Decode HTML entities (&nbsp; -> space, &amp; -> &, etc.)
        text = unescape(text)

        # Remove multiple consecutive blank lines (keep max 2 for paragraph separation)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Collapse multiple horizontal spaces/tabs to single space
        text = re.sub(r"[ \t]{2,}", " ", text)

        # Remove trailing whitespace on each line
        lines = [line.rstrip() for line in text.split("\n")]

        # Filter out lines matching chrome text patterns
        filtered_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                filtered_lines.append("")
                continue

            skip = False
            for pattern in RegulationContentExtractor.CHROME_PATTERNS["text_patterns"]:
                if re.search(pattern, stripped, re.IGNORECASE):
                    skip = True
                    break

            if not skip:
                filtered_lines.append(line)

        # Rejoin lines and collapse any resulting 3+ newlines
        clean_text = "\n".join(filtered_lines)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
        return clean_text.strip()


import os
import glob
import time
import random
import xml.etree.ElementTree as ET
from app.core.config import settings


class FINRAOfficialAdapter:
    """
    Fetches FINRA regulatory content through official, legitimate channels only.
    No WAF bypass, no User-Agent spoofing, no Cloudflare evasion.
    
    Three strategies, tried in order:
    1. FINRA RSS/Atom feed (notices and regulatory updates)
    2. FINRA public Data API (no key required for public datasets)  
    3. Manual upload fallback (drop a PDF/HTML into ./data/finra_manual/)
    """
    
    FINRA_RSS_URL = "https://www.finra.org/rules-guidance/notices/rss"
    FINRA_DATA_API = "https://api.finra.org"
    
    @staticmethod
    def fetch_regulatory_notices(rss_url: str = FINRA_RSS_URL) -> Dict[str, Any]:
        """Fetch FINRA regulatory notices via official RSS feed."""
        try:
            import urllib.request
            headers = {"User-Agent": "AegisAI-CompliancePlatform/1.0"}
            req = urllib.request.Request(rss_url or FINRAOfficialAdapter.FINRA_RSS_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_data = resp.read()
                
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")
            notices = []
            full_text_snippets = []

            for item in items[:15]:
                title = (item.findtext("title") or "FINRA Regulatory Notice").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                description = (item.findtext("description") or "").strip()
                
                notices.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "description": description
                })
                full_text_snippets.append(f"FINRA Regulatory Notice: {title}\nPublished: {pub_date}\nLink: {link}\nSummary: {description}")
            
            combined_text = "\n\n---\n\n".join(full_text_snippets)
            return {
                "status": "SUCCESS",
                "strategy": "FINRA_OFFICIAL_RSS",
                "count": len(notices),
                "notices": notices,
                "content_text": combined_text,
                "ocr_confidence": 1.0
            }
        except Exception as e:
            logger.warning("FINRA Official RSS feed fetch failed: %s", e)
            return {
                "status": "FAILED",
                "strategy": "FINRA_OFFICIAL_RSS",
                "error": str(e)
            }
    
    @staticmethod  
    def fetch_via_data_api(dataset: str = "regsho") -> Dict[str, Any]:
        """Fetch from FINRA public Data API — no credentials required."""
        try:
            import urllib.request
            import json
            url = f"{FINRAOfficialAdapter.FINRA_DATA_API}/data/group/otcMarket/name/{dataset}"
            headers = {
                "User-Agent": "AegisAI-CompliancePlatform/1.0",
                "Accept": "application/json"
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
            return {
                "status": "SUCCESS",
                "strategy": "FINRA_PUBLIC_DATA_API",
                "dataset": dataset,
                "data": data,
                "content_text": json.dumps(data, indent=2),
                "ocr_confidence": 1.0
            }
        except Exception as e:
            logger.warning("FINRA Public Data API fetch failed: %s", e)
            return {
                "status": "FAILED",
                "strategy": "FINRA_PUBLIC_DATA_API",
                "error": str(e)
            }
    
    @staticmethod
    def load_manual_upload(upload_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Fallback: load any PDF/HTML files dropped into ./data/finra_manual/.
        Documented Manual Process:
        1. Download from https://www.finra.org/rules-guidance/rulebooks/finra-rules
        2. Drop file into ./data/finra_manual/
        3. This method processes them automatically on next scheduler run
        """
        target_dir = upload_dir or getattr(settings, "FINRA_MANUAL_UPLOAD_PATH", "./data/finra_manual")
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        pdf_files = glob.glob(os.path.join(target_dir, "*.pdf"))
        html_files = glob.glob(os.path.join(target_dir, "*.html")) + glob.glob(os.path.join(target_dir, "*.htm"))
        txt_files = glob.glob(os.path.join(target_dir, "*.txt"))
        
        extracted_texts = []
        processed_files = []
        
        for pdf_path in pdf_files:
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                pdf_text = "\n".join([page.extract_text() or "" for page in reader.pages])
                if pdf_text.strip():
                    extracted_texts.append(f"=== MANUAL UPLOAD PDF: {os.path.basename(pdf_path)} ===\n" + pdf_text)
                    processed_files.append(os.path.basename(pdf_path))
            except Exception as err:
                logger.warning("Error parsing manual PDF %s: %s", pdf_path, err)
                
        for doc_path in html_files + txt_files:
            if doc_path.endswith("README.txt"):
                continue
            try:
                with open(doc_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    if content.strip():
                        extracted_texts.append(f"=== MANUAL UPLOAD DOC: {os.path.basename(doc_path)} ===\n" + content)
                        processed_files.append(os.path.basename(doc_path))
            except Exception as err:
                logger.warning("Error reading manual doc %s: %s", doc_path, err)

        if extracted_texts:
            combined_text = "\n\n========================================\n\n".join(extracted_texts)
            return {
                "status": "SUCCESS",
                "strategy": "FINRA_MANUAL_UPLOAD",
                "processed_files": processed_files,
                "content_text": combined_text,
                "ocr_confidence": 0.98
            }
            
        return {
            "status": "EMPTY",
            "strategy": "FINRA_MANUAL_UPLOAD",
            "message": "No manual FINRA rulebook files found in ./data/finra_manual/. Drop PDF or HTML files there for ingestion.",
            "content_text": ""
        }



