"""
Phase 2: Enrich leads with website analysis, social media data.
Optimized for concurrency — Serper (50 req/s), Apify (256 concurrent runs).
"""
import os
import re
import time
import threading
from datetime import datetime
import requests
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import pandas as pd
from apify_client import ApifyClient
from config import (
    APIFY_API_TOKEN, RESERVATION_PLATFORMS,
    APIFY_ACTOR_GOOGLE_REVIEWS, APIFY_ACTOR_IG_REELS, APIFY_ACTOR_IG_POSTS,
    APIFY_ACTOR_OPENTABLE, RESERVATION_DIFFICULTY_KEYWORDS,
    GOOGLE_REVIEWS_MAX_PER_PLACE, RESY_API_BASE, RESY_API_KEY,
    SERPER_API_KEY, PRESS_DOMAINS,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _atomic_csv_write(df: pd.DataFrame, path: str):
    """Write CSV atomically: write to .tmp then rename, so crashes don't corrupt."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


# --- Rate limiter for Serper (shared across enrichment phases) ---
SERPER_RPS = 45
_serper_lock = threading.Lock()
_serper_times: list[float] = []


def _serper_rate_limit():
    """Token-bucket rate limiter for Serper API calls."""
    with _serper_lock:
        now = time.monotonic()
        while _serper_times and _serper_times[0] < now - 1.0:
            _serper_times.pop(0)
        if len(_serper_times) >= SERPER_RPS:
            sleep_until = _serper_times[0] + 1.0
            wait = sleep_until - now
            if wait > 0:
                time.sleep(wait)
        _serper_times.append(time.monotonic())


# ─── Website Analysis ────────────────────────────────────────────────

ECOMMERCE_SIGNALS = [
    "shopify", "squarespace", "woocommerce", "bigcommerce", "square",
    "add to cart", "add-to-cart", "shop now", "order online", "buy now",
    "online store", "online ordering", "delivery", "shipping",
    "goldbelly", "mercato", "toast", "chowly",
]

EMAIL_SIGNALS = [
    "mailchimp", "klaviyo", "constant contact", "mailerlite", "convertkit",
    "sendinblue", "hubspot", "newsletter", "sign up", "signup",
    "email list", "subscribe", "join our list", "get updates",
    "popup", "email-signup", "email_signup",
]

ONLINE_ORDER_SIGNALS = [
    "order online", "online ordering", "place order", "order now",
    "pickup", "curbside", "delivery available", "ship nationwide",
    "ships nationwide", "we ship", "order for delivery",
    "toast", "square online", "chownow",
]


def analyze_website(url: str) -> dict:
    """Crawl a website and extract signals."""
    result = {
        "website_reachable": False,
        "has_ecommerce": False,
        "has_email_signup": False,
        "has_online_ordering": False,
        "instagram_url": "",
        "facebook_url": "",
        "ecommerce_platform": "",
        "email_platform": "",
        "page_title": "",
        "reservation_difficulty": 0,
        "reservation_url": "",
        "domain_age": 0,
    }

    if not url or not isinstance(url, str):
        return result

    if not url.startswith("http"):
        url = "https://" + url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        result["website_reachable"] = True

        html = resp.text.lower()
        soup = BeautifulSoup(resp.text, "html.parser")

        if soup.title:
            result["page_title"] = soup.title.string or ""

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "instagram.com/" in href and "/p/" not in href:
                result["instagram_url"] = href.strip()
            elif "facebook.com/" in href and "/sharer" not in href:
                result["facebook_url"] = href.strip()

        for signal in ECOMMERCE_SIGNALS:
            if signal in html:
                result["has_ecommerce"] = True
                if signal in ["shopify"]:
                    result["ecommerce_platform"] = "Shopify"
                elif signal in ["squarespace"]:
                    result["ecommerce_platform"] = "Squarespace"
                elif signal in ["woocommerce"]:
                    result["ecommerce_platform"] = "WooCommerce"
                elif signal in ["square"]:
                    result["ecommerce_platform"] = "Square"
                break

        for signal in EMAIL_SIGNALS:
            if signal in html:
                result["has_email_signup"] = True
                if signal in ["mailchimp"]:
                    result["email_platform"] = "Mailchimp"
                elif signal in ["klaviyo"]:
                    result["email_platform"] = "Klaviyo"
                elif signal in ["constant contact"]:
                    result["email_platform"] = "Constant Contact"
                elif signal in ["convertkit"]:
                    result["email_platform"] = "ConvertKit"
                break

        for signal in ONLINE_ORDER_SIGNALS:
            if signal in html:
                result["has_online_ordering"] = True
                break

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            for platform, difficulty in RESERVATION_PLATFORMS.items():
                if platform in href:
                    if difficulty > result["reservation_difficulty"]:
                        result["reservation_difficulty"] = difficulty
                        result["reservation_url"] = a_tag["href"].strip()

        shop_paths = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            if any(kw in href for kw in ["/shop", "/store", "/order", "/products", "/menu"]):
                full_url = urljoin(url, a_tag["href"])
                if urlparse(full_url).netloc == urlparse(url).netloc:
                    shop_paths.append(full_url)

        for shop_url in shop_paths[:1]:
            try:
                resp2 = requests.get(shop_url, headers=headers, timeout=8, allow_redirects=True)
                html2 = resp2.text.lower()
                for signal in ECOMMERCE_SIGNALS:
                    if signal in html2:
                        result["has_ecommerce"] = True
                        break
                for signal in ONLINE_ORDER_SIGNALS:
                    if signal in html2:
                        result["has_online_ordering"] = True
                        break
            except Exception:
                pass

    except Exception:
        pass

    return result


def enrich_websites(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich all leads with website analysis data, processing in chunks to save RAM."""
    print(f"\n{'='*60}")
    print(f"PHASE 2a: ANALYZING WEBSITES")
    print(f"{'='*60}")

    enrichment_cols = ["website_reachable", "has_ecommerce", "has_email_signup",
                       "has_online_ordering", "instagram_url", "facebook_url",
                       "ecommerce_platform", "email_platform", "page_title",
                       "reservation_difficulty", "reservation_url", "domain_age"]

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_websites.csv")

    # Resume: check if partial output exists with enrichment cols
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "website_reachable" in existing.columns and len(existing) > 0:
            already_done = len(existing)
            if already_done < len(df):
                print(f"  Resuming from {already_done}/{len(df)} (partial output found)")
                for col in enrichment_cols:
                    if col not in df.columns:
                        df[col] = pd.array([""] * len(df), dtype="object")
                    df[col] = df[col].astype("object")
                    df.loc[df.index[:already_done], col] = existing[col].iloc[:already_done].values
                df_remaining = df.iloc[already_done:].copy()
            else:
                print(f"  Website enrichment already complete ({already_done} rows). Skipping.")
                return existing
        else:
            df_remaining = df.copy()
    else:
        df_remaining = df.copy()
        for col in enrichment_cols:
            df[col] = pd.array([""] * len(df), dtype="object")

    # Ensure enrichment cols are object dtype (not StringDtype)
    for col in enrichment_cols:
        if col in df.columns:
            df[col] = df[col].astype("object")

    total = len(df)
    chunk_size = 5000
    start_offset = total - len(df_remaining)
    chunks = [df_remaining.iloc[i:i + chunk_size] for i in range(0, len(df_remaining), chunk_size)]

    print(f"  Crawling {len(df_remaining)} websites in {len(chunks)} chunks of {chunk_size} (50 threads)...")
    print()

    def process_row(idx, url):
        return idx, analyze_website(url)

    for chunk_num, chunk in enumerate(chunks):
        results = {}
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {
                executor.submit(process_row, idx, row["website"]): idx
                for idx, row in chunk.iterrows()
            }
            done = 0
            for future in as_completed(futures):
                idx, data = future.result()
                results[idx] = data
                done += 1
                if done % 100 == 0:
                    processed = start_offset + chunk_num * chunk_size + done
                    print(f"  Processed {processed}/{total} websites...", flush=True)

        # Apply results to main df
        for col in enrichment_cols:
            for idx in results:
                val = results.get(idx, {}).get(col, "")
                if not isinstance(val, str):
                    val = str(val) if val is not None else ""
                df.at[idx, col] = val

        # Save after each chunk
        processed_total = start_offset + (chunk_num + 1) * chunk_size
        processed_total = min(processed_total, total)
        _atomic_csv_write(df.iloc[:processed_total], output_path)
        print(f"  [Saved checkpoint: {processed_total}/{total} rows to {output_path}]", flush=True)
        del results  # free RAM

    # Final save of complete df
    _atomic_csv_write(df, output_path)

    reachable = df["website_reachable"].astype(bool).sum() if "website_reachable" in df.columns else 0
    ecom = df["has_ecommerce"].astype(bool).sum() if "has_ecommerce" in df.columns else 0
    email = df["has_email_signup"].astype(bool).sum() if "has_email_signup" in df.columns else 0
    ig = (df["instagram_url"] != "").sum() if "instagram_url" in df.columns else 0
    fb = (df["facebook_url"] != "").sum() if "facebook_url" in df.columns else 0

    print(f"\n  Websites reachable: {reachable}")
    print(f"  Have ecommerce: {ecom}")
    print(f"  Have email signup: {email}")
    print(f"  Instagram found: {ig}")
    print(f"  Facebook found: {fb}")

    return df


# ─── Instagram Enrichment via Apify ──────────────────────────────────

def extract_ig_username(url) -> str:
    """Extract Instagram username from URL."""
    if not url or not isinstance(url, str):
        return ""
    url = url.rstrip("/")
    match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", url)
    if match:
        username = match.group(1)
        if username in ["p", "reel", "stories", "explore", "accounts"]:
            return ""
        return username
    return ""


def _scrape_ig_profiles_batch(usernames: list[str], batch_label: str = "") -> dict:
    """Scrape a single batch of IG profiles. Returns {username: data_dict}."""
    if not usernames:
        return {}
    client = ApifyClient(APIFY_API_TOKEN)
    try:
        run = client.actor("apify/instagram-profile-scraper").call(
            run_input={"usernames": usernames}
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        results = {}
        for item in items:
            username = item.get("username", "").lower()
            results[username] = {
                "ig_followers": item.get("followersCount", 0),
                "ig_following": item.get("followsCount", 0),
                "ig_posts": item.get("postsCount", 0),
                "ig_bio": item.get("biography", ""),
                "ig_is_verified": item.get("verified", False),
                "ig_is_business": item.get("isBusinessAccount", False),
                "avg_video_views": item.get("avgVideoViews", 0) or 0,
                "avg_likes": item.get("avgLikes", 0) or 0,
            }
        return results
    except Exception as e:
        print(f"  [ERROR] IG profile batch {batch_label} failed: {e}", flush=True)
        return {}


def enrich_instagram(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with Instagram data via Apify (concurrent batches, saves checkpoints)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2b: SCRAPING INSTAGRAM PROFILES")
    print(f"{'='*60}")

    df["ig_username"] = df["instagram_url"].apply(extract_ig_username)
    usernames = df[df["ig_username"] != ""]["ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles found to scrape")
        for col in ["ig_followers", "ig_posts", "ig_is_business"]:
            df[col] = 0
        return df

    print(f"  Found {len(usernames)} Instagram profiles to scrape")

    # Check for existing partial IG data to skip already-scraped usernames
    ig_cols = ["ig_followers", "ig_posts", "ig_is_business", "avg_video_views", "avg_likes"]
    output_path = os.path.join(OUTPUT_DIR, "2_enriched_instagram.csv")
    all_ig_data = {}

    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "ig_followers" in existing.columns:
            has_data = existing[existing["ig_followers"] > 0]
            if len(has_data) > 0:
                for _, row in has_data.iterrows():
                    u = str(row.get("ig_username", "")).lower()
                    if u:
                        all_ig_data[u] = {col: row.get(col, 0) for col in ig_cols}
                already_scraped = set(all_ig_data.keys())
                usernames = [u for u in usernames if u.lower() not in already_scraped]
                print(f"  Resuming: {len(already_scraped)} profiles already scraped, {len(usernames)} remaining")

    if not usernames:
        print("  All Instagram profiles already scraped. Applying data...")
    else:
        batch_size = 30
        batches = [usernames[i:i + batch_size] for i in range(0, len(usernames), batch_size)]
        total_batches = len(batches)
        concurrent_batches = 8
        checkpoint_every = 50

        print(f"  {total_batches} batches of {batch_size}, {concurrent_batches} concurrent Apify runs")
        print(f"  Saving checkpoint every {checkpoint_every} batches")

        completed = 0
        for chunk_start in range(0, total_batches, checkpoint_every):
            chunk_end = min(chunk_start + checkpoint_every, total_batches)
            chunk_batches = batches[chunk_start:chunk_end]

            with ThreadPoolExecutor(max_workers=concurrent_batches) as executor:
                futures = {
                    executor.submit(_scrape_ig_profiles_batch, batch, f"{chunk_start+j+1}/{total_batches}"): j
                    for j, batch in enumerate(chunk_batches)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    all_ig_data.update(batch_results)
                    completed += 1
                    if completed % 10 == 0 or completed == total_batches:
                        print(f"  Completed {completed}/{total_batches} batches, {len(all_ig_data)} profiles so far", flush=True)

            # Save checkpoint after each chunk of batches
            for col in ig_cols:
                default = 0 if col != "ig_is_business" else False
                df[col] = df["ig_username"].apply(
                    lambda u, c=col, d=default: all_ig_data.get(u.lower(), {}).get(c, d) if isinstance(u, str) and u else d
                )
            _atomic_csv_write(df, output_path)
            print(f"  [Saved checkpoint: {completed}/{total_batches} batches to {output_path}]", flush=True)

    # Final apply
    for col in ig_cols:
        default = 0 if col != "ig_is_business" else False
        df[col] = df["ig_username"].apply(
            lambda u, c=col, d=default: all_ig_data.get(u.lower(), {}).get(c, d) if isinstance(u, str) and u else d
        )

    print(f"\n  Instagram enrichment complete")
    has_data = (df["ig_followers"] > 0).sum()
    print(f"  Profiles with follower data: {has_data}")

    return df


# ─── Facebook Enrichment (basic — from page HTML) ───────────────────

def scrape_facebook_likes(fb_url) -> dict:
    """Try to get basic Facebook page data from public page."""
    result = {"fb_likes": 0, "fb_page_name": ""}
    if not fb_url or not isinstance(fb_url, str):
        return result
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = requests.get(fb_url, headers=headers, timeout=8)
        html = resp.text
        likes_match = re.search(r'"follower_count":(\d+)', html)
        if likes_match:
            result["fb_likes"] = int(likes_match.group(1))
        name_match = re.search(r'"name":"([^"]+)"', html)
        if name_match:
            result["fb_page_name"] = name_match.group(1)
    except Exception:
        pass
    return result


def enrich_facebook(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich with Facebook page data (chunked, checkpointed)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2c: CHECKING FACEBOOK PAGES")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_social.csv")

    # Resume: check for existing partial data
    already_done_indices = set()
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "fb_likes" in existing.columns and len(existing) == len(df):
            has_data = existing[existing["fb_likes"].fillna(0) > 0]
            already_done_indices = set(has_data.index)
            if "fb_likes" not in df.columns:
                df["fb_likes"] = 0
            df.loc[has_data.index, "fb_likes"] = has_data["fb_likes"].values
            print(f"  Resuming: {len(already_done_indices)} pages already scraped")

    fb_mask = df["facebook_url"].fillna("").astype(str).pipe(lambda s: (s != "") & (s != "nan"))
    fb_indices = [i for i in df.loc[fb_mask].index if i not in already_done_indices]

    if not fb_indices:
        if "fb_likes" not in df.columns:
            df["fb_likes"] = 0
        print(f"  No Facebook pages to check (or all done)")
    else:
        print(f"  {len(fb_indices)} Facebook pages to check (30 concurrent threads)")
        if "fb_likes" not in df.columns:
            df["fb_likes"] = 0

        chunk_size = 5000
        chunks = [fb_indices[i:i + chunk_size] for i in range(0, len(fb_indices), chunk_size)]

        def process_fb(idx, url):
            return idx, scrape_facebook_likes(url)

        for chunk_num, chunk_indices in enumerate(chunks):
            results = {}
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = {
                    executor.submit(process_fb, idx, df.at[idx, "facebook_url"]): idx
                    for idx in chunk_indices
                    if isinstance(df.at[idx, "facebook_url"], str)
                }
                done = 0
                for future in as_completed(futures):
                    idx, data = future.result()
                    results[idx] = data
                    done += 1
                    if done % 100 == 0:
                        print(f"  Processed {done}/{len(futures)} Facebook pages...", flush=True)

            for idx, data in results.items():
                df.at[idx, "fb_likes"] = data.get("fb_likes", 0)

            _atomic_csv_write(df, output_path)
            total_done = len(already_done_indices) + (chunk_num + 1) * chunk_size
            print(f"  [Saved checkpoint: chunk {chunk_num+1}/{len(chunks)}]", flush=True)
            del results

    has_likes = (df["fb_likes"].fillna(0) > 0).sum()
    print(f"  Pages with like data: {has_likes}")

    ig = df["ig_followers"].fillna(0).astype(int) if "ig_followers" in df.columns else 0
    fb = df["fb_likes"].fillna(0).astype(int)
    df["follower_count"] = ig + fb

    return df


# ─── Press & Awards Enrichment via Serper ─────────────────────────


def search_press_mentions(business_name: str, city: str) -> dict:
    """Search Serper for press coverage on food media sites."""
    _serper_rate_limit()
    result = {"press_mentions": 0, "press_sources": ""}
    site_query = " OR ".join(f"site:{d}" for d in PRESS_DOMAINS)
    query = f'"{business_name}" ({site_query})'
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": 10},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        organic = data.get("organic", [])
        sources = set()
        for r in organic:
            link = r.get("link", "")
            for domain in PRESS_DOMAINS:
                if domain in link:
                    sources.add(domain)
        result["press_mentions"] = len(organic)
        result["press_sources"] = ", ".join(sorted(sources))
    except Exception:
        pass
    return result


def search_awards(business_name: str, city: str, business_type: str = "") -> dict:
    """Search for James Beard, Michelin, and other food/wine/butcher awards."""
    _serper_rate_limit()
    result = {"awards_count": 0, "awards_list": ""}
    award_keywords = ["James Beard", "Michelin", "best new restaurant", "Food & Wine best"]
    if business_type == "wine_store":
        award_keywords.extend([
            "Wine Spectator", "Wine Enthusiast", "best wine shop",
            "wine store of the year", "top wine shop",
        ])
    if business_type == "butcher":
        award_keywords.extend([
            "best butcher", "craft butcher award", "best meat shop",
            "top butcher shop", "butcher of the year",
        ])
    query = f'"{business_name}" {city} ({" OR ".join(award_keywords)})'
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": 10},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        organic = data.get("organic", [])
        awards_found = set()
        for r in organic:
            title = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            if "james beard" in title:
                awards_found.add("James Beard")
            if "michelin" in title:
                awards_found.add("Michelin")
            if "best new restaurant" in title:
                awards_found.add("Best New Restaurant")
            if "wine spectator" in title:
                awards_found.add("Wine Spectator")
            if "wine enthusiast" in title:
                awards_found.add("Wine Enthusiast")
            if "best wine" in title:
                awards_found.add("Best Wine Shop")
            if "best butcher" in title:
                awards_found.add("Best Butcher")
            if "best meat" in title:
                awards_found.add("Best Meat Shop")
        result["awards_count"] = len(awards_found)
        result["awards_list"] = ", ".join(sorted(awards_found))
    except Exception:
        pass
    return result


def enrich_press_and_awards(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with press mentions and awards data (chunked, checkpointed)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2d: SEARCHING PRESS & AWARDS")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_full.csv")
    press_cols = ["press_mentions", "press_sources", "awards_count", "awards_list"]

    for col in press_cols:
        if col not in df.columns:
            df[col] = 0 if col in ("press_mentions", "awards_count") else ""

    # Resume: check for existing partial data
    already_done_indices = set()
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "press_mentions" in existing.columns and len(existing) == len(df):
            has_data = existing[(existing["press_mentions"].fillna(0) > 0) | (existing["awards_count"].fillna(0) > 0)]
            already_done_indices = set(has_data.index)
            for col in press_cols:
                if col in existing.columns:
                    df[col] = existing[col]
            print(f"  Resuming: {len(already_done_indices)} businesses already searched")

    remaining_indices = [i for i in df.index if i not in already_done_indices]
    if not remaining_indices:
        print(f"  All businesses already searched. Skipping.")
        return df

    print(f"  Searching {len(remaining_indices)} businesses (40 concurrent threads, rate-limited to {SERPER_RPS} req/s)...")

    def process_press(idx, name, city):
        name = str(name) if isinstance(name, str) else ""
        city = str(city) if isinstance(city, str) else ""
        return idx, search_press_mentions(name, city)

    def process_awards(idx, name, city, btype):
        name = str(name) if isinstance(name, str) else ""
        city = str(city) if isinstance(city, str) else ""
        btype = str(btype) if isinstance(btype, str) else ""
        return idx, search_awards(name, city, btype)

    chunk_size = 5000
    chunks = [remaining_indices[i:i + chunk_size] for i in range(0, len(remaining_indices), chunk_size)]
    global_start = time.monotonic()

    for chunk_num, chunk_indices in enumerate(chunks):
        press_results = {}
        awards_results = {}

        with ThreadPoolExecutor(max_workers=40) as executor:
            press_futures = {
                executor.submit(process_press, idx, df.at[idx, "name"], df.at[idx, "search_city"] if "search_city" in df.columns else ""): idx
                for idx in chunk_indices
            }
            awards_futures = {
                executor.submit(process_awards, idx, df.at[idx, "name"],
                                df.at[idx, "search_city"] if "search_city" in df.columns else "",
                                df.at[idx, "business_type"] if "business_type" in df.columns else ""): idx
                for idx in chunk_indices
            }

            all_futures = {}
            all_futures.update({f: ("press", idx) for f, idx in press_futures.items()})
            all_futures.update({f: ("awards", idx) for f, idx in awards_futures.items()})

            done = 0
            total = len(all_futures)
            last_print = time.monotonic()

            for future in as_completed(all_futures):
                kind, idx = all_futures[future]
                try:
                    result_idx, data = future.result()
                    if kind == "press":
                        press_results[result_idx] = data
                    else:
                        awards_results[result_idx] = data
                except Exception:
                    pass
                done += 1
                now = time.monotonic()
                if now - last_print >= 5.0 or done == total:
                    elapsed = now - global_start
                    print(f"  [chunk {chunk_num+1}/{len(chunks)}] {done}/{total} | {elapsed:.0f}s elapsed", flush=True)
                    last_print = now

        # Apply chunk results to df
        for idx, data in press_results.items():
            df.at[idx, "press_mentions"] = data.get("press_mentions", 0)
            df.at[idx, "press_sources"] = data.get("press_sources", "")
        for idx, data in awards_results.items():
            df.at[idx, "awards_count"] = data.get("awards_count", 0)
            df.at[idx, "awards_list"] = data.get("awards_list", "")

        _atomic_csv_write(df, output_path)
        print(f"  [Saved checkpoint: chunk {chunk_num+1}/{len(chunks)}]", flush=True)
        del press_results, awards_results

    has_press = (df["press_mentions"].fillna(0) > 0).sum()
    has_awards = (df["awards_count"].fillna(0) > 0).sum()
    print(f"\n  Leads with press mentions: {has_press}")
    print(f"  Leads with awards: {has_awards}")

    return df


# ─── Google Reviews & Reservation Sentiment ──────────────────────────

def analyze_reservation_difficulty_from_reviews(reviews: list[dict]) -> tuple[float, list[str]]:
    """Analyze review texts for reservation difficulty mentions."""
    if not reviews:
        return 0.0, []
    mentions = 0
    samples = []
    for review in reviews:
        text = (review.get("snippet") or review.get("text") or review.get("textTranslated") or "").lower()
        if not text:
            continue
        for keyword in RESERVATION_DIFFICULTY_KEYWORDS:
            if keyword in text:
                mentions += 1
                if len(samples) < 3:
                    samples.append(text[:200])
                break
    total = len(reviews)
    if total == 0:
        return 0.0, []
    mention_ratio = mentions / total
    score = min(1.0, mention_ratio * 5)
    return round(score, 3), samples


def _fetch_serper_reviews(cid: str) -> list[dict]:
    """Fetch reviews for a single place via Serper Reviews API."""
    _serper_rate_limit()
    try:
        resp = requests.post(
            "https://google.serper.dev/reviews",
            json={"cid": str(cid), "num": 10},
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("reviews", [])
    except Exception:
        return []


def enrich_google_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with Google Reviews data (chunked, checkpointed)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2e: FETCHING GOOGLE REVIEWS (Serper)")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_reviews.csv")

    if "review_difficulty_sentiment" not in df.columns:
        df["review_difficulty_sentiment"] = 0.0
    if "review_texts_sample" not in df.columns:
        df["review_texts_sample"] = ""

    # Filter valid CIDs (not empty, not "nan")
    mask = df["cid"].astype(str).str.strip().pipe(lambda s: (s != "") & (s != "nan"))
    cid_indices = df.loc[mask].index.tolist()

    if not cid_indices:
        print("  No CIDs found — skipping Google Reviews enrichment")
        return df

    # Resume: check for existing partial data
    already_done_indices = set()
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "review_difficulty_sentiment" in existing.columns and len(existing) == len(df):
            has_data = existing[existing["review_difficulty_sentiment"].fillna(0) > 0]
            already_done_indices = set(has_data.index)
            df["review_difficulty_sentiment"] = existing["review_difficulty_sentiment"]
            if "review_texts_sample" in existing.columns:
                df["review_texts_sample"] = existing["review_texts_sample"]
            print(f"  Resuming: {len(already_done_indices)} places already reviewed")

    remaining = [i for i in cid_indices if i not in already_done_indices]
    if not remaining:
        print(f"  All reviews already fetched. Skipping.")
        return df

    print(f"  {len(remaining)} places to fetch reviews for (40 concurrent threads)")

    def fetch_and_analyze(idx):
        cid_val = str(df.at[idx, "cid"])
        reviews = _fetch_serper_reviews(cid_val)
        if reviews:
            score, sample_texts = analyze_reservation_difficulty_from_reviews(reviews)
            sample_str = " | ".join(sample_texts) if sample_texts else ""
            return idx, score, sample_str
        return idx, 0.0, ""

    chunk_size = 5000
    chunks = [remaining[i:i + chunk_size] for i in range(0, len(remaining), chunk_size)]
    global_start = time.monotonic()

    for chunk_num, chunk_indices in enumerate(chunks):
        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = {executor.submit(fetch_and_analyze, idx): idx for idx in chunk_indices}
            done = 0
            last_print = time.monotonic()
            for future in as_completed(futures):
                idx, score, sample_str = future.result()
                df.at[idx, "review_difficulty_sentiment"] = score
                df.at[idx, "review_texts_sample"] = sample_str
                done += 1
                now = time.monotonic()
                if now - last_print >= 5.0 or done == len(chunk_indices):
                    elapsed = now - global_start
                    rate = done / elapsed if elapsed > 0 else 0
                    print(f"  [chunk {chunk_num+1}/{len(chunks)}] {done}/{len(chunk_indices)} | {elapsed:.0f}s elapsed", flush=True)
                    last_print = now

        _atomic_csv_write(df, output_path)
        print(f"  [Saved checkpoint: chunk {chunk_num+1}/{len(chunks)}]", flush=True)

    has_sentiment = (df["review_difficulty_sentiment"].fillna(0) > 0).sum()
    print(f"\n  Places with reservation difficulty mentions in reviews: {has_sentiment}")

    return df


# ─── Instagram Reels (avg_video_views) ───────────────────────────────

def _scrape_ig_reels_batch(usernames: list[str], batch_label: str = "") -> dict:
    """Scrape Reels for a batch. Returns {username: avg_views}."""
    if not usernames:
        return {}
    client = ApifyClient(APIFY_API_TOKEN)
    try:
        run = client.actor(APIFY_ACTOR_IG_REELS).call(
            run_input={"username": usernames, "resultsLimit": 12}
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        reels_by_user = {}
        for item in items:
            owner = (item.get("ownerUsername") or "").lower()
            views = item.get("videoViewCount") or item.get("playCount") or 0
            if owner and views > 0:
                reels_by_user.setdefault(owner, []).append(views)
        return {user: sum(v) / len(v) for user, v in reels_by_user.items() if v}
    except Exception as e:
        print(f"  [ERROR] IG Reels batch {batch_label} failed: {e}", flush=True)
        return {}


def enrich_instagram_reels(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with avg_video_views from Instagram Reels (chunked, checkpointed)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2f: SCRAPING INSTAGRAM REELS")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_reels.csv")

    mask = df["ig_username"].fillna("").astype(str).str.strip().pipe(lambda s: (s != "") & (s != "nan"))
    usernames = df.loc[mask, "ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles — skipping Reels enrichment")
        return df

    # Resume: check for existing partial data
    all_views = {}
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "avg_video_views" in existing.columns and len(existing) == len(df):
            has_data = existing[existing["avg_video_views"].fillna(0) > 0]
            for _, row in has_data.iterrows():
                u = str(row.get("ig_username", "")).lower()
                if u and u != "nan":
                    all_views[u] = row["avg_video_views"]
            already_scraped = set(all_views.keys())
            usernames = [u for u in usernames if u.lower() not in already_scraped]
            print(f"  Resuming: {len(already_scraped)} profiles already scraped, {len(usernames)} remaining")

    if not usernames:
        print("  All Reels already scraped. Applying data...")
    else:
        print(f"  {len(usernames)} profiles to scrape Reels for")

        batch_size = 30
        batches = [usernames[i:i + batch_size] for i in range(0, len(usernames), batch_size)]
        total_batches = len(batches)
        concurrent_batches = 8
        checkpoint_every = 50

        print(f"  {total_batches} batches, {concurrent_batches} concurrent, checkpoint every {checkpoint_every}")

        completed = 0
        for chunk_start in range(0, total_batches, checkpoint_every):
            chunk_end = min(chunk_start + checkpoint_every, total_batches)
            chunk_batches = batches[chunk_start:chunk_end]

            with ThreadPoolExecutor(max_workers=concurrent_batches) as executor:
                futures = {
                    executor.submit(_scrape_ig_reels_batch, batch, f"{chunk_start+j+1}/{total_batches}"): j
                    for j, batch in enumerate(chunk_batches)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    all_views.update(batch_results)
                    completed += 1
                    if completed % 10 == 0 or completed == total_batches:
                        print(f"  Completed {completed}/{total_batches} batches, {len(all_views)} profiles with data", flush=True)

            # Save checkpoint
            existing_col = df["avg_video_views"] if "avg_video_views" in df.columns else 0
            df["avg_video_views"] = df["ig_username"].apply(
                lambda u: all_views.get(u.lower(), 0) if isinstance(u, str) and u else 0
            )
            if isinstance(existing_col, pd.Series):
                no_new = (df["avg_video_views"] == 0) & (existing_col > 0)
                df.loc[no_new, "avg_video_views"] = existing_col[no_new]
            _atomic_csv_write(df, output_path)
            print(f"  [Saved checkpoint: {completed}/{total_batches} batches]", flush=True)

    # Final apply
    existing_col = df["avg_video_views"] if "avg_video_views" in df.columns else 0
    df["avg_video_views"] = df["ig_username"].apply(
        lambda u: all_views.get(u.lower(), 0) if isinstance(u, str) and u else 0
    )
    if isinstance(existing_col, pd.Series):
        no_new = (df["avg_video_views"] == 0) & (existing_col > 0)
        df.loc[no_new, "avg_video_views"] = existing_col[no_new]

    has_views = (df["avg_video_views"] > 0).sum()
    print(f"\n  Profiles with Reels view data: {has_views}")

    return df


# ─── Instagram Posts (avg_likes) ─────────────────────────────────────

def _scrape_ig_posts_batch(usernames: list[str], batch_label: str = "") -> dict:
    """Scrape Posts for a batch. Returns {username: avg_likes}."""
    if not usernames:
        return {}
    client = ApifyClient(APIFY_API_TOKEN)
    try:
        run = client.actor(APIFY_ACTOR_IG_POSTS).call(
            run_input={"username": usernames, "resultsLimit": 12}
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        posts_by_user = {}
        for item in items:
            owner = (item.get("ownerUsername") or "").lower()
            likes = item.get("likesCount", -1)
            if owner and likes >= 0:
                posts_by_user.setdefault(owner, []).append(likes)
        return {user: sum(v) / len(v) for user, v in posts_by_user.items() if v}
    except Exception as e:
        print(f"  [ERROR] IG Posts batch {batch_label} failed: {e}", flush=True)
        return {}


def enrich_instagram_posts(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with avg_likes from Instagram Posts (chunked, checkpointed)."""
    print(f"\n{'='*60}")
    print(f"PHASE 2g: SCRAPING INSTAGRAM POSTS")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_posts.csv")

    mask = df["ig_username"].fillna("").astype(str).str.strip().pipe(lambda s: (s != "") & (s != "nan"))
    usernames = df.loc[mask, "ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles — skipping Posts enrichment")
        return df

    # Resume: check for existing partial data
    all_likes = {}
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "avg_likes" in existing.columns and len(existing) == len(df):
            has_data = existing[existing["avg_likes"].fillna(0) > 0]
            for _, row in has_data.iterrows():
                u = str(row.get("ig_username", "")).lower()
                if u and u != "nan":
                    all_likes[u] = row["avg_likes"]
            already_scraped = set(all_likes.keys())
            usernames = [u for u in usernames if u.lower() not in already_scraped]
            print(f"  Resuming: {len(already_scraped)} profiles already scraped, {len(usernames)} remaining")

    if not usernames:
        print("  All Posts already scraped. Applying data...")
    else:
        print(f"  {len(usernames)} profiles to scrape Posts for")

        batch_size = 30
        batches = [usernames[i:i + batch_size] for i in range(0, len(usernames), batch_size)]
        total_batches = len(batches)
        concurrent_batches = 8
        checkpoint_every = 50

        print(f"  {total_batches} batches, {concurrent_batches} concurrent, checkpoint every {checkpoint_every}")

        completed = 0
        for chunk_start in range(0, total_batches, checkpoint_every):
            chunk_end = min(chunk_start + checkpoint_every, total_batches)
            chunk_batches = batches[chunk_start:chunk_end]

            with ThreadPoolExecutor(max_workers=concurrent_batches) as executor:
                futures = {
                    executor.submit(_scrape_ig_posts_batch, batch, f"{chunk_start+j+1}/{total_batches}"): j
                    for j, batch in enumerate(chunk_batches)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    all_likes.update(batch_results)
                    completed += 1
                    if completed % 10 == 0 or completed == total_batches:
                        print(f"  Completed {completed}/{total_batches} batches, {len(all_likes)} profiles with data", flush=True)

            # Save checkpoint
            existing_col = df["avg_likes"] if "avg_likes" in df.columns else 0
            df["avg_likes"] = df["ig_username"].apply(
                lambda u: all_likes.get(u.lower(), 0) if isinstance(u, str) and u else 0
            )
            if isinstance(existing_col, pd.Series):
                no_new = (df["avg_likes"] == 0) & (existing_col > 0)
                df.loc[no_new, "avg_likes"] = existing_col[no_new]
            _atomic_csv_write(df, output_path)
            print(f"  [Saved checkpoint: {completed}/{total_batches} batches]", flush=True)

    # Final apply
    existing_col = df["avg_likes"] if "avg_likes" in df.columns else 0
    df["avg_likes"] = df["ig_username"].apply(
        lambda u: all_likes.get(u.lower(), 0) if isinstance(u, str) and u else 0
    )
    if isinstance(existing_col, pd.Series):
        no_new = (df["avg_likes"] == 0) & (existing_col > 0)
        df.loc[no_new, "avg_likes"] = existing_col[no_new]

    has_likes = (df["avg_likes"] > 0).sum()
    print(f"\n  Profiles with Post like data: {has_likes}")

    return df


# ─── Booking Availability (OpenTable / Resy) ─────────────────────────

def enrich_booking_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Check actual booking availability for restaurants with reservation platforms."""
    print(f"\n{'='*60}")
    print(f"PHASE 2h: CHECKING BOOKING AVAILABILITY")
    print(f"{'='*60}")

    output_path = os.path.join(OUTPUT_DIR, "2_enriched_availability.csv")

    # Resume: check for existing data
    if os.path.exists(output_path):
        existing = pd.read_csv(output_path)
        if "booking_availability_score" in existing.columns and len(existing) == len(df):
            non_default = existing[existing["booking_availability_score"].fillna(1.0) != 1.0]
            if len(non_default) > 0:
                print(f"  Resuming: {len(non_default)} restaurants already checked")
                df["booking_availability_score"] = existing["booking_availability_score"]
                return df

    mask = df["reservation_difficulty"].fillna(0).astype(int) >= 1
    candidates = df.loc[mask]

    if candidates.empty:
        print("  No restaurants with reservation platforms — skipping")
        df["booking_availability_score"] = 1.0
        return df

    print(f"  Found {len(candidates)} restaurants with reservation platforms")

    from datetime import timedelta
    today = datetime.now().date()
    check_dates = [
        (today + timedelta(days=1)).isoformat(),
        (today + timedelta(days=3)).isoformat(),
        (today + timedelta(days=7)).isoformat(),
    ]

    client = ApifyClient(APIFY_API_TOKEN)
    availability_scores = {}

    # --- OpenTable (reservation_difficulty == 1) ---
    ot_mask = candidates["reservation_difficulty"].astype(int) == 1
    ot_rows = candidates.loc[ot_mask]

    if not ot_rows.empty:
        print(f"\n  Checking OpenTable availability for {len(ot_rows)} restaurants...")

        ot_urls = []
        ot_indices = []
        for idx, row in ot_rows.iterrows():
            url = row.get("reservation_url", "")
            if url and "opentable.com" in url.lower():
                ot_urls.append(url)
                ot_indices.append(idx)

        if ot_urls:
            # Run OpenTable batches concurrently (4 at a time)
            batch_size = 20
            ot_batches = []
            for i in range(0, len(ot_urls), batch_size):
                ot_batches.append((ot_urls[i:i + batch_size], ot_indices[i:i + batch_size]))

            def scrape_ot_batch(batch_urls, batch_indices):
                results = {}
                run_input = {
                    "startUrls": [{"url": u} for u in batch_urls],
                    "dates": check_dates,
                    "partySize": 2,
                    "time": "19:00",
                }
                try:
                    run = client.actor(APIFY_ACTOR_OPENTABLE).call(run_input=run_input)
                    items = client.dataset(run["defaultDatasetId"]).list_items().items
                    for item in items:
                        source_url = item.get("url", "")
                        slots = item.get("availableSlots") or item.get("timeslots") or []
                        slot_count = len(slots) if isinstance(slots, list) else 0
                        for j, url in enumerate(batch_urls):
                            if source_url and url.rstrip("/") in source_url:
                                results.setdefault(batch_indices[j], []).append(slot_count)
                                break
                except Exception as e:
                    print(f"  [ERROR] OpenTable scrape failed: {e}", flush=True)
                return results

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(scrape_ot_batch, urls, indices): i
                    for i, (urls, indices) in enumerate(ot_batches)
                }
                for future in as_completed(futures):
                    batch_results = future.result()
                    for idx, slots in batch_results.items():
                        availability_scores.setdefault(idx, []).extend(slots)

    # --- Resy (reservation_difficulty == 2) ---
    resy_mask = candidates["reservation_difficulty"].astype(int) == 2
    resy_rows = candidates.loc[resy_mask]

    if not resy_rows.empty and RESY_API_KEY:
        print(f"\n  Checking Resy availability for {len(resy_rows)} restaurants (30 concurrent)...")

        def check_resy(idx, resy_url):
            if not resy_url or "resy.com" not in resy_url.lower():
                return idx, None
            slug_match = re.search(r"resy\.com/cities/[^/]+/([^/?]+)", resy_url)
            if not slug_match:
                return idx, None
            venue_slug = slug_match.group(1)
            total_slots = 0
            for date in check_dates:
                try:
                    resp = requests.get(
                        f"{RESY_API_BASE}/find",
                        params={
                            "lat": 0, "long": 0,
                            "day": date,
                            "party_size": 2,
                            "venue_id": venue_slug,
                        },
                        headers={
                            "Authorization": f'ResyAPI api_key="{RESY_API_KEY}"',
                            "X-Resy-Auth-Token": RESY_API_KEY,
                        },
                        timeout=10,
                    )
                    if resp.ok:
                        data = resp.json()
                        slots = data.get("results", {}).get("venues", [])
                        for venue in slots:
                            slot_list = venue.get("slots", [])
                            total_slots += len(slot_list)
                except Exception:
                    pass
            return idx, [total_slots / len(check_dates)] if total_slots else [0]

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {
                executor.submit(check_resy, idx, row.get("reservation_url", "")): idx
                for idx, row in resy_rows.iterrows()
            }
            for future in as_completed(futures):
                idx, slots = future.result()
                if slots is not None:
                    availability_scores[idx] = slots

    elif not resy_rows.empty and not RESY_API_KEY:
        print(f"  Skipping Resy checks — RESY_API_KEY not set")

    # Compute normalized score
    max_slots_per_date = 10.0

    def compute_availability(idx):
        if idx not in availability_scores:
            return 1.0
        slots = availability_scores[idx]
        avg_slots = sum(slots) / len(slots) if slots else 0
        return round(min(1.0, avg_slots / max_slots_per_date), 3)

    df["booking_availability_score"] = df.index.map(
        lambda i: compute_availability(i) if i in availability_scores else 1.0
    )

    checked = len(availability_scores)
    fully_booked = sum(1 for v in availability_scores.values() if sum(v) == 0)
    print(f"\n  Checked availability: {checked}")
    print(f"  Fully booked (score=0): {fully_booked}")

    _atomic_csv_write(df, output_path)
    print(f"  [Saved checkpoint to {output_path}]", flush=True)

    return df


if __name__ == "__main__":
    result = analyze_website("https://www.publicanqualitymeats.com")
    for k, v in result.items():
        print(f"  {k}: {v}")
