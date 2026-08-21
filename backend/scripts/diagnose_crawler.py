import sys
import os
sys.path.insert(0, os.path.abspath("."))

import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from app.services.discovery_crawler import PoliteDiscoveryCrawler

def diagnose_url(test_url):
    print(f"\n{'='*70}\nDIAGNOSING: {test_url}\n{'='*70}")
    crawler = PoliteDiscoveryCrawler(max_pages=5)
    canonical_start, root_domain = crawler.normalize_url(test_url)
    
    print(f"Submitted URL: {test_url}")
    print(f"Canonical Start: {canonical_start}")
    print(f"Root Domain: {root_domain}")
    
    # 1. Robots.txt
    robots = crawler.check_robots_txt(canonical_start)
    print(f"Robots.txt parsed: {'YES' if robots else 'NO'}")
    
    # 2. Homepage request
    headers = crawler.session.headers
    try:
        resp = crawler.session.get(canonical_start, timeout=10, allow_redirects=True)
        print(f"HTTP status: {resp.status_code}")
        print(f"Final URL: {resp.url}")
        print(f"Content type: {resp.headers.get('Content-Type')}")
        print(f"Response length: {len(resp.text)} bytes")
        
        # Check domain mismatch
        final_domain = urlparse(resp.url).netloc
        print(f"Final domain: {final_domain}")
        print(f"Same domain check: {crawler.is_same_domain(resp.url, root_domain)}")
        
        # Check soup
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.title.string.strip() if soup.title and soup.title.string else 'No title'
        print(f"Page Title: {title}")
        
        # Check links
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        print(f"Total links on homepage: {len(links)}")
        valid_domain_links = []
        for l in links:
            full = urljoin(resp.url, l)
            if crawler.is_same_domain(full, root_domain):
                valid_domain_links.append(full)
        print(f"Valid same-domain links: {len(valid_domain_links)}")
        if valid_domain_links:
            print("Sample links:", valid_domain_links[:5])
            
        # Check paragraphs
        paras = []
        for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'li']):
            t = p.get_text(strip=True)
            if len(t) > 25:
                paras.append(t)
        print(f"Readable paragraphs (>25 chars): {len(paras)}")
        if paras:
            print("Sample paragraph:", paras[0][:150])
            
    except Exception as e:
        print(f"Request failed: {e}")

    # 3. Crawler run
    print("\n--- Running crawler.crawl_website ---")
    pages = crawler.crawl_website(canonical_start)
    print(f"Pages successfully extracted: {len(pages)}")
    for p in pages:
        print(f" - Page URL: {p.url} | Title: {p.title} | Paragraphs: {len(p.paragraphs)}")

if __name__ == '__main__':
    diagnose_url("https://in.nec.com")
    diagnose_url("https://www.nec.com")
