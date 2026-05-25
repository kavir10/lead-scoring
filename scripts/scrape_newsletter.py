"""
Async newsletter / email-list scraper across the full ~100K lead universe.

Reads output/newsletter_merchants/inputs/seed_100k.csv, fetches each merchant
website (and up to 2 newsletter/contact-pathed subpages), and writes detected
ESP signals (Mailchimp, Klaviyo, Substack, Beehiiv, ConvertKit, MailerLite,
Constant Contact, Brevo, HubSpot, ActiveCampaign, Flodesk, Drip, Omnisend,
Squarespace-native, Shopify-native, generic forms) to a resumable progress CSV.

Usage:
    python scripts/scrape_newsletter.py                 # full run
    python scripts/scrape_newsletter.py --limit 200     # smoke test
    python scripts/scrape_newsletter.py --concurrency 75
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from selectolax.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(ROOT, "output/newsletter_merchants/inputs/seed_100k.csv")
PROGRESS_PATH = os.path.join(ROOT, "output/newsletter_merchants/raw/scrape_progress.csv")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

# Subpages worth probing if the homepage shows no signal.
SUBPAGE_HINTS = (
    "newsletter", "subscribe", "sign-up", "signup", "sign up",
    "join", "mailing", "stay in touch", "stay-in-touch",
    "contact", "club", "members",
)
FALLBACK_PATHS = (
    "/newsletter", "/subscribe", "/signup", "/sign-up",
    "/join", "/contact", "/club",
)

OUT_COLS = [
    "cid", "name", "website", "business_type", "city", "state",
    "website_status", "final_url",
    "any_signal",
    "esp_platforms",         # semicolon-joined list of canonical ESP names
    "esp_count",
    "form_present",          # 1 if any newsletter-ish <form> with email input
    "popup_signal",          # 1 if popup library / modal-flag observed
    "newsletter_url",        # link to public newsletter (substack/beehiiv/etc.)
    "embed_iframe_host",     # host of first embed iframe found
    "form_action_host",      # host of first newsletter-form action
    "source_path",           # home OR the subpage URL that produced signals
    "raw_signals",           # semicolon list of raw hit tokens (for QA)
    "scraped_at",
]

_ASSET_EXTS = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp",
    ".gif", ".woff", ".woff2", ".mp4", ".pdf",
)


# ─── ESP signal definitions ──────────────────────────────────────────
# Each entry: canonical name -> list of substring tokens. Tokens are matched
# case-insensitively against the raw HTML, the union of href/src attributes,
# and form action values. Order matters only for `esp_platforms` ordering.
ESP_SIGNALS: dict[str, tuple[str, ...]] = {
    "Mailchimp": (
        "list-manage.com", "mailchimp.com/embed", "chimpstatic.com",
        "mc-embedded-subscribe", "mcembedsignup", "mailchimp.com/audience",
        "us1.list-manage.com", "us2.list-manage.com", "us3.list-manage.com",
        "us4.list-manage.com", "us5.list-manage.com", "us6.list-manage.com",
        "us7.list-manage.com", "us8.list-manage.com", "us9.list-manage.com",
        "us10.list-manage.com", "us11.list-manage.com", "us12.list-manage.com",
        "us13.list-manage.com", "us14.list-manage.com", "us15.list-manage.com",
        "us16.list-manage.com", "us17.list-manage.com", "us18.list-manage.com",
        "us19.list-manage.com", "us20.list-manage.com", "us21.list-manage.com",
    ),
    "Klaviyo": (
        "klaviyo.com", "static.klaviyo.com", "kl-private-reset-css",
        "klaviyo_subscribe", "klaviyoembedkey", "a.klaviyo.com",
        "klaviyo-form", "data-klaviyo",
    ),
    "Substack": (
        "substack.com/embed", ".substack.com", "substackcdn.com",
    ),
    "Beehiiv": (
        "beehiiv.com", "embeds.beehiiv.com", "subscribe-forms.beehiiv.com",
    ),
    "ConvertKit": (
        "convertkit.com", "ck-form-id", "ckforms.com", "formkit.com",
        "kit.com/forms", "data-uid=\"",
    ),
    "MailerLite": (
        "mailerlite.com", "ml-form-embed", "assets.mailerlite.com",
        "static.mailerlite.com", "ml-block-form",
    ),
    "Constant Contact": (
        "constantcontact.com", "r20.rs6.net", "static.ctctcdn.com",
        "ctctcdn.com",
    ),
    "Brevo": (
        "sibforms.com", "sendinblue.com", "brevo.com",
    ),
    "HubSpot": (
        "hsforms.net", "js.hsforms.net", "forms.hubspot.com",
        "hubspotusercontent",
    ),
    "ActiveCampaign": (
        "activehosted.com", "activecampaign.com", "_ac_init_form",
    ),
    "Flodesk": (
        "flodesk.com", "assets.flodesk.com", "fd-form",
    ),
    "Drip": (
        "getdrip.com", "drip.com/forms",
    ),
    "Omnisend": (
        "omnisend.com", "omnisrc.com", "omnisend-app",
    ),
    "Squarespace Native": (
        "newsletter-form-block", "newsletterblock", "sqs-async-form",
        "data-block-type=\"5\"",   # squarespace newsletter block type
    ),
    "Shopify Native": (
        "/contact#contact_form", "customer[email]", "contact[email]",
        "shopify-newsletter", "contact_subscribe",
    ),
    "Squarespace Email Campaigns": (
        "campaign-archive.com",
    ),
}

POPUP_TOKENS = (
    "privy.com", "sumo.com", "optinmonster", "wisepops",
    "popupsmart", "justuno", "getsitecontrol", "wheelio",
    "optinly", "klaviyo_subscribe_popup", "data-popup",
    "modal-newsletter", "newsletter-modal", "subscribe-modal",
)

PUBLIC_NEWSLETTER_HOSTS = (
    "substack.com", "beehiiv.com", "ghost.io", "buttondown.email",
    "buttondown.com", "revue.co",
)


# ─── URL helpers ─────────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def is_asset(url: str) -> bool:
    u = (url or "").lower()
    return any(u.endswith(ext) for ext in _ASSET_EXTS)


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def safe_join(base: str, href: str) -> str:
    """urljoin that swallows ValueError from malformed hrefs on Python 3.13+."""
    try:
        return urljoin(base, href)
    except Exception:
        return ""


# ─── Detection ───────────────────────────────────────────────────────


_NEWSLETTER_FORM_HINT_RE = re.compile(
    r"(newsletter|subscribe|signup|sign[\-_ ]up|mailing|email[\-_ ]list|join[\-_ ]our)",
    re.I,
)


def collect_link_attrs(tree: HTMLParser) -> list[str]:
    """All href/src/action attributes from the page."""
    out: list[str] = []
    for css, attr in (
        ("a[href]", "href"),
        ("iframe[src]", "src"),
        ("script[src]", "src"),
        ("link[href]", "href"),
        ("form[action]", "action"),
        ("img[src]", "src"),
    ):
        for tag in tree.css(css):
            v = tag.attributes.get(attr, "")
            if v:
                out.append(v)
    return out


def detect_form_signal(tree: HTMLParser, base_url: str) -> dict:
    """Look for <form> elements with email input + newsletter-ish naming."""
    out = {
        "form_present": False,
        "form_action_host": "",
    }
    for f in tree.css("form"):
        # Need at least one email-type input
        has_email = False
        for inp in f.css("input"):
            t = (inp.attributes.get("type") or "").lower()
            n = (inp.attributes.get("name") or "").lower()
            ph = (inp.attributes.get("placeholder") or "").lower()
            if t == "email" or "email" in n or "email" in ph:
                has_email = True
                break
        if not has_email:
            continue

        # Newsletter-ish?
        haystack = " ".join(
            (f.attributes.get(k) or "")
            for k in ("id", "class", "name", "aria-label", "action")
        )
        if not _NEWSLETTER_FORM_HINT_RE.search(haystack):
            # Also check nearby form-html (placeholders, button text) within form
            inner = (f.html or "")[:2000].lower()
            if not _NEWSLETTER_FORM_HINT_RE.search(inner):
                continue

        out["form_present"] = True
        action = (f.attributes.get("action") or "").strip()
        if action:
            full = safe_join(base_url, action)
            h = host_of(full)
            if h and h != host_of(base_url):
                out["form_action_host"] = h
        break
    return out


def detect_esp(html_lower: str, link_blob_lower: str) -> tuple[list[str], list[str]]:
    """Return (esp_canonical_names, raw_hit_tokens)."""
    hits: list[str] = []
    raw: list[str] = []
    combined = html_lower + " " + link_blob_lower
    for name, tokens in ESP_SIGNALS.items():
        for tk in tokens:
            if tk in combined:
                hits.append(name)
                raw.append(tk)
                break
    return hits, raw


def detect_popup(html_lower: str, link_blob_lower: str) -> bool:
    blob = html_lower + " " + link_blob_lower
    return any(tk in blob for tk in POPUP_TOKENS)


def detect_newsletter_url(tree: HTMLParser, base_url: str) -> str:
    """Find a link pointing to a public newsletter host (substack/beehiiv/etc.)."""
    for a in tree.css("a[href]"):
        href = a.attributes.get("href", "") or ""
        if not href:
            continue
        full = safe_join(base_url, href)
        if not full:
            continue
        h = host_of(full)
        if any(host in h for host in PUBLIC_NEWSLETTER_HOSTS):
            return full.strip()
    return ""


def detect_embed_iframe_host(tree: HTMLParser, base_url: str) -> str:
    """First iframe whose host is a known ESP/newsletter host."""
    esp_host_tokens = []
    for tokens in ESP_SIGNALS.values():
        esp_host_tokens.extend(t for t in tokens if "/" not in t and "[" not in t)
    esp_host_tokens.extend(PUBLIC_NEWSLETTER_HOSTS)
    for f in tree.css("iframe[src]"):
        src = (f.attributes.get("src") or "").strip()
        if not src:
            continue
        full = safe_join(base_url, src)
        if not full:
            continue
        h = host_of(full)
        if any(tok in h for tok in esp_host_tokens):
            return h
    return ""


def analyze_page(html: str, base_url: str) -> dict:
    """Extract all signals from one HTML page."""
    out = {
        "esp_platforms": [],
        "raw_signals": [],
        "form_present": False,
        "form_action_host": "",
        "popup_signal": False,
        "newsletter_url": "",
        "embed_iframe_host": "",
    }
    if not html:
        return out

    try:
        tree = HTMLParser(html)
    except Exception:
        return out

    try:
        html_lower = html.lower()
        link_blob = " ".join(collect_link_attrs(tree)).lower()

        esps, raw = detect_esp(html_lower, link_blob)
        out["esp_platforms"] = esps
        out["raw_signals"] = raw
        out["popup_signal"] = detect_popup(html_lower, link_blob)
        out["newsletter_url"] = detect_newsletter_url(tree, base_url)
        out["embed_iframe_host"] = detect_embed_iframe_host(tree, base_url)
        form_sig = detect_form_signal(tree, base_url)
        out["form_present"] = form_sig["form_present"]
        out["form_action_host"] = form_sig["form_action_host"]
    except Exception:
        pass
    return out


def merge_page_results(dst: dict, src: dict) -> None:
    """Union ESPs/raw; prefer first-seen non-empty for scalar fields."""
    for name in src["esp_platforms"]:
        if name not in dst["esp_platforms"]:
            dst["esp_platforms"].append(name)
    for tk in src["raw_signals"]:
        if tk not in dst["raw_signals"]:
            dst["raw_signals"].append(tk)
    if src["form_present"]:
        dst["form_present"] = True
    if src["popup_signal"]:
        dst["popup_signal"] = True
    for k in ("newsletter_url", "embed_iframe_host", "form_action_host"):
        if not dst.get(k) and src.get(k):
            dst[k] = src[k]


def pick_fallback_paths(html: str, base_url: str) -> list[str]:
    """Up to 2 same-domain subpages whose href/text hints at newsletter signup."""
    if not html:
        return []
    try:
        tree = HTMLParser(html)
    except Exception:
        return []

    base_host = host_of(base_url)
    seen = set()
    picks: list[str] = []
    for tag in tree.css("a[href]"):
        href = tag.attributes.get("href", "") or ""
        text = (tag.text() or "").lower()
        if not href or is_asset(href):
            continue
        h_lower = href.lower()
        if not any(hint in h_lower or hint in text for hint in SUBPAGE_HINTS):
            continue
        full = safe_join(base_url, href)
        if not full:
            continue
        if host_of(full) and host_of(full) != base_host:
            continue
        if full in seen:
            continue
        seen.add(full)
        picks.append(full)
        if len(picks) >= 2:
            return picks

    if not picks:
        for p in FALLBACK_PATHS[:2]:
            joined = safe_join(base_url, p)
            if joined:
                picks.append(joined)
    return picks


# ─── Async fetch ─────────────────────────────────────────────────────


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

    aggregated = {
        "esp_platforms": [],
        "raw_signals": [],
        "form_present": False,
        "form_action_host": "",
        "popup_signal": False,
        "newsletter_url": "",
        "embed_iframe_host": "",
    }
    source_path = "home"

    async with sem:
        html, final_url, status = await fetch(client, raw_url)
        out["website_status"] = status
        out["final_url"] = final_url

        if html:
            home_hits = analyze_page(html, final_url)
            merge_page_results(aggregated, home_hits)

            # Probe subpages if home produced no signal
            home_signal = (
                bool(home_hits["esp_platforms"])
                or home_hits["form_present"]
                or home_hits["newsletter_url"]
            )
            if not home_signal:
                for sp in pick_fallback_paths(html, final_url):
                    sub_html, sub_final, sub_status = await fetch(client, sp)
                    if not sub_html:
                        continue
                    sub_hits = analyze_page(sub_html, sub_final)
                    if (
                        sub_hits["esp_platforms"]
                        or sub_hits["form_present"]
                        or sub_hits["newsletter_url"]
                    ):
                        merge_page_results(aggregated, sub_hits)
                        source_path = sub_final
                        # Keep probing the second subpage only if still no ESP match
                        if aggregated["esp_platforms"]:
                            break

    out["esp_platforms"] = ";".join(aggregated["esp_platforms"])
    out["esp_count"] = str(len(aggregated["esp_platforms"]))
    out["form_present"] = "1" if aggregated["form_present"] else ""
    out["popup_signal"] = "1" if aggregated["popup_signal"] else ""
    out["newsletter_url"] = aggregated["newsletter_url"]
    out["embed_iframe_host"] = aggregated["embed_iframe_host"]
    out["form_action_host"] = aggregated["form_action_host"]
    out["source_path"] = source_path
    out["raw_signals"] = ";".join(aggregated["raw_signals"])
    out["any_signal"] = "1" if (
        aggregated["esp_platforms"]
        or aggregated["form_present"]
        or aggregated["newsletter_url"]
    ) else ""
    return out


# ─── Driver ──────────────────────────────────────────────────────────


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

    write_header = (
        not os.path.exists(PROGRESS_PATH)
        or os.path.getsize(PROGRESS_PATH) == 0
    )
    f = open(PROGRESS_PATH, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=OUT_COLS, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        f.flush()

    limits = httpx.Limits(
        max_connections=concurrency * 2,
        max_keepalive_connections=concurrency,
    )
    client_timeout = httpx.Timeout(timeout, connect=min(timeout, 6.0))

    sem = asyncio.Semaphore(concurrency)
    t0 = time.time()
    completed = 0
    sig_hits = 0
    esp_hits = 0
    form_hits = 0
    err_hits = 0
    flush_every = 500

    rows = seed.to_dict("records")
    total = len(rows)
    # Chunk to keep memory bounded — pre-allocating 60K+ tasks at once OOMs.
    chunk_size = max(concurrency * 20, 1000)

    async with httpx.AsyncClient(
        http2=True, limits=limits, timeout=client_timeout, verify=False
    ) as client:
        for chunk_start in range(0, total, chunk_size):
            chunk = rows[chunk_start:chunk_start + chunk_size]
            tasks = [asyncio.create_task(scrape_one(client, sem, r)) for r in chunk]
            for fut in asyncio.as_completed(tasks):
                res = await fut
                writer.writerow(res)
                completed += 1
                if res["any_signal"]:
                    sig_hits += 1
                if res["esp_platforms"]:
                    esp_hits += 1
                if res["form_present"]:
                    form_hits += 1
                if res["website_status"] and not res["website_status"].startswith(
                    ("200", "non_html")
                ):
                    err_hits += 1

                if completed % flush_every == 0:
                    f.flush()
                    elapsed = time.time() - t0
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(
                        f"  [{completed:,}/{total:,}] "
                        f"any={sig_hits} esp={esp_hits} form={form_hits} err={err_hits} "
                        f"| {rate:.1f}/s | ETA {eta/60:.1f}min",
                        flush=True,
                    )
            # Release task list memory between chunks
            tasks.clear()
            f.flush()

    f.flush()
    f.close()
    print(
        f"\nDone in {(time.time()-t0)/60:.1f}min. "
        f"any={sig_hits} esp={esp_hits} form={form_hits} errors={err_hits}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--timeout", type=float, default=12.0)
    args = ap.parse_args()
    asyncio.run(main(args.limit, args.concurrency, args.timeout))
