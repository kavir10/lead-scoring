"""
Shared utilities across all lead-scoring pipelines.

Modules:
    geo       - state/city tables, US filter, banned-states filter, city slicing
    schema    - canonical row schema + make_row()
    csv_io    - to_dataframe, save_source (writes per-source CSV with date stamp)
    dedupe    - name+city dedupe and phone-or-name+address dedupe
    http_fetch- HEADERS, httpx fetch with retries, Playwright session + fallback,
                serper_search, readable-text extraction
    apify     - thin ApifyClient wrapper (run actor + fetch dataset)
    llm       - anthropic_client() with empty-API-key-shell guard
    keywords  - CHAIN_KEYWORDS, LIQUOR_KEYWORDS, CLUB_KEYWORDS

ROOT points at the repo root and is safe to import anywhere.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
