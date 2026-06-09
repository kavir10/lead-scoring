"""
Detect existing club/subscription/membership programs by scraping websites.
Runs concurrently on a CSV of discovered leads. Outputs the same CSV with
new columns: has_club, club_type, club_url, club_signals.

Usage:
    python detect_clubs.py input.csv                          # default 50 threads
    python detect_clubs.py input.csv --threads 100            # more threads
    python detect_clubs.py input.csv -o output/with_clubs.csv # custom output path
    python detect_clubs.py input.csv --resume                 # resume from partial output
"""
import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ─── Club/Subscription Signals ──────────────────────────────────────

# Keywords found in page text or HTML that indicate a club program
CLUB_KEYWORDS = [
    # ── direct club terms (food-specific) ──
    "wine club", "meat club", "cheese club", "beer club", "coffee club",
    "bread club", "fish club", "seafood club", "produce club", "food club",
    "butcher club", "baker club", "bakery club", "pickle club", "sauce club",
    "snack club", "dessert club", "chocolate club", "pasta club",
    "olive oil club", "spice club", "tea club", "cocktail club",
    "spirits club", "whiskey club", "bourbon club", "sake club",
    "charcuterie club", "salami club", "jerky club", "honey club",
    "jam club", "hot sauce club", "bbq club", "barbeque club",
    "ramen club", "noodle club", "pizza club", "bagel club",
    "sourdough club", "pastry club", "pie club", "cookie club",
    "cake club", "ice cream club", "gelato club",
    "supper club", "dinner club", "chef's club", "chef club",
    "tasting club", "cellar club", "bottle club", "growler club",
    "harvest club", "provisions club", "pantry club",
    # ── "of the month" programs (specific only — generic "of the month" is too noisy) ──
    "wine of the month", "meat of the month", "cheese of the month",
    "beer of the month", "coffee of the month", "meal of the month",
    "bottle of the month", "box of the month", "bread of the month",
    "chocolate of the month", "spice of the month", "tea of the month",
    "seafood of the month", "fish of the month", "snack of the month",
    # ── subscription terms ──
    "subscription box", "subscribe and save", "subscribe & save",
    "monthly subscription", "weekly subscription", "quarterly subscription",
    "annual subscription", "yearly subscription", "biweekly subscription",
    "subscription plan", "subscription program", "subscription service",
    "subscription offering", "start a subscription", "start your subscription",
    "manage subscription", "my subscription", "cancel subscription",
    "subscription details", "subscription faq",
    "recurring delivery", "recurring order", "scheduled delivery",
    "auto-renew", "auto renew", "autoship", "auto-ship",
    "auto delivery", "auto-delivery", "automatic delivery",
    "standing order", "repeat order",
    # ── membership terms ──
    "membership program", "member program", "become a member",
    "join the club", "join our club",
    "member benefits", "members only", "member exclusive",
    "membership plan", "membership tier", "membership level",
    "membership options", "membership details",
    "vip membership", "loyalty membership", "premium membership",
    "founding member", "charter member",
    "member perks", "member rewards", "member discount",
    "members receive", "members get", "member pricing",
    "insider club", "inner circle",
    # ── CSA / box / share terms ──
    "csa program", "csa share", "csa box", "csa membership", "csa signup",
    "csa sign-up", "csa season", "csa pickup",
    "community supported agriculture", "community supported fishery",
    "community supported bakery", "community supported brewery",
    "farm share", "farm box", "harvest box", "produce box",
    "weekly box", "monthly box", "curated box", "mystery box",
    "tasting box", "discovery box", "seasonal box", "sampler box",
    "snack box", "treat box", "gift box subscription",
    "meat share", "fish share", "bread share", "veggie share",
    "butcher box", "seafood box", "cheese box", "charcuterie box",
    # ── delivery cadence language ──
    "delivered monthly", "delivered weekly", "delivered quarterly",
    "delivered biweekly", "delivered every",
    "ships monthly", "ships weekly", "ships quarterly",
    "ships every", "shipped monthly", "shipped weekly",
    "sign up for delivery", "schedule your delivery",
    # ── pricing / plan language ──
    "choose your plan", "select a plan", "pick your plan",
    "3-month plan", "6-month plan", "12-month plan",
    "month-to-month",
    "gift a subscription", "gift subscription", "gift a membership",
    "gift the club",
    # ── waitlist / allocation language (high-end clubs) ──
    "allocation list", "allocation program", "mailing list allocation",
    "waitlist for club", "club waitlist", "limited allocation",
    "limited membership",
]

# Platform signals — searched in raw HTML (including script/meta tags) since
# these appear as class names, data attributes, or JS config rather than page text.
PLATFORM_SIGNALS = [
    # ── Shopify subscription apps ──
    "recharge subscription", "recharge-subscription", "rc-subscription",
    "bold subscriptions", "bold-subscriptions",
    "ordergroove", "order groove",
    "yotpo subscriptions", "yotpo-subscriptions",
    "loop subscriptions", "loop-subscriptions",
    "seal subscriptions", "seal-subscriptions",
    "appstle subscription", "appstle-subscription",
    "paywhirl", "pay-whirl",
    "skio subscriptions", "skio-subscriptions",
    "awtomatic", "awtomatic-subscription",
    "smartrr", "smartrr-subscription",
    "stay ai", "stay-ai-subscription",
    # ── Billing / commerce platforms (subscription-specific only) ──
    "cratejoy", "subbly",
    "shopify subscription", "squarespace-subscription",
    # ── Wine & beverage industry platforms (club-specific) ──
    "winedirect", "wine-direct", "wine direct",
    "vin65", "vin-65",
    "wineclub.com", "wine-club-software",
    "vinoshipper", "vino-shipper", "vinoshipper.com",
    "wineshipping", "wine-shipping",
    "offsetpartners", "offset-partners",
    "barrel-order",
    # ── Food subscription / CSA platforms ──
    "farmigo", "harvie", "barn2door", "barn-2-door",
    "local-line", "localline", "local line",
    "cropolis", "csaware", "csa-ware",
    "re:farm", "small farm central",
    # ── Membership / loyalty platforms ──
    "patreon.com", "memberful", "memberspace",
]

# URL path segments that suggest a club/subscription page
CLUB_URL_PATHS = [
    "/club", "/clubs",
    "/wine-club", "/wineclub", "/meat-club", "/meatclub",
    "/cheese-club", "/cheeseclub", "/beer-club", "/beerclub",
    "/coffee-club", "/coffeeclub",
    "/subscription", "/subscriptions", "/subscribe",
    "/membership", "/memberships", "/members", "/member",
    "/csa", "/farm-share", "/farmshare", "/community-supported",
    "/box", "/monthly-box", "/monthlybox", "/subscription-box",
    "/join", "/join-the-club", "/jointheclub", "/join-now",
    "/loyalty", "/loyalty-program", "/rewards", "/rewards-program",
    "/vip", "/insider", "/perks",
    "/allocation", "/mailing-list",
    "/of-the-month", "/ofthemonth",
    "/recurring", "/auto-ship",
    "/share", "/meat-share", "/fish-share",
    "/supper-club", "/supperclub", "/dinner-club",
]

# Classify what type of club was detected
CLUB_TYPE_PATTERNS = {
    "wine_club": r"wine\s*(club|of the month|subscription|allocation)",
    "meat_club": r"(meat|butcher|charcuterie|salami|jerky)\s*(club|of the month|share|box|subscription)",
    "cheese_club": r"cheese\s*(club|of the month|box|subscription)",
    "beer_club": r"(beer|brew|growler)\s*(club|of the month|subscription)",
    "coffee_club": r"coffee\s*(club|of the month|subscription)",
    "bread_club": r"(bread|sourdough|bagel|bakery|pastry)\s*(club|of the month|share|subscription)",
    "seafood_club": r"(fish|seafood)\s*(club|of the month|share|box|subscription)",
    "supper_club": r"(supper|dinner|chef.?s?)\s*club",
    "csa": r"(csa|community\s*supported|farm\s*share|harvest\s*box|produce\s*box)",
    "subscription_box": r"(subscription\s*box|monthly\s*box|curated\s*box|tasting\s*box|mystery\s*box|sampler\s*box|discovery\s*box)",
    "of_the_month": r"of\s*the\s*(month|week|quarter)",
    "membership": r"(membership\s*(program|plan|tier)|become\s*a\s*member|members?\s*only|insider\s*club|inner\s*circle|founding\s*member)",
    "subscription": r"(subscription|subscribe|recurring|auto.?renew|auto.?ship|auto.?deliver|standing\s*order)",
}


# ─── Scraping Logic ─────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
TIMEOUT = (3, 5)  # (connect_timeout, read_timeout) in seconds


MAX_BODY = 500_000  # 500KB cap — skip huge pages


def _fetch_page(url: str) -> tuple[str, str, BeautifulSoup] | None:
    """Fetch a URL and return (raw_html_lower, visible_text_lower, soup) or None."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                            allow_redirects=True, stream=True)
        resp.raise_for_status()
        # Read up to MAX_BODY bytes then stop — prevents slow-drip hangs
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536, decode_unicode=True):
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_BODY:
                break
        resp.close()
        raw_text = "".join(chunks)
        raw_html = raw_text.lower()
        soup = BeautifulSoup(raw_text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True).lower()
        return raw_html, text, soup
    except Exception:
        return None


def _find_club_subpages(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Find internal links that look like club/subscription pages."""
    found = []
    base_domain = urlparse(base_url).netloc
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].lower()
        full_url = urljoin(base_url, a_tag["href"])
        if urlparse(full_url).netloc != base_domain:
            continue
        for path in CLUB_URL_PATHS:
            if path in href:
                found.append(full_url)
                break
    return list(dict.fromkeys(found))[:2]  # dedupe, limit to 2


def _classify_club_type(signals: list[str]) -> str:
    """Determine the most specific club type from matched signals."""
    combined = " ".join(signals).lower()
    for club_type, pattern in CLUB_TYPE_PATTERNS.items():
        if re.search(pattern, combined):
            return club_type
    return "unknown"


def detect_club(url: str) -> dict:
    """Scrape a website homepage for club/subscription/membership signals."""
    result = {
        "has_club": False,
        "club_type": "",
        "club_url": "",
        "club_signals": "",
    }

    if not url or not isinstance(url, str) or str(url).lower() == "nan":
        return result

    if not url.startswith("http"):
        url = "https://" + url

    page = _fetch_page(url)
    if page is None:
        return result

    raw_html, text, soup = page
    signals = []

    # Content keywords — match against visible text only (no HTML noise)
    for kw in CLUB_KEYWORDS:
        if kw in text:
            signals.append(kw)

    # Platform signals — match against raw HTML (script tags, class names, etc.)
    for kw in PLATFORM_SIGNALS:
        if kw in raw_html:
            signals.append(kw)

    if signals:
        result["has_club"] = True
        result["club_type"] = _classify_club_type(signals)
        result["club_url"] = url
        result["club_signals"] = "; ".join(signals[:10])

    return result


# ─── Batch Processing ────────────────────────────────────────────────

def _atomic_csv_write(df: pd.DataFrame, path: str):
    """Write CSV atomically via temp file."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def run(input_path: str, output_path: str | None, threads: int, resume: bool):
    """Run club detection on all rows in the input CSV."""
    # Unbuffered prints so background jobs show progress
    import functools
    global print
    print = functools.partial(print, flush=True)

    print(f"Loading {input_path}...")
    df = pd.read_csv(input_path)

    if "website" not in df.columns:
        print("ERROR: CSV must have a 'website' column.")
        sys.exit(1)

    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_clubs.csv"

    # New columns — force object dtype to avoid bool/string conflicts
    club_cols = ["has_club", "club_type", "club_url", "club_signals"]
    for col in club_cols:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].astype("object")

    # Resume support
    start_idx = 0
    if resume and os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "has_club" in existing.columns:
            # Only count rows where has_club is actually set (True or False, not empty)
            start_idx = len(existing[existing["has_club"].isin([True, False, "True", "False"])])
            for col in club_cols:
                if col in existing.columns:
                    df[col] = df[col].astype("object")
                    df.loc[df.index[:start_idx], col] = existing[col].iloc[:start_idx].values
            print(f"  Resuming from row {start_idx}/{len(df)}")

    remaining = df.iloc[start_idx:]
    total = len(df)
    to_process = len(remaining)

    if to_process == 0:
        print("All rows already processed.")
        return

    print(f"  Processing {to_process} websites with {threads} threads...")
    print()

    chunk_size = 500
    chunks = [remaining.iloc[i:i + chunk_size] for i in range(0, to_process, chunk_size)]
    processed = start_idx

    for chunk_num, chunk in enumerate(chunks):
        results = {}
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(detect_club, row.get("website", "")): idx
                for idx, row in chunk.iterrows()
            }
            done = 0
            for future in as_completed(futures, timeout=120):
                idx = futures[future]
                try:
                    data = future.result(timeout=8)
                except Exception:
                    data = {"has_club": "False", "club_type": "", "club_url": "", "club_signals": ""}
                results[idx] = data
                done += 1
                if done % 200 == 0:
                    print(f"    Chunk {chunk_num + 1}/{len(chunks)}: {done}/{len(chunk)} done")

        # Write results back to df (cast all values to str to avoid dtype conflicts)
        for idx, data in results.items():
            for col, val in data.items():
                df.at[idx, col] = str(val)

        processed += len(chunk)
        _atomic_csv_write(df, output_path)
        clubs_found = (df["has_club"] == "True").sum()
        print(f"  [{processed}/{total}] saved — {clubs_found} clubs detected so far")

    # Final summary
    clubs_found = (df["has_club"] == "True").sum()
    print(f"\n{'='*60}")
    print(f"DONE: {clubs_found}/{total} businesses have a club/subscription ({clubs_found/total*100:.1f}%)")
    print(f"Output: {output_path}")
    print(f"{'='*60}")

    if clubs_found > 0:
        print(f"\nClub type breakdown:")
        type_counts = df[df["has_club"] == "True"]["club_type"].value_counts()
        for ctype, count in type_counts.items():
            print(f"  {ctype}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Detect club/subscription programs on business websites")
    parser.add_argument("input_csv", help="Path to CSV with a 'website' column")
    parser.add_argument("-o", "--output", help="Output CSV path (default: <input>_clubs.csv)")
    parser.add_argument("--threads", type=int, default=50, help="Number of concurrent threads (default: 50)")
    parser.add_argument("--resume", action="store_true", help="Resume from partial output")
    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"ERROR: File not found: {args.input_csv}")
        sys.exit(1)

    run(args.input_csv, args.output, args.threads, args.resume)


if __name__ == "__main__":
    main()
