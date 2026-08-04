FINRA Manual Regulatory Document Upload Directory
===================================================

This directory stores manually downloaded FINRA Rulebook PDFs or HTML files 
for automatic ingestion into Aegis AI.

FINRA's website uses Cloudflare bot protection on rulebook pages. To maintain 
100% legal compliance and reliability:

1. Visit https://www.finra.org/rules-guidance/rulebooks/finra-rules
2. Download the relevant rule or master direction as a PDF or HTML document.
3. Save or drop the downloaded file directly into this directory:
   ./data/finra_manual/
4. Aegis AI will automatically discover, parse, and ingest any files in 
   this directory during the next scheduled re-verification run, or when 
   triggered via POST /api/v1/sources/{id}/trigger.
