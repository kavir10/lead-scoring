"""
Verify whole-animal butcher shops from their own websites.

Input: any CSV with Name/Website/City/State columns (case-insensitive).
For each shop, crawls the homepage plus up to 5 internal pages (about, story,
meat, butcher, visit, hours, contact...) and records:

  - whole_animal: True when the site itself says "whole animal",
    "nose to tail", or describes breaking down whole animals in-house.
    Keeps the matched snippet and the page URL as evidence.
  - storefront: "yes" when a page shows posted retail hours (day + time) or
    visit-the-shop language; "no" when the site says online-only / no
    storefront / markets-only; otherwise "unclear".

States in BANNED_STATES are dropped before crawling.

    python scripts/verify_whole_animal.py IN.csv OUT.csv [--concurrency 24] [--browser]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import sys
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from selectolax.parser import HTMLParser

BANNED_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

WHOLE_ANIMAL_PATTERNS = [
    ("whole animal", re.compile(r"\bwhole[\s\-]+animals?\b", re.I)),
    ("nose to tail", re.compile(r"\bnose[\s\-]+to[\s\-]+tail\b", re.I)),
    ("breaks down whole", re.compile(
        r"\b(?:break(?:s|ing)?|broke|butcher(?:s|ing)?|process(?:es|ing)?|cut(?:s|ting)?)\s+"
        r"(?:down\s+)?(?:whole|entire)\s+"
        r"(?:hogs?|pigs?|cows?|steers?|lambs?|goats?|beef|carcass(?:es)?|sides?)\b", re.I)),
]

# Grading. "strong" = the shop describes its own craft; "processing" = custom
# slaughter/processing of the customer's animal; "bulk" = selling whole/half/
# quarter animals; "weak" = incidental mention (merch, blog, dry-aging explainer).
WA = r"whole[\s\-]+animals?"
STRONG_RES = [
    re.compile(rf"{WA}\s+(?:butcher(?:y|s|ing)?|butcher shop|meat (?:market|shop)|shop|approach|philosophy|program|"
               r"utilization|practices?)\b", re.I),
    re.compile(rf"\b(?:source[sd]?|sourcing|buy(?:s|ing)?|bring(?:s|ing)? in|purchas(?:e|es|ing)|work(?:s|ing)? with|"
               rf"break(?:s|ing)? down|broken down|use[sd]?|using|utiliz(?:e|es|ing))\b[^.\n]{{0,45}}{WA}", re.I),
    re.compile(rf"{WA}\b[^.\n]{{0,40}}\b(?:broken down|break down|in[\s\-]house|hand[\s\-]cut)", re.I),
    re.compile(r"nose[\s\-]+to[\s\-]+tail\s+(?:butcher(?:y|s|ing)?|philosophy|operation|approach|shop|program)\b", re.I),
    re.compile(r"\bbreak(?:s|ing)?\s+down\s+whole\s+(?:hogs?|pigs?|lambs?|steers?|sides?|carcass)", re.I),
    re.compile(rf"\b(?:make|made|cut)\b[^.\n]{{0,40}}\bfrom\s+(?:the\s+same\s+)?{WA}", re.I),
    re.compile(rf"{WA}\s*(?:&|and)\s+\w+\s+butcher(?:y|s|ing)?\b", re.I),
]
PROCESSING_RE = re.compile(
    r"custom (?:processing|slaughter|exempt)|process(?:ing)? your|(?:whole[\s\-]+animal|carcass)\s+(?:processing|slaughter)|"
    r"slaughter(?:ing)?\b|deer processing|(?:wild )?game processing|hunter services", re.I)
BULK_RE = re.compile(
    rf"{WA}\s+(?:shares?|purchas(?:e|es|ing)|orders?|sales?|packages?|section)|buy(?:ing)?\s+(?:a\s+|the\s+)?{WA}|"
    rf"(?:half|halves)\s+(?:or|and)\s+(?:a\s+)?whole|whole,?\s+(?:or\s+)?half|quarter,?\s+half|"
    rf"cheaper than purchasing|can.t handle a {WA}|bulk (?:shares?|beef|pork|orders?)|freezer (?:beef|pork|orders?)",
    re.I)
WEAK_RE = re.compile(r"hoodie|t-?shirt|\btee\b|merch|hanging the whole animal|on the whole animal", re.I)


def _grade(snippets: list[tuple[str, str]]) -> tuple[str, tuple[str, str]]:
    for snip, url in snippets:
        if WEAK_RE.search(snip):
            continue
        if any(rx.search(snip) for rx in STRONG_RES) and not BULK_RE.search(snip) and not PROCESSING_RE.search(snip):
            return "strong", (snip, url)
    for label, rx in (("processing", PROCESSING_RE), ("bulk", BULK_RE)):
        for snip, url in snippets:
            if rx.search(snip):
                return label, (snip, url)
    return "weak", snippets[0]


DAY = r"(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\.?"
TIME = r"\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)"
RANGE = r"\d{1,2}(?::\d{2})?\s*(?:-|–|—|to)\s*\d{1,2}(?::\d{2})?"
HOURS_RE = re.compile(rf"\b{DAY}\b[^\n]{{0,40}}?(?:{TIME}|{RANGE})", re.I)
VISIT_RE = re.compile(
    r"\b(?:store hours|shop hours|retail hours|hours of operation|visit (?:us|the shop|our shop|our store)|"
    r"come (?:visit|see us)|our (?:retail )?(?:shop|storefront|butcher shop) (?:is )?(?:located|open)|"
    r"open now|closes at \d|location (?:&|and) hours|hours (?:&|and) location|visit our (?:shop|store|butcher shop)s?)\b", re.I)
ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+(?:[NSEW]\.?\s+)?[A-Z0-9][\w.']*(?:\s+[A-Z0-9][\w.']*){0,4}\s+"
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Hwy|Highway|Way|Pl|Place|Ln|Lane|Pike|Pkwy|Ct|Sq|Square|Row)\b"
    r"[.,]?[^\n]{0,60}?\b[A-Z]{2}\s+\d{5}\b")
NO_STORE_RE = re.compile(
    r"\b(?:online only|no (?:retail )?storefront|we do not have a (?:retail )?(?:store|storefront|shop)|"
    r"not open to the public|by appointment only|delivery only|pick[\s\-]?up only)\b", re.I)

PAGE_HINT_RE = re.compile(
    r"about|story|who-we-are|our-|philosoph|meat|butcher|sourc|farm|visit|hours|location|find-us|contact|shop-info",
    re.I)
IG_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})/?(?:[?#\"']|$)", re.I)
IG_SKIP = {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "share", "sharer"}
SKIP_HREF_RE = re.compile(r"\.(?:pdf|jpg|jpeg|png|gif|webp|mp4|zip)$|/cart|/account|/checkout|mailto:|tel:", re.I)

MAX_EXTRA_PAGES = 8


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: c.strip().lower() for c in df.columns})


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url or url.lower() in {"nan", "none"}:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _text(html: str) -> tuple[str, HTMLParser]:
    tree = HTMLParser(html)
    for tag in ("script", "style", "noscript", "svg"):
        for node in tree.css(tag):
            node.decompose()
    body = tree.body
    text = body.text(separator="\n") if body else tree.text(separator="\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text, tree


def _snippet(text: str, m: re.Match, pad: int = 110) -> str:
    s = max(0, m.start() - pad)
    e = min(len(text), m.end() + pad)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def _candidate_links(tree: HTMLParser, base: str) -> list[str]:
    host = urlparse(base).netloc.lower().removeprefix("www.")
    seen, out = set(), []
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith("#") or SKIP_HREF_RE.search(href):
            continue
        try:
            url = urljoin(base, href).split("#")[0].rstrip("/")
            p = urlparse(url)
        except ValueError:
            continue
        if p.scheme not in ("http", "https") or p.netloc.lower().removeprefix("www.") != host:
            continue
        label = f"{p.path} {a.text(strip=True)}"
        if not PAGE_HINT_RE.search(label) or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out[:MAX_EXTRA_PAGES]


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    try:
        r = await client.get(url)
        ctype = r.headers.get("content-type", "")
        if r.status_code >= 400 or "html" not in ctype:
            return str(r.url), ""
        return str(r.url), r.text
    except Exception:
        return url, ""


class BrowserClient:
    """Playwright-backed stand-in for httpx.AsyncClient.get, for sites that block plain HTTP."""

    def __init__(self, context):
        self.context = context

    async def get(self, url: str):
        page = await self.context.new_page()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(1500)
            status = resp.status if resp else 0
            return _BrowserResponse(page.url, status, await page.content())
        finally:
            await page.close()


class _BrowserResponse:
    def __init__(self, url: str, status: int, text: str):
        self.url, self.status_code, self.text = url, status, text
        self.headers = {"content-type": "text/html"}


async def verify_one(client, sem: asyncio.Semaphore, website: str) -> dict:
    result = {
        "site_status": "no_website",
        "whole_animal": False,
        "wa_terms": "",
        "wa_evidence": "",
        "wa_evidence_url": "",
        "wa_strength": "",
        "storefront": "unclear",
        "storefront_evidence": "",
        "pages_checked": 0,
        "links_table22": False,
        "instagram": "",
    }
    url = _normalize_url(website)
    if not url:
        return result
    async with sem:
        final, html = await _fetch(client, url)
        if not html and url.startswith("https://"):
            final, html = await _fetch(client, "http://" + url[len("https://"):])
        if not html:
            result["site_status"] = "unreachable"
            return result
        result["site_status"] = "ok"
        raw = [html]
        text, tree = _text(html)
        pages = [(final, text)]
        extra = _candidate_links(tree, final)
        fetched = await asyncio.gather(*(_fetch(client, u) for u in extra))
        for u, h in fetched:
            if h:
                raw.append(h)
                pages.append((u, _text(h)[0]))
        result["links_table22"] = any("table22.com" in h.lower() for h in raw)
        for h in raw:
            handles = [m.group(1).lower().strip(".") for m in IG_RE.finditer(h)]
            handles = [x for x in handles if x not in IG_SKIP]
            if handles:
                result["instagram"] = handles[0]
                break
    result["pages_checked"] = len(pages)

    terms, snippets = [], []
    for page_url, text in pages:
        for label, rx in WHOLE_ANIMAL_PATTERNS:
            for m in rx.finditer(text):
                if label not in terms:
                    terms.append(label)
                if len(snippets) < 12:
                    snippets.append((_snippet(text, m), page_url))
    result["whole_animal"] = bool(terms)
    result["wa_terms"] = "; ".join(terms)
    result["wa_strength"] = ""
    if snippets:
        strength, (snip, url) = _grade(snippets)
        result["wa_strength"] = strength
        result["wa_evidence"], result["wa_evidence_url"] = snip, url

    no_store = None
    for page_url, text in pages:
        m = HOURS_RE.search(text) or VISIT_RE.search(text)
        if m:
            result["storefront"] = "yes"
            result["storefront_evidence"] = f"{_snippet(text, m, 60)} [{page_url}]"
            break
        n = NO_STORE_RE.search(text)
        if n and no_store is None:
            no_store = f"{_snippet(text, n, 60)} [{page_url}]"
    if result["storefront"] != "yes" and no_store:
        result["storefront"] = "no"
        result["storefront_evidence"] = no_store
    if result["storefront"] == "unclear":
        for page_url, text in pages:
            m = ADDRESS_RE.search(text)
            if m:
                result["storefront"] = "address_only"
                result["storefront_evidence"] = f"{_snippet(text, m, 30)} [{page_url}]"
                break
    return result


SITE_TIMEOUT = {"http": 90, "browser": 150}  # seconds per site, all pages included
_CACHE: dict[str, dict] = {}
RETRYABLE = {"unreachable", "error"}
_NO_LIMIT = asyncio.Semaphore(10**9)  # verify_one's own gate, when the caller already holds a slot
CANARY_HOSTS = ("google.com", "cloudflare.com")


def _network_up() -> bool:
    for host in CANARY_HOSTS:
        try:
            socket.gethostbyname(host)
            return True
        except OSError:
            continue
    return False


async def _wait_for_network() -> None:
    """Block while DNS is down (laptop sleep, wifi drop); returns once it's back."""
    waited = 0
    while not await asyncio.to_thread(_network_up):
        if waited % 60 == 0:
            print(f"  network down, waiting ({waited}s)", file=sys.stderr, flush=True)
        await asyncio.sleep(10)
        waited += 10
_CACHE_PATH = ""


def _load_cache(path: str) -> None:
    """Per-site results as JSONL, appended as each site finishes, so a crash or hang loses nothing."""
    global _CACHE_PATH
    _CACHE_PATH = path
    if path and os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    # Failures are retried on rerun: a network drop must not become a verdict.
                    if rec["result"].get("site_status") not in RETRYABLE:
                        _CACHE[rec["key"]] = rec["result"]
                except (ValueError, KeyError):
                    continue
        print(f"cache: {len(_CACHE)} site results loaded from {path}", file=sys.stderr)


def _save(key: str, result: dict) -> None:
    _CACHE[key] = result
    if _CACHE_PATH:
        with open(_CACHE_PATH, "a") as fh:
            fh.write(json.dumps({"key": key, "result": result}, default=str) + "\n")


async def _verify_all(client, df: pd.DataFrame, concurrency: int, mode: str = "http") -> pd.DataFrame:
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def wrapped(w: str) -> dict:
        nonlocal done
        key = f"{mode}|{_normalize_url(w)}"
        if key in _CACHE:
            r = _CACHE[key]
        else:
            for attempt in range(3):
                try:
                    # A dead browser or a JS redirect loop can leave a page awaiting forever.
                    # Take the slot first: the timeout must cover fetching, not queueing.
                    async with sem:
                        r = await asyncio.wait_for(verify_one(client, _NO_LIMIT, w), timeout=SITE_TIMEOUT[mode])
                except asyncio.TimeoutError:
                    r = {"site_status": "unreachable", "wa_evidence": f"timeout after {SITE_TIMEOUT[mode]}s"}
                except Exception as e:  # one bad site must not sink the batch
                    r = {"site_status": "error", "wa_evidence": f"{type(e).__name__}: {e}"[:200]}
                if r.get("site_status") not in RETRYABLE or await asyncio.to_thread(_network_up):
                    break
                await _wait_for_network()  # the failure was ours, not the site's: retry
            _save(key, r)
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(df)}", file=sys.stderr, flush=True)
        return r

    results = await asyncio.gather(*(wrapped(w) for w in df["website"].fillna("")))
    out = pd.DataFrame(results, index=df.index)
    defaults = {"whole_animal": False, "links_table22": False, "storefront": "unclear", "pages_checked": 0}
    for col, val in defaults.items():
        out[col] = out[col].fillna(val) if col in out else val
    out["whole_animal"] = out["whole_animal"].astype(bool)
    return out


async def run_ordered(df: pd.DataFrame, concurrency: int, browser: bool = False) -> pd.DataFrame:
    if browser:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            b = await pw.chromium.launch()
            context = await b.new_context(user_agent=HEADERS["User-Agent"], ignore_https_errors=True)
            try:
                return await _verify_all(BrowserClient(context), df, concurrency, mode="browser")
            finally:
                await b.close()

    limits = httpx.Limits(max_connections=concurrency * 4)
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=15.0, follow_redirects=True, limits=limits, verify=False
    ) as client:
        return await _verify_all(client, df, concurrency)


def _resolves(website: str) -> bool:
    host = urlparse(_normalize_url(website)).netloc
    if not host:
        return False
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--browser", action="store_true", help="fetch everything with headless Chromium")
    ap.add_argument("--no-retry", action="store_true", help="skip the automatic Chromium retry pass")
    ap.add_argument("--cache", default="", help="JSONL of per-site results; default OUTPUT.cache.jsonl")
    args = ap.parse_args()

    df = _norm_cols(pd.read_csv(args.input, dtype=str))
    df["state"] = df["state"].fillna("").str.strip().str.upper()
    before = len(df)
    df = df[~df["state"].isin(BANNED_STATES)].copy()
    print(f"{before} rows, {before - len(df)} dropped for excluded states, verifying {len(df)}", file=sys.stderr)

    _load_cache(args.cache or args.output.rsplit(".", 1)[0] + ".cache.jsonl")
    checks = asyncio.run(run_ordered(df, args.concurrency, args.browser))
    if not args.browser and not args.no_retry:
        retry = checks.index[
            (checks.site_status == "unreachable")
            | (checks.whole_animal & checks.storefront.isin(["unclear", "address_only"]))
        ]
        if len(retry):
            print(f"retrying {len(retry)} rows in headless Chromium", file=sys.stderr)
            again = asyncio.run(run_ordered(df.loc[retry], max(1, args.concurrency // 4), browser=True))
            better = again.index[(again.site_status == "ok") & ~(
                checks.loc[again.index, "whole_animal"] & ~again.whole_animal)]
            checks.loc[better] = again.loc[better]
    asyncio.run(_wait_for_network())  # DNS verdicts below are meaningless while offline
    checks["site_status"] = checks["site_status"].where(
        checks.site_status != "unreachable",
        [("dead_domain" if not _resolves(w) else "unreachable") for w in df.loc[checks.index, "website"].fillna("")])
    out = pd.concat([df, checks], axis=1)
    out.to_csv(args.output, index=False)

    print(out.site_status.value_counts().to_string(), file=sys.stderr)
    print(f"whole_animal: {out.whole_animal.sum()}", file=sys.stderr)
    print(out[out.whole_animal].storefront.value_counts().to_string(), file=sys.stderr)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
