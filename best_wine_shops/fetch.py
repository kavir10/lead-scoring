"""
Fetch + readable-text extraction. Now a thin layer over `core/http_fetch`.

Re-exports the same surface that this package historically used, so
existing imports keep working without churn:

    from .fetch import fetch_readable, serper_search
"""
from __future__ import annotations

from core.http_fetch import (
    HEADERS,
    MAX_TEXT,
    MIN_TEXT,
    RETRYABLE,
    UA,
    fetch_readable,
    httpx_get as _httpx_get,
    playwright_session,
    readable_text_selectolax as _readable,
    serper_search,
)


__all__ = [
    "HEADERS",
    "MAX_TEXT",
    "MIN_TEXT",
    "RETRYABLE",
    "UA",
    "_httpx_get",
    "_readable",
    "fetch_readable",
    "playwright_session",
    "serper_search",
]
