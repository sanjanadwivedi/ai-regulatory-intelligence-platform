import sys
import os
sys.path.insert(0, os.path.abspath("."))

import requests

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://in.nec.com/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
})

urls = [
    "https://in.nec.com/",
    "https://in.nec.com/en_IN/solutions_services/index.html",
    "https://in.nec.com/en_IN/about/index.html",
    "https://in.nec.com/en_IN/industries/manufacturing/index.html",
    "https://in.nec.com/en_IN/solutions_services/excellence-center-unit/index.html"
]

for u in urls:
    r = session.get(u, timeout=10)
    print(f"{u} -> HTTP {r.status_code} ({len(r.text)} bytes)")
