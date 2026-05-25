"""
Waterfall recovery for merchants flagged Tock/Resy in April but missed in
the May fresh scrape. Each merchant flows through tiers and exits on the
first Tock or Resy hit:

  Tier 1: httpx with hardened Chrome-like headers, 20s timeout, 1 retry
  Tier 2: curl-cffi with Chrome TLS impersonation (bypasses Cloudflare JA3)
  Tier 3: Playwright headless Chromium (renders JS, captures embed slugs)
  Tier 4: Serper site:exploretock.com / site:resy.com lookups on name+city

Usage:
    python scripts/recover_lost_resy_tock.py --limit 20    # smoke test
    python scripts/recover_lost_resy_tock.py               # full run
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
import pandas as pd
from selectolax.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SERPER_API_KEY  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(ROOT, "output/resy_tock_merchants/inputs/lost_to_recover.csv")
PROGRESS_PATH = os.path.join(ROOT, "output/resy_tock_merchants/raw/recovery_progress.csv")

CHROME_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="123", "Not?A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

TOCK_RE = re.compile(r"exploretock\.com/([^/?#\s\"'<>]+)", re.I)
RESY_RE = re.compile(
    r"resy\.com/(?:cities/[^/]+/(?:venues/)?([^/?#\s\"'<>]+)|venues/([^/?#\s\"'<>]+))",
    re.I,
)
RESY_WIDGET_RE = re.compile(
    r"widgets\.resy\.com/[^\"'\s<>]*?(?:venueId=|/venue/)([^&\"'\s<>]+)", re.I
)
_ASSET_EXTS = (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".gif", ".woff", ".woff2", ".html", ".json")
_GENERIC_SLUGS = {
    "list", "search", "results", "top-rated", "events", "signup", "login",
    "cities", "city", "about", "support", "help", "blog", "contact",
    "experience", "venues", "venue", "checkout", "account", "home",
}

OUT_COLS = [
    "cid", "name", "website", "business_type", "city", "state",
    "april_reservation_url",
    "recovered_via",      # tier1_httpx | tier2_curlcffi | tier3_playwright | tier4_serper | none
    "tock_url", "tock_slug", "tock_embed_only",
    "resy_url", "resy_slug", "resy_embed_only",
    "tier_attempts",       # comma-joined tier names attempted
    "last_status",
    "scraped_at",
]


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_platform_links(html: str, base_url: str) -> dict:
    out = {"tock_url": "", "resy_url": "", "opentable_url": ""}
    if not html:
        return out
    try:
        tree = HTMLParser(html)
    except Exception:
        return out

    candidates = []
    for tag in tree.css("a[href]"):
        candidates.append(tag.attributes.get("href", ""))
    for tag in tree.css("iframe[src]"):
        candidates.append(tag.attributes.get("src", ""))
    for tag in tree.css("link[href]"):
        candidates.append(tag.attributes.get("href", ""))
    for m in re.finditer(r"https?://[^\s\"'<>)]+", html):
        candidates.append(m.group(0))

    for href in candidates:
        if not href:
            continue
        h = href.lower()
        if not out["tock_url"] and "exploretock.com" in h:
            out["tock_url"] = urljoin(base_url or "", href).strip()
        elif not out["resy_url"] and ("resy.com" in h or "widgets.resy.com" in h):
            out["resy_url"] = urljoin(base_url or "", href).strip()
        elif not out["opentable_url"] and "opentable.com" in h:
            out["opentable_url"] = urljoin(base_url or "", href).strip()
        if all(out.values()):
            break
    return out


def _clean_slug(slug: str) -> str:
    if not slug:
        return ""
    slug = slug.lower()
    if any(slug.endswith(e) for e in _ASSET_EXTS):
        return ""
    if slug in _GENERIC_SLUGS:
        return ""
    return slug


def parse_tock_slug(url: str) -> str:
    m = TOCK_RE.search(url or "")
    return _clean_slug(m.group(1)) if m else ""


def parse_resy_slug(url: str) -> str:
    m = RESY_RE.search(url or "")
    if m:
        return _clean_slug(m.group(1) or m.group(2) or "")
    m = RESY_WIDGET_RE.search(url or "")
    return m.group(1).lower() if m else ""


# ── Tier 1: httpx hardened ───────────────────────────────────────────


async def tier1_httpx(client: httpx.AsyncClient, url: str) -> tuple[str, str, str]:
    for attempt in (0, 1):
        try:
            r = await client.get(url, headers=CHROME_HEADERS, timeout=20.0, follow_redirects=True)
            if "text/html" not in r.headers.get("content-type", ""):
                return "", str(r.url), f"non_html_{r.status_code}"
            return r.text, str(r.url), str(r.status_code)
        except httpx.TimeoutException:
            if attempt:
                return "", url, "timeout"
        except Exception as e:
            return "", url, f"err:{type(e).__name__}"
    return "", url, "timeout"


# ── Tier 2: curl-cffi ────────────────────────────────────────────────


def tier2_curl_cffi(url: str) -> tuple[str, str, str]:
    from curl_cffi import requests as crq
    try:
        r = crq.get(
            url,
            impersonate="chrome",
            timeout=20,
            allow_redirects=True,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        if "text/html" not in r.headers.get("content-type", ""):
            return "", str(r.url), f"non_html_{r.status_code}"
        return r.text, str(r.url), str(r.status_code)
    except Exception as e:
        return "", url, f"err:{type(e).__name__}"


# ── Tier 3: Playwright ───────────────────────────────────────────────


async def tier3_playwright(browser, url: str) -> tuple[str, str, str]:
    ctx = await browser.new_context(
        user_agent=CHROME_HEADERS["User-Agent"],
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    page = await ctx.new_page()
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        html = await page.content()
        final = page.url
        status = str(resp.status) if resp else "no_resp"
        return html, final, status
    except Exception as e:
        return "", url, f"err:{type(e).__name__}"
    finally:
        try:
            await page.close()
            await ctx.close()
        except Exception:
            pass


# ── Tier 4: Serper site: search ──────────────────────────────────────


async def tier4_serper(client: httpx.AsyncClient, name: str, city: str, platform: str) -> str:
    """Return first matching URL from a Google site: search, or empty string."""
    if not SERPER_API_KEY or not name:
        return ""
    domain = "exploretock.com" if platform == "tock" else "resy.com"
    q = f'site:{domain} "{name}" {city}'.strip()
    try:
        r = await client.post(
            "https://google.serper.dev/search",
            json={"q": q, "num": 5},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=10.0,
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        for item in (data.get("organic") or []):
            link = item.get("link", "")
            if domain not in link.lower():
                continue
            # Only accept links that yield a real venue slug
            slug = parse_tock_slug(link) if platform == "tock" else parse_resy_slug(link)
            if slug:
                return link
    except Exception:
        return ""
    return ""


# ── Per-merchant waterfall ───────────────────────────────────────────


def found_hit(out: dict) -> bool:
    return bool(out.get("tock_url") or out.get("resy_url"))


def apply_hits(out: dict, hits: dict, base_url: str):
    if not out["tock_url"] and hits.get("tock_url"):
        out["tock_url"] = hits["tock_url"]
    if not out["resy_url"] and hits.get("resy_url"):
        out["resy_url"] = hits["resy_url"]


async def process_merchant(
    row: dict, httpx_client: httpx.AsyncClient, browser, serper_client: httpx.AsyncClient
) -> dict:
    out = {c: "" for c in OUT_COLS}
    for k in ("cid", "name", "website", "business_type", "city", "state", "april_reservation_url"):
        out[k] = row.get(k, "")
    out["scraped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out["recovered_via"] = "none"
    out["tier_attempts"] = ""

    url = normalize_url(out["website"])
    last_status = ""
    attempts = []

    if url:
        # Tier 1
        attempts.append("tier1_httpx")
        html, final, status = await tier1_httpx(httpx_client, url)
        last_status = status
        if html:
            apply_hits(out, extract_platform_links(html, final), final)
            if found_hit(out):
                out["recovered_via"] = "tier1_httpx"

        # Tier 2
        if not found_hit(out):
            attempts.append("tier2_curlcffi")
            html, final, status = await asyncio.to_thread(tier2_curl_cffi, url)
            last_status = status
            if html:
                apply_hits(out, extract_platform_links(html, final), final)
                if found_hit(out):
                    out["recovered_via"] = "tier2_curlcffi"

        # Tier 3
        if not found_hit(out):
            attempts.append("tier3_playwright")
            html, final, status = await tier3_playwright(browser, url)
            last_status = status
            if html:
                apply_hits(out, extract_platform_links(html, final), final)
                if found_hit(out):
                    out["recovered_via"] = "tier3_playwright"

    # Tier 4 — Serper fallback (only target the platform April said they were on)
    if not found_hit(out):
        wants_tock = row.get("lost_tock") == "1"
        wants_resy = row.get("lost_resy") == "1"
        if wants_tock:
            attempts.append("tier4_serper_tock")
            link = await tier4_serper(serper_client, row.get("name", ""), row.get("city", ""), "tock")
            if link:
                out["tock_url"] = link
                if not out["recovered_via"] or out["recovered_via"] == "none":
                    out["recovered_via"] = "tier4_serper"
        if wants_resy and not out["resy_url"]:
            attempts.append("tier4_serper_resy")
            link = await tier4_serper(serper_client, row.get("name", ""), row.get("city", ""), "resy")
            if link:
                out["resy_url"] = link
                if not out["recovered_via"] or out["recovered_via"] == "none":
                    out["recovered_via"] = "tier4_serper"

    out["tier_attempts"] = ",".join(attempts)
    out["last_status"] = last_status
    out["tock_slug"] = parse_tock_slug(out["tock_url"])
    out["resy_slug"] = parse_resy_slug(out["resy_url"])
    out["tock_embed_only"] = "1" if out["tock_url"] and not out["tock_slug"] else ""
    out["resy_embed_only"] = "1" if out["resy_url"] and not out["resy_slug"] else ""
    return out


# ── Driver ───────────────────────────────────────────────────────────


def load_done_cids() -> set:
    if not os.path.exists(PROGRESS_PATH):
        return set()
    try:
        df = pd.read_csv(PROGRESS_PATH, usecols=["cid"], dtype=str)
        return set(df["cid"].dropna().astype(str).tolist())
    except Exception:
        return set()


async def main(limit: int | None, concurrency: int, input_path: str, progress_path: str):
    global PROGRESS_PATH
    PROGRESS_PATH = progress_path
    df = pd.read_csv(input_path, dtype=str).fillna("")
    print(f"Loaded lost merchants: {len(df):,}")

    done = load_done_cids()
    if done:
        print(f"Resuming — {len(done):,} already done")
        df = df[~df["cid"].astype(str).isin(done)]
    if limit:
        df = df.head(limit)
    print(f"To process: {len(df):,}")
    if df.empty:
        print("Nothing to do.")
        return

    from playwright.async_api import async_playwright

    write_header = not os.path.exists(PROGRESS_PATH) or os.path.getsize(PROGRESS_PATH) == 0
    f = open(PROGRESS_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        f.flush()

    httpx_limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(20.0, connect=10.0)

    sem = asyncio.Semaphore(concurrency)
    counts = {"tier1_httpx": 0, "tier2_curlcffi": 0, "tier3_playwright": 0, "tier4_serper": 0, "none": 0}
    t0 = time.time()
    completed = 0

    async def worker(row):
        nonlocal completed
        async with sem:
            res = await process_merchant(row, httpx_client, browser, serper_client)
        writer.writerow(res)
        counts[res["recovered_via"]] += 1
        completed += 1
        if completed % 25 == 0:
            f.flush()
            elapsed = time.time() - t0
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (len(df) - completed) / rate if rate > 0 else 0
            print(
                f"  [{completed}/{len(df)}] "
                f"t1={counts['tier1_httpx']} t2={counts['tier2_curlcffi']} "
                f"t3={counts['tier3_playwright']} t4={counts['tier4_serper']} "
                f"none={counts['none']} | {rate:.2f}/s ETA {eta/60:.1f}min",
                flush=True,
            )
        return res

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        async with httpx.AsyncClient(
            http2=True, limits=httpx_limits, timeout=timeout, verify=False
        ) as httpx_client, httpx.AsyncClient(timeout=10.0) as serper_client:
            rows = df.to_dict("records")
            tasks = [asyncio.create_task(worker(r)) for r in rows]
            await asyncio.gather(*tasks)
        await browser.close()

    f.flush()
    f.close()
    print(f"\nDone in {(time.time()-t0)/60:.1f}min")
    print(f"  Recovered via tier1: {counts['tier1_httpx']}")
    print(f"  Recovered via tier2: {counts['tier2_curlcffi']}")
    print(f"  Recovered via tier3: {counts['tier3_playwright']}")
    print(f"  Recovered via tier4: {counts['tier4_serper']}")
    print(f"  Still missed:        {counts['none']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--input", default=INPUT_PATH)
    ap.add_argument("--progress", default=PROGRESS_PATH)
    args = ap.parse_args()
    asyncio.run(main(args.limit, args.concurrency, args.input, args.progress))
