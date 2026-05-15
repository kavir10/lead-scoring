"""
Self-contained "best wine shops" lead discovery.

Pulls from a curated set of editorial "best wine shops in America" articles
(Chowhound, VinePair, Sokolin, USA Wine Ratings, Food & Wine, USA Today 10Best,
Imbibe) plus ~70 Serper-discovered articles matching the same theme.

Stack: httpx + selectolax for fetching/parsing, Playwright fallback when
blocked, Claude for LLM extraction.

Entrypoint:
    python -m best_wine_shops.discover [--no-seeds] [--no-search]
                                       [--max-per-query N] [--dry-run]
"""
