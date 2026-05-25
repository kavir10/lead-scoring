"""
TLS-fingerprint-spoofing HTTP fetch helper.

Many specialty food retailers (D'Artagnan, Forever Cheese, Murray's,
Williams-Sonoma, Goldbelly) sit behind Cloudflare or Akamai protections
that block plain `requests` on TLS-fingerprint signals. Playwright works
but is slow and resource-heavy.

`curl_cffi` impersonates the TLS handshake + cipher suite ordering of a
real Chrome 120 build, bypassing the bulk of these challenges with a
drop-in `requests`-shaped API.

Use this whenever a target sits behind WAF: prefer it over `requests` in
new code. Fall back to Playwright only when the target requires
JS-rendering (e.g., Goldbelly's Next.js merchants grid).
"""
from __future__ import annotations

from curl_cffi import requests as _cffi_requests


_DEFAULT_IMPERSONATE = "chrome120"


def fetch_html_cffi(
    url: str,
    *,
    impersonate: str = _DEFAULT_IMPERSONATE,
    timeout: int = 30,
    allow_redirects: bool = True,
    accept_status_codes: tuple[int, ...] = (200, 301, 302, 404),
) -> str:
    """
    Fetch a URL with browser TLS impersonation.

    Returns the response body as text. WAF endpoints often return 404 or
    other "error" status codes while still serving the real page body —
    we keep the body whenever it's substantive (>1500 chars).

    Returns empty string on hard failure.
    """
    try:
        r = _cffi_requests.get(
            url,
            impersonate=impersonate,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )
    except Exception as e:
        print(f"  [browser_fetch] error fetching {url}: {e}", flush=True)
        return ""
    body = r.text or ""
    if r.status_code in accept_status_codes or len(body) > 1500:
        return body
    print(f"  [browser_fetch] {r.status_code} ({len(body)} bytes) on {url}", flush=True)
    return ""


def fetch_html_with_fallback(url: str) -> str:
    """
    Try curl_cffi first, fall back to plain requests, then Playwright.

    Use this as the standard fetch path for any source that might be
    behind a WAF. The cost ladder is:
      curl_cffi  ~0.5s, free
      requests   ~0.5s, free (probably already failed if we're here)
      playwright ~5s, ~50MB memory
    """
    html = fetch_html_cffi(url)
    if html:
        return html
    # Fall back to awards._lib.fetch_html (plain requests with retries)
    from awards._lib import fetch_html
    html = fetch_html(url)
    if html and "<body" in html.lower():
        return html
    # Last resort: Playwright (defer import to avoid loading at module import)
    from awards._lib import playwright_session
    try:
        with playwright_session() as (page, _ctx, _br):
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=12_000)
            except Exception:
                pass
            return page.content() or ""
    except Exception as e:
        print(f"  [browser_fetch] playwright fallback failed for {url}: {e}", flush=True)
        return ""
