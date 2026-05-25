"""
Async Tock/Resy/OpenTable link scraper for the April 2026 lead universe.

Reads output/resy_tock_merchants/inputs/seed_52k.csv, fetches each merchant
website (and up to 2 reservation-pathed subpages), and writes any detected
exploretock.com / resy.com / opentable.com links to a resumable progress CSV.

Usage:
    python scripts/scrape_resy_tock.py                 # full run
    python scripts/scrape_resy_tock.py --limit 200     # smoke test
    python scripts/scrape_resy_tock.py --concurrency 75
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
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from selectolax.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(ROOT, "output/resy_tock_merchants/inputs/seed_52k.csv")
PROGRESS_PATH = os.path.join(ROOT, "output/resy_tock_merchants/raw/scrape_progress.csv")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

SUBPAGE_HINTS = ("reservation", "reserve", "book", "booking")
FALLBACK_PATHS = ("/reservations", "/reserve", "/book", "/booking", "/menu")

OUT_COLS = [
    "cid", "name", "website", "business_type", "city", "state",
    "website_status", "final_url",
    "tock_url", "tock_slug", "tock_embed_only",
    "resy_url", "resy_slug", "resy_embed_only",
    "opentable_url",
    "source_path",
    "scraped_at",
]

_ASSET_EXTS = (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp", ".gif", ".woff", ".woff2", ".html", ".json")


# ── URL parsing helpers ──────────────────────────────────────────────

TOCK_RE = re.compile(r"exploretock\.com/([^/?#\s\"'<>]+)", re.I)
RESY_RE = re.compile(
    r"resy\.com/(?:cities/[^/]+/(?:venues/)?([^/?#\s\"'<>]+)|venues/([^/?#\s\"'<>]+))",
    re.I,
)
RESY_WIDGET_RE = re.compile(r"widgets\.resy\.com/[^\"'\s<>]*?(?:venueId=|/venue/)([^&\"'\s<>]+)", re.I)


def parse_tock_slug(url: str) -> str:
    m = TOCK_RE.search(url or "")
    if not m:
        return ""
    slug = m.group(1).lower()
    if any(slug.endswith(ext) for ext in _ASSET_EXTS):
        return ""
    return slug


def parse_resy_slug(url: str) -> str:
    m = RESY_RE.search(url or "")
    if m:
        slug = (m.group(1) or m.group(2) or "").lower()
        if any(slug.endswith(ext) for ext in _ASSET_EXTS):
            return ""
        return slug
    m = RESY_WIDGET_RE.search(url or "")
    if m:
        return m.group(1).lower()
    return ""


def is_tock_embed(url: str) -> bool:
    return bool(url) and ("tock.js" in url.lower() or "/embed" in url.lower())


def is_resy_embed(url: str) -> bool:
    return bool(url) and "widgets.resy.com" in url.lower() and not RESY_WIDGET_RE.search(url)


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_platform_links(html: str, base_url: str) -> dict:
    """Scan parsed HTML for tock/resy/opentable links in <a> and <iframe>."""
    out = {"tock_url": "", "resy_url": "", "opentable_url": ""}
    if not html:
        return out

    try:
        tree = HTMLParser(html)
    except Exception:
        return out

    # Walk a + iframe + link tags
    candidates = []
    for tag in tree.css("a[href]"):
        candidates.append(tag.attributes.get("href", ""))
    for tag in tree.css("iframe[src]"):
        candidates.append(tag.attributes.get("src", ""))
    for tag in tree.css("link[href]"):
        candidates.append(tag.attributes.get("href", ""))

    # As a backstop, regex-scan raw HTML for inline-mentioned URLs
    # (some sites bury Resy in <script> data attributes)
    for m in re.finditer(r"https?://[^\s\"'<>)]+", html):
        candidates.append(m.group(0))

    for href in candidates:
        if not href:
            continue
        h = href.lower()
        if not out["tock_url"] and "exploretock.com" in h:
            out["tock_url"] = urljoin(base_url, href).strip()
        elif not out["resy_url"] and ("resy.com" in h or "widgets.resy.com" in h):
            out["resy_url"] = urljoin(base_url, href).strip()
        elif not out["opentable_url"] and "opentable.com" in h:
            out["opentable_url"] = urljoin(base_url, href).strip()
        if all(out.values()):
            break

    return out


def pick_fallback_paths(html: str, base_url: str) -> list[str]:
    """Return up to 2 same-domain subpages whose href/text hints at reservations."""
    if not html:
        return []
    try:
        tree = HTMLParser(html)
    except Exception:
        return []

    base_host = urlparse(base_url).netloc.lower()
    seen = set()
    picks = []
    for tag in tree.css("a[href]"):
        href = tag.attributes.get("href", "") or ""
        text = (tag.text() or "").lower()
        if not href:
            continue
        if not any(h in href.lower() or h in text for h in SUBPAGE_HINTS):
            continue
        full = urljoin(base_url, href)
        host = urlparse(full).netloc.lower()
        if host and host != base_host:
            continue
        if full in seen:
            continue
        seen.add(full)
        picks.append(full)
        if len(picks) >= 2:
            return picks

    # If we found nothing in-text, try canonical fallback paths
    if not picks:
        for p in FALLBACK_PATHS[:2]:
            picks.append(urljoin(base_url, p))
    return picks


# ── Async fetch ──────────────────────────────────────────────────────


FETCH_TIMEOUT = 12.0

async def fetch(client: httpx.AsyncClient, url: str) -> tuple[str, str, str]:
    """Return (html, final_url, status_str)."""
    try:
        r = await client.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, follow_redirects=True)
        ct = r.headers.get("content-type", "")
        if "text/html" not in ct and "application/xhtml" not in ct:
            return "", str(r.url), f"non_html_{r.status_code}"
        return r.text, str(r.url), str(r.status_code)
    except httpx.TimeoutException:
        return "", url, "timeout"
    except httpx.TooManyRedirects:
        return "", url, "too_many_redirects"
    except httpx.HTTPError as e:
        return "", url, f"http_err:{type(e).__name__}"
    except Exception as e:
        return "", url, f"err:{type(e).__name__}"


async def scrape_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, row: dict) -> dict:
    out = {c: "" for c in OUT_COLS}
    for k in ("cid", "name", "website", "business_type", "city", "state"):
        out[k] = row.get(k, "")
    out["scraped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    raw_url = normalize_url(str(row.get("website") or ""))
    if not raw_url:
        out["website_status"] = "no_url"
        return out

    async with sem:
        html, final_url, status = await fetch(client, raw_url)
        out["website_status"] = status
        out["final_url"] = final_url
        out["source_path"] = "home"

        if html:
            hits = extract_platform_links(html, final_url)
            out["tock_url"] = hits["tock_url"]
            out["resy_url"] = hits["resy_url"]
            out["opentable_url"] = hits["opentable_url"]

            # Fallback subpages if no tock/resy found — skip for wine_store (low yield)
            biz_type = (row.get("business_type") or "").lower()
            if not out["tock_url"] and not out["resy_url"] and biz_type != "wine_store":
                subpages = pick_fallback_paths(html, final_url)
                for sp in subpages:
                    sub_html, sub_final, sub_status = await fetch(client, sp)
                    if not sub_html:
                        continue
                    hits2 = extract_platform_links(sub_html, sub_final)
                    if hits2["tock_url"] or hits2["resy_url"] or hits2["opentable_url"]:
                        if not out["tock_url"]:
                            out["tock_url"] = hits2["tock_url"]
                        if not out["resy_url"]:
                            out["resy_url"] = hits2["resy_url"]
                        if not out["opentable_url"]:
                            out["opentable_url"] = hits2["opentable_url"]
                        out["source_path"] = sub_final
                        if out["tock_url"] and out["resy_url"]:
                            break

    out["tock_slug"] = parse_tock_slug(out["tock_url"])
    out["resy_slug"] = parse_resy_slug(out["resy_url"])
    out["tock_embed_only"] = "1" if out["tock_url"] and not out["tock_slug"] else ""
    out["resy_embed_only"] = "1" if out["resy_url"] and not out["resy_slug"] else ""
    return out


# ── Driver ───────────────────────────────────────────────────────────


def load_done_cids(progress_path: str) -> set[str]:
    if not os.path.exists(progress_path):
        return set()
    try:
        df = pd.read_csv(progress_path, usecols=["cid"], dtype=str)
        return set(df["cid"].dropna().astype(str).tolist())
    except Exception:
        return set()


async def main(limit: int | None, concurrency: int, timeout: float):
    global FETCH_TIMEOUT
    FETCH_TIMEOUT = timeout
    seed = pd.read_csv(SEED_PATH, dtype=str).fillna("")
    print(f"Loaded seed: {len(seed):,} rows")

    done = load_done_cids(PROGRESS_PATH)
    if done:
        print(f"Resuming — {len(done):,} cids already scraped, skipping.")
        seed = seed[~seed["cid"].astype(str).isin(done)]

    if limit:
        seed = seed.head(limit)
    print(f"To scrape this run: {len(seed):,}")

    if seed.empty:
        print("Nothing to do.")
        return

    write_header = not os.path.exists(PROGRESS_PATH) or os.path.getsize(PROGRESS_PATH) == 0
    f = open(PROGRESS_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        f.flush()

    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    client_timeout = httpx.Timeout(timeout, connect=min(timeout, 6.0))

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    completed = 0
    tock_hits = 0
    resy_hits = 0
    ot_hits = 0
    err_hits = 0
    flush_every = 500

    async with httpx.AsyncClient(
        http2=True, limits=limits, timeout=client_timeout, verify=False
    ) as client:
        rows = seed.to_dict("records")
        tasks = [asyncio.create_task(scrape_one(client, sem, r)) for r in rows]

        for fut in asyncio.as_completed(tasks):
            res = await fut
            writer.writerow(res)
            completed += 1
            if res["tock_url"]:
                tock_hits += 1
            if res["resy_url"]:
                resy_hits += 1
            if res["opentable_url"]:
                ot_hits += 1
            if res["website_status"] and not res["website_status"].startswith(("200", "non_html")):
                err_hits += 1

            if completed % flush_every == 0:
                f.flush()
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(rows) - completed) / rate if rate > 0 else 0
                print(
                    f"  [{completed:,}/{len(rows):,}] "
                    f"tock={tock_hits} resy={resy_hits} ot={ot_hits} err={err_hits} "
                    f"| {rate:.1f}/s | ETA {eta/60:.1f}min",
                    flush=True,
                )

    f.flush()
    f.close()
    print(
        f"\nDone in {(time.time()-t0)/60:.1f}min. "
        f"tock={tock_hits} resy={resy_hits} opentable={ot_hits} errors={err_hits}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()
    asyncio.run(main(args.limit, args.concurrency, args.timeout))
