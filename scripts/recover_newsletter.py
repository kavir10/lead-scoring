"""
Waterfall recovery for newsletter scrape error rows. Each row flows
through two tiers and exits on the first hit:

  Tier 1: curl-cffi with Chrome TLS impersonation (bypasses Cloudflare JA3)
  Tier 2: Playwright headless Chromium (renders JS-injected forms)

The main scraper already used httpx, so we skip a tier-1 httpx retry.
There's no analog to tier-4 Serper here — newsletter ESPs don't live at
one canonical host like exploretock.com.

Reuses analyze_page() / merge_page_results() from scrape_newsletter.py so
detection logic stays consistent.

Usage:
    python scripts/recover_newsletter.py --limit 100    # smoke test
    python scripts/recover_newsletter.py                # full run
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from scrape_newsletter import (  # type: ignore
    analyze_page,
    merge_page_results,
    normalize_url,
    pick_fallback_paths,
)

INPUT_PATH = os.path.join(ROOT, "output/newsletter_merchants/inputs/recovery_input.csv")
PROGRESS_PATH = os.path.join(ROOT, "output/newsletter_merchants/raw/recovery_progress.csv")

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

OUT_COLS = [
    "cid", "name", "website", "business_type", "city", "state",
    "original_status",
    "recovered_via",          # tier1_curlcffi | tier2_playwright | none
    "website_status",         # status returned by the tier that produced HTML
    "final_url",
    "any_signal",
    "esp_platforms",
    "esp_count",
    "form_present",
    "popup_signal",
    "newsletter_url",
    "embed_iframe_host",
    "form_action_host",
    "source_path",
    "raw_signals",
    "tier_attempts",
    "scraped_at",
]


# ─── Tier 1: curl-cffi ───────────────────────────────────────────────


def tier1_curl_cffi(url: str, timeout: int = 20) -> tuple[str, str, str]:
    """Synchronous; called via asyncio.to_thread."""
    from curl_cffi import requests as crq
    try:
        r = crq.get(
            url,
            impersonate="chrome",
            timeout=timeout,
            allow_redirects=True,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        ct = r.headers.get("content-type", "") or ""
        if "text/html" not in ct and "application/xhtml" not in ct:
            return "", str(r.url), f"non_html_{r.status_code}"
        return r.text, str(r.url), str(r.status_code)
    except Exception as e:
        return "", url, f"err:{type(e).__name__}"


def tier1_subpage_fetch(url: str, timeout: int = 15) -> tuple[str, str, str]:
    return tier1_curl_cffi(url, timeout=timeout)


# ─── Tier 2: Playwright ──────────────────────────────────────────────


async def tier2_playwright(browser, url: str, ua: str) -> tuple[str, str, str]:
    ctx = await browser.new_context(
        user_agent=ua,
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


# ─── Per-row waterfall ───────────────────────────────────────────────


def _empty_signals() -> dict:
    return {
        "esp_platforms": [],
        "raw_signals": [],
        "form_present": False,
        "form_action_host": "",
        "popup_signal": False,
        "newsletter_url": "",
        "embed_iframe_host": "",
    }


def _has_useful_signal(agg: dict) -> bool:
    return bool(agg["esp_platforms"] or agg["form_present"] or agg["newsletter_url"])


def _serialize(out: dict, agg: dict, source_path: str):
    out["esp_platforms"] = ";".join(agg["esp_platforms"])
    out["esp_count"] = str(len(agg["esp_platforms"]))
    out["form_present"] = "1" if agg["form_present"] else ""
    out["popup_signal"] = "1" if agg["popup_signal"] else ""
    out["newsletter_url"] = agg["newsletter_url"]
    out["embed_iframe_host"] = agg["embed_iframe_host"]
    out["form_action_host"] = agg["form_action_host"]
    out["source_path"] = source_path
    out["raw_signals"] = ";".join(agg["raw_signals"])
    out["any_signal"] = "1" if _has_useful_signal(agg) else ""


async def process_row(row: dict, browser, tier1_sem: asyncio.Semaphore,
                      tier2_sem: asyncio.Semaphore) -> dict:
    out = {c: "" for c in OUT_COLS}
    for k in ("cid", "name", "website", "business_type", "city", "state"):
        out[k] = row.get(k, "")
    out["original_status"] = row.get("website_status", "")
    out["scraped_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out["recovered_via"] = "none"

    raw_url = normalize_url(str(row.get("website") or ""))
    if not raw_url:
        out["website_status"] = "no_url"
        out["tier_attempts"] = ""
        return out

    attempts: list[str] = []
    agg = _empty_signals()
    source_path = "home"
    final_url = raw_url
    last_status = ""
    tier1_got_html = False

    # ── Tier 1: curl-cffi ─────────────────────────────────────────────
    attempts.append("tier1_curlcffi")
    async with tier1_sem:
        html, final, status = await asyncio.to_thread(tier1_curl_cffi, raw_url)
    last_status = status
    final_url = final or raw_url
    if html:
        tier1_got_html = True
        home_hits = analyze_page(html, final_url)
        merge_page_results(agg, home_hits)
        if not _has_useful_signal(agg):
            subpages = pick_fallback_paths(html, final_url)
            for sp in subpages:
                async with tier1_sem:
                    sub_html, sub_final, _ = await asyncio.to_thread(tier1_subpage_fetch, sp)
                if not sub_html:
                    continue
                sub_hits = analyze_page(sub_html, sub_final)
                if (sub_hits["esp_platforms"] or sub_hits["form_present"]
                        or sub_hits["newsletter_url"]):
                    merge_page_results(agg, sub_hits)
                    source_path = sub_final
                    if agg["esp_platforms"]:
                        break

        if _has_useful_signal(agg):
            out["recovered_via"] = "tier1_curlcffi"

    # ── Tier 2: Playwright ─────────────────────────────────────────────
    # Only fires when tier 1 failed to get HTML at all (TLS/network block).
    # If curl-cffi already returned the page, Playwright re-fetching the
    # same URL adds zero value — the absent signal is genuinely absent.
    if not _has_useful_signal(agg) and not tier1_got_html:
        attempts.append("tier2_playwright")
        async with tier2_sem:
            html, final, status = await tier2_playwright(
                browser, raw_url, CHROME_HEADERS["User-Agent"]
            )
        last_status = status or last_status
        final_url = final or final_url
        if html:
            home_hits = analyze_page(html, final_url)
            merge_page_results(agg, home_hits)
            if not _has_useful_signal(agg):
                subpages = pick_fallback_paths(html, final_url)
                for sp in subpages[:1]:  # one sub for Playwright (expensive)
                    async with tier2_sem:
                        sub_html, sub_final, _ = await tier2_playwright(
                            browser, sp, CHROME_HEADERS["User-Agent"]
                        )
                    if not sub_html:
                        continue
                    sub_hits = analyze_page(sub_html, sub_final)
                    if (sub_hits["esp_platforms"] or sub_hits["form_present"]
                            or sub_hits["newsletter_url"]):
                        merge_page_results(agg, sub_hits)
                        source_path = sub_final
                        if agg["esp_platforms"]:
                            break

            if _has_useful_signal(agg):
                out["recovered_via"] = "tier2_playwright"

    out["tier_attempts"] = ",".join(attempts)
    out["website_status"] = last_status
    out["final_url"] = final_url
    _serialize(out, agg, source_path)
    return out


# ─── Driver ──────────────────────────────────────────────────────────


def load_done_cids(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    try:
        df = pd.read_csv(path, usecols=["cid"], dtype=str)
        return set(df["cid"].dropna().astype(str).tolist())
    except Exception:
        return set()


async def main(limit: int | None, tier1_concurrency: int, tier2_concurrency: int,
               input_path: str, progress_path: str):
    df = pd.read_csv(input_path, dtype=str).fillna("")
    print(f"Loaded recovery candidates: {len(df):,}")

    done = load_done_cids(progress_path)
    if done:
        print(f"Resuming — {len(done):,} cids already attempted, skipping.")
        df = df[~df["cid"].astype(str).isin(done)]

    if limit:
        df = df.head(limit)
    print(f"To process this run: {len(df):,}")

    if df.empty:
        print("Nothing to do.")
        return

    from playwright.async_api import async_playwright

    os.makedirs(os.path.dirname(progress_path), exist_ok=True)
    write_header = (
        not os.path.exists(progress_path) or os.path.getsize(progress_path) == 0
    )
    f = open(progress_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        f.flush()

    tier1_sem = asyncio.Semaphore(tier1_concurrency)
    tier2_sem = asyncio.Semaphore(tier2_concurrency)
    counts = {"tier1_curlcffi": 0, "tier2_playwright": 0, "none": 0}
    t0 = time.time()
    completed = 0
    flush_every = 50

    chunk_size = max(tier1_concurrency * 8, 200)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        rows = df.to_dict("records")
        total = len(rows)

        for chunk_start in range(0, total, chunk_size):
            chunk = rows[chunk_start:chunk_start + chunk_size]
            tasks = [
                asyncio.create_task(process_row(r, browser, tier1_sem, tier2_sem))
                for r in chunk
            ]
            for fut in asyncio.as_completed(tasks):
                res = await fut
                writer.writerow(res)
                counts[res["recovered_via"]] += 1
                completed += 1
                if completed % flush_every == 0:
                    f.flush()
                    elapsed = time.time() - t0
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(
                        f"  [{completed:,}/{total:,}] "
                        f"t1={counts['tier1_curlcffi']} "
                        f"t2={counts['tier2_playwright']} "
                        f"none={counts['none']} "
                        f"| {rate:.2f}/s | ETA {eta/60:.1f}min",
                        flush=True,
                    )
            tasks.clear()
            f.flush()

        await browser.close()

    f.flush()
    f.close()
    print(f"\nDone in {(time.time()-t0)/60:.1f}min.")
    print(f"  Tier 1 (curl-cffi):    {counts['tier1_curlcffi']:,}")
    print(f"  Tier 2 (Playwright):   {counts['tier2_playwright']:,}")
    print(f"  Still missed:          {counts['none']:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tier1-concurrency", type=int, default=20)
    ap.add_argument("--tier2-concurrency", type=int, default=5)
    ap.add_argument("--input", default=INPUT_PATH)
    ap.add_argument("--progress", default=PROGRESS_PATH)
    args = ap.parse_args()
    asyncio.run(main(
        args.limit, args.tier1_concurrency, args.tier2_concurrency,
        args.input, args.progress,
    ))
