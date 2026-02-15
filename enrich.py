"""
Phase 2: Enrich leads with website analysis, social media data
"""
import re
import time
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
)


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

    if not url:
        return result

    # Normalize URL
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

        # Page title
        if soup.title:
            result["page_title"] = soup.title.string or ""

        # Find social media links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "instagram.com/" in href and "/p/" not in href:
                result["instagram_url"] = href.strip()
            elif "facebook.com/" in href and "/sharer" not in href:
                result["facebook_url"] = href.strip()

        # Check for ecommerce signals
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

        # Check for email signup signals
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

        # Check for online ordering
        for signal in ONLINE_ORDER_SIGNALS:
            if signal in html:
                result["has_online_ordering"] = True
                break

        # Check for reservation platforms and capture booking URL
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            for platform, difficulty in RESERVATION_PLATFORMS.items():
                if platform in href:
                    if difficulty > result["reservation_difficulty"]:
                        result["reservation_difficulty"] = difficulty
                        result["reservation_url"] = a_tag["href"].strip()

        # Also check a few subpages if we find links to /shop, /order, /products
        shop_paths = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            if any(kw in href for kw in ["/shop", "/store", "/order", "/products", "/menu"]):
                full_url = urljoin(url, a_tag["href"])
                if urlparse(full_url).netloc == urlparse(url).netloc:
                    shop_paths.append(full_url)

        # Check first shop page found
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

    except Exception as e:
        pass

    return result


def enrich_websites(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich all leads with website analysis data."""
    print(f"\n{'='*60}")
    print(f"PHASE 2a: ANALYZING WEBSITES")
    print(f"{'='*60}")
    print(f"Crawling {len(df)} websites for social links, email, ecommerce signals...")
    print()

    results = {}

    def process_row(idx, url):
        return idx, analyze_website(url)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(process_row, idx, row["website"]): idx
            for idx, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            idx, data = future.result()
            results[idx] = data
            done += 1
            if done % 25 == 0:
                print(f"  Processed {done}/{len(df)} websites...")

    print(f"  Processed {len(results)}/{len(df)} websites total")

    # Merge results into DataFrame
    for col in ["website_reachable", "has_ecommerce", "has_email_signup",
                "has_online_ordering", "instagram_url", "facebook_url",
                "ecommerce_platform", "email_platform", "page_title",
                "reservation_difficulty", "reservation_url", "domain_age"]:
        df[col] = df.index.map(lambda i: results.get(i, {}).get(col, ""))

    reachable = df["website_reachable"].sum()
    ecom = df["has_ecommerce"].sum()
    email = df["has_email_signup"].sum()
    ig = (df["instagram_url"] != "").sum()
    fb = (df["facebook_url"] != "").sum()

    print(f"\n  Websites reachable: {reachable}")
    print(f"  Have ecommerce: {ecom}")
    print(f"  Have email signup: {email}")
    print(f"  Instagram found: {ig}")
    print(f"  Facebook found: {fb}")

    return df


# ─── Instagram Enrichment via Apify ──────────────────────────────────

def extract_ig_username(url: str) -> str:
    """Extract Instagram username from URL."""
    if not url:
        return ""
    url = url.rstrip("/")
    # Handle various IG URL formats
    match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", url)
    if match:
        username = match.group(1)
        # Filter out generic pages
        if username in ["p", "reel", "stories", "explore", "accounts"]:
            return ""
        return username
    return ""


def scrape_instagram_batch(usernames: list[str]) -> dict:
    """Use Apify Instagram Profile Scraper to get profile data."""
    if not usernames:
        return {}

    client = ApifyClient(APIFY_API_TOKEN)

    print(f"  Starting Apify Instagram scrape for {len(usernames)} profiles...")

    run_input = {
        "usernames": usernames,
    }

    try:
        run = client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items

        results = {}
        for item in dataset_items:
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

        print(f"  Got data for {len(results)} Instagram profiles")
        return results

    except Exception as e:
        print(f"  [ERROR] Apify Instagram scrape failed: {e}")
        return {}


def enrich_instagram(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with Instagram data via Apify."""
    print(f"\n{'='*60}")
    print(f"PHASE 2b: SCRAPING INSTAGRAM PROFILES")
    print(f"{'='*60}")

    # Extract usernames from IG URLs
    df["ig_username"] = df["instagram_url"].apply(extract_ig_username)
    usernames = df[df["ig_username"] != ""]["ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles found to scrape")
        for col in ["ig_followers", "ig_posts", "ig_is_business"]:
            df[col] = 0
        return df

    print(f"  Found {len(usernames)} Instagram profiles to scrape")

    # Batch in groups of 30 to avoid timeout
    batch_size = 30
    all_ig_data = {}

    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        print(f"\n  Batch {i // batch_size + 1}/{(len(usernames) - 1) // batch_size + 1} ({len(batch)} profiles)")
        batch_results = scrape_instagram_batch(batch)
        all_ig_data.update(batch_results)
        if i + batch_size < len(usernames):
            time.sleep(2)

    # Merge into DataFrame
    for col in ["ig_followers", "ig_posts", "ig_is_business", "avg_video_views", "avg_likes"]:
        default = 0 if col != "ig_is_business" else False
        df[col] = df["ig_username"].apply(
            lambda u: all_ig_data.get(u.lower(), {}).get(col, default) if u else default
        )

    print(f"\n  Instagram enrichment complete")
    has_data = (df["ig_followers"] > 0).sum()
    print(f"  Profiles with follower data: {has_data}")

    return df


# ─── Facebook Enrichment (basic — from page HTML) ───────────────────

def scrape_facebook_likes(fb_url: str) -> dict:
    """Try to get basic Facebook page data from public page."""
    result = {"fb_likes": 0, "fb_page_name": ""}

    if not fb_url:
        return result

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        resp = requests.get(fb_url, headers=headers, timeout=8)
        html = resp.text

        # Try to extract follower/like count from meta tags or page content
        likes_match = re.search(r'"follower_count":(\d+)', html)
        if likes_match:
            result["fb_likes"] = int(likes_match.group(1))

        # Try page name
        name_match = re.search(r'"name":"([^"]+)"', html)
        if name_match:
            result["fb_page_name"] = name_match.group(1)

    except Exception:
        pass

    return result


def enrich_facebook(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich with Facebook page data."""
    print(f"\n{'='*60}")
    print(f"PHASE 2c: CHECKING FACEBOOK PAGES")
    print(f"{'='*60}")

    fb_urls = df[df["facebook_url"] != ""]["facebook_url"].tolist()
    print(f"  Found {len(fb_urls)} Facebook pages to check")

    if not fb_urls:
        df["fb_likes"] = 0
        return df

    results = {}

    def process_fb(idx, url):
        return idx, scrape_facebook_likes(url)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for idx, row in df.iterrows():
            if row.get("facebook_url", ""):
                futures[executor.submit(process_fb, idx, row["facebook_url"])] = idx

        for future in as_completed(futures):
            idx, data = future.result()
            results[idx] = data

    df["fb_likes"] = df.index.map(lambda i: results.get(i, {}).get("fb_likes", 0))

    has_likes = (df["fb_likes"] > 0).sum()
    print(f"  Pages with like data: {has_likes}")

    # Compute combined follower count for scoring
    ig = df["ig_followers"].fillna(0).astype(int) if "ig_followers" in df.columns else 0
    fb = df["fb_likes"].fillna(0).astype(int)
    df["follower_count"] = ig + fb

    return df


# ─── Press & Awards Enrichment via Serper ─────────────────────────

def search_press_mentions(business_name: str, city: str) -> dict:
    """Search Serper for press coverage on food media sites."""
    from config import SERPER_API_KEY, PRESS_DOMAINS

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


def search_awards(business_name: str, city: str) -> dict:
    """Search for James Beard, Michelin, and other food awards."""
    from config import SERPER_API_KEY

    result = {"awards_count": 0, "awards_list": ""}

    award_keywords = ["James Beard", "Michelin", "best new restaurant", "Food & Wine best"]
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

        result["awards_count"] = len(awards_found)
        result["awards_list"] = ", ".join(sorted(awards_found))
    except Exception:
        pass

    return result


def enrich_press_and_awards(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with press mentions and awards data."""
    print(f"\n{'='*60}")
    print(f"PHASE 2d: SEARCHING PRESS & AWARDS")
    print(f"{'='*60}")
    print(f"  Searching {len(df)} businesses for press coverage and awards...")

    press_results = {}
    awards_results = {}

    def process_press(idx, name, city):
        return idx, search_press_mentions(name, city)

    def process_awards(idx, name, city):
        return idx, search_awards(name, city)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_press, idx, row["name"], row.get("search_city", "")): idx
            for idx, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            idx, data = future.result()
            press_results[idx] = data
            done += 1
            if done % 25 == 0:
                print(f"  Press: {done}/{len(df)}...")

        time.sleep(1)

        futures = {
            executor.submit(process_awards, idx, row["name"], row.get("search_city", "")): idx
            for idx, row in df.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            idx, data = future.result()
            awards_results[idx] = data
            done += 1
            if done % 25 == 0:
                print(f"  Awards: {done}/{len(df)}...")

    df["press_mentions"] = df.index.map(lambda i: press_results.get(i, {}).get("press_mentions", 0))
    df["press_sources"] = df.index.map(lambda i: press_results.get(i, {}).get("press_sources", ""))
    df["awards_count"] = df.index.map(lambda i: awards_results.get(i, {}).get("awards_count", 0))
    df["awards_list"] = df.index.map(lambda i: awards_results.get(i, {}).get("awards_list", ""))

    has_press = (df["press_mentions"] > 0).sum()
    has_awards = (df["awards_count"] > 0).sum()
    print(f"\n  Leads with press mentions: {has_press}")
    print(f"  Leads with awards: {has_awards}")

    return df


# ─── Google Reviews & Reservation Sentiment ──────────────────────────

def analyze_reservation_difficulty_from_reviews(reviews: list[dict]) -> tuple[float, list[str]]:
    """Analyze review texts for reservation difficulty mentions.

    Handles both Serper format (snippet field) and Apify format (text field).
    Returns (score 0-1, sample of matching review texts).
    """
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
    score = min(1.0, mention_ratio * 5)  # 20%+ mention rate = 1.0
    return round(score, 3), samples


def _fetch_serper_reviews(cid: str) -> list[dict]:
    """Fetch reviews for a single place via Serper Reviews API."""
    from config import SERPER_API_KEY
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
    """Enrich leads with Google Reviews data and reservation sentiment via Serper."""
    print(f"\n{'='*60}")
    print(f"PHASE 2e: FETCHING GOOGLE REVIEWS (Serper)")
    print(f"{'='*60}")

    # Only process rows with a CID (Google Maps identifier)
    mask = df["cid"].astype(str).str.strip().ne("")
    cid_indices = df.loc[mask].index.tolist()

    if not cid_indices:
        print("  No CIDs found — skipping Google Reviews enrichment")
        df["review_difficulty_sentiment"] = 0.0
        df["review_texts_sample"] = ""
        return df

    print(f"  Found {len(cid_indices)} places with CIDs")
    print(f"  Fetching ~10 reviews each via Serper Reviews API...")

    all_reviews = {}  # cid_str -> list of review dicts

    def fetch_reviews(idx):
        cid_val = str(df.at[idx, "cid"])
        reviews = _fetch_serper_reviews(cid_val)
        return idx, cid_val, reviews

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_reviews, idx): idx for idx in cid_indices}
        done = 0
        for future in as_completed(futures):
            idx, cid_val, reviews = future.result()
            if reviews:
                all_reviews[cid_val] = reviews
            done += 1
            if done % 100 == 0:
                print(f"  Fetched reviews for {done}/{len(cid_indices)} places ({len(all_reviews)} with data)...")

    print(f"  Fetched reviews for {done}/{len(cid_indices)} places total ({len(all_reviews)} with data)")

    # Analyze sentiment and merge
    sentiments = {}
    samples = {}
    for cid_val, reviews in all_reviews.items():
        score, sample_texts = analyze_reservation_difficulty_from_reviews(reviews)
        sentiments[cid_val] = score
        samples[cid_val] = " | ".join(sample_texts) if sample_texts else ""

    df["review_difficulty_sentiment"] = df["cid"].astype(str).map(
        lambda c: sentiments.get(c, 0.0)
    )
    df["review_texts_sample"] = df["cid"].astype(str).map(
        lambda c: samples.get(c, "")
    )

    has_sentiment = (df["review_difficulty_sentiment"] > 0).sum()
    print(f"\n  Places with reservation difficulty mentions in reviews: {has_sentiment}")

    return df


# ─── Instagram Reels (avg_video_views) ───────────────────────────────

def enrich_instagram_reels(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with actual avg_video_views from Instagram Reels."""
    print(f"\n{'='*60}")
    print(f"PHASE 2f: SCRAPING INSTAGRAM REELS")
    print(f"{'='*60}")

    mask = df["ig_username"].astype(str).str.strip().ne("")
    usernames = df.loc[mask, "ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles — skipping Reels enrichment")
        return df

    print(f"  Found {len(usernames)} profiles to scrape Reels for")

    client = ApifyClient(APIFY_API_TOKEN)
    all_views = {}  # username -> avg views

    batch_size = 30
    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(usernames) - 1) // batch_size + 1
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} profiles)")

        run_input = {
            "username": batch,
            "resultsLimit": 12,
        }

        try:
            run = client.actor(APIFY_ACTOR_IG_REELS).call(run_input=run_input)
            items = client.dataset(run["defaultDatasetId"]).list_items().items

            # Group reels by username
            reels_by_user = {}
            for item in items:
                owner = (item.get("ownerUsername") or "").lower()
                views = item.get("videoViewCount") or item.get("playCount") or 0
                if owner and views > 0:
                    reels_by_user.setdefault(owner, []).append(views)

            for user, views_list in reels_by_user.items():
                if views_list:
                    all_views[user] = sum(views_list) / len(views_list)

            print(f"  Got Reels data for {len(all_views)} profiles so far")
        except Exception as e:
            print(f"  [ERROR] Instagram Reels batch failed: {e}")

        if i + batch_size < len(usernames):
            time.sleep(3)

    # Overwrite avg_video_views with actual computed average where available
    existing = df["avg_video_views"] if "avg_video_views" in df.columns else 0
    df["avg_video_views"] = df["ig_username"].apply(
        lambda u: all_views.get(u.lower(), 0) if u else 0
    )
    # Keep existing values for profiles where the scraper didn't return data
    if isinstance(existing, pd.Series):
        no_new_data = (df["avg_video_views"] == 0) & (existing > 0)
        df.loc[no_new_data, "avg_video_views"] = existing[no_new_data]

    has_views = (df["avg_video_views"] > 0).sum()
    print(f"\n  Profiles with Reels view data: {has_views}")

    return df


# ─── Instagram Posts (avg_likes) ─────────────────────────────────────

def enrich_instagram_posts(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich leads with actual avg_likes from Instagram Posts."""
    print(f"\n{'='*60}")
    print(f"PHASE 2g: SCRAPING INSTAGRAM POSTS")
    print(f"{'='*60}")

    mask = df["ig_username"].astype(str).str.strip().ne("")
    usernames = df.loc[mask, "ig_username"].tolist()

    if not usernames:
        print("  No Instagram profiles — skipping Posts enrichment")
        return df

    print(f"  Found {len(usernames)} profiles to scrape Posts for")

    client = ApifyClient(APIFY_API_TOKEN)
    all_likes = {}  # username -> avg likes

    batch_size = 30
    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(usernames) - 1) // batch_size + 1
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} profiles)")

        run_input = {
            "username": batch,
            "resultsLimit": 12,
        }

        try:
            run = client.actor(APIFY_ACTOR_IG_POSTS).call(run_input=run_input)
            items = client.dataset(run["defaultDatasetId"]).list_items().items

            # Group posts by username
            posts_by_user = {}
            for item in items:
                owner = (item.get("ownerUsername") or "").lower()
                likes = item.get("likesCount", -1)
                if owner and likes >= 0:  # Exclude hidden likes (-1)
                    posts_by_user.setdefault(owner, []).append(likes)

            for user, likes_list in posts_by_user.items():
                if likes_list:
                    all_likes[user] = sum(likes_list) / len(likes_list)

            print(f"  Got Posts data for {len(all_likes)} profiles so far")
        except Exception as e:
            print(f"  [ERROR] Instagram Posts batch failed: {e}")

        if i + batch_size < len(usernames):
            time.sleep(3)

    # Overwrite avg_likes with actual computed average where available
    existing = df["avg_likes"] if "avg_likes" in df.columns else 0
    df["avg_likes"] = df["ig_username"].apply(
        lambda u: all_likes.get(u.lower(), 0) if u else 0
    )
    # Keep existing values for profiles where the scraper didn't return data
    if isinstance(existing, pd.Series):
        no_new_data = (df["avg_likes"] == 0) & (existing > 0)
        df.loc[no_new_data, "avg_likes"] = existing[no_new_data]

    has_likes = (df["avg_likes"] > 0).sum()
    print(f"\n  Profiles with Post like data: {has_likes}")

    return df


# ─── Booking Availability (OpenTable / Resy) ─────────────────────────

def enrich_booking_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Check actual booking availability for restaurants with reservation platforms."""
    print(f"\n{'='*60}")
    print(f"PHASE 2h: CHECKING BOOKING AVAILABILITY")
    print(f"{'='*60}")

    # Only check restaurants that have a reservation platform detected
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
            batch_size = 20
            for i in range(0, len(ot_urls), batch_size):
                batch_urls = ot_urls[i:i + batch_size]
                batch_indices = ot_indices[i:i + batch_size]

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

                        # Match back to index by URL
                        for j, url in enumerate(batch_urls):
                            if source_url and url.rstrip("/") in source_url:
                                idx = batch_indices[j]
                                availability_scores.setdefault(idx, []).append(slot_count)
                                break

                except Exception as e:
                    print(f"  [ERROR] OpenTable scrape failed: {e}")

                if i + batch_size < len(ot_urls):
                    time.sleep(3)

    # --- Resy (reservation_difficulty == 2) ---
    resy_mask = candidates["reservation_difficulty"].astype(int) == 2
    resy_rows = candidates.loc[resy_mask]

    if not resy_rows.empty and RESY_API_KEY:
        print(f"\n  Checking Resy availability for {len(resy_rows)} restaurants...")

        for idx, row in resy_rows.iterrows():
            resy_url = row.get("reservation_url", "")
            if not resy_url or "resy.com" not in resy_url.lower():
                continue

            # Extract venue slug from URL
            slug_match = re.search(r"resy\.com/cities/[^/]+/([^/?]+)", resy_url)
            if not slug_match:
                continue
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

            availability_scores[idx] = [total_slots / len(check_dates)] if total_slots else [0]
    elif not resy_rows.empty and not RESY_API_KEY:
        print(f"  Skipping Resy checks — RESY_API_KEY not set")

    # Tock (reservation_difficulty == 3) — no API, skip availability check

    # Compute normalized score: 0.0 = fully booked, 1.0 = wide open
    # Normalize based on max ~10 slots per date as "wide open"
    max_slots_per_date = 10.0

    def compute_availability(idx):
        if idx not in availability_scores:
            return 1.0  # Default for unchecked
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

    return df


if __name__ == "__main__":
    result = analyze_website("https://www.publicanqualitymeats.com")
    for k, v in result.items():
        print(f"  {k}: {v}")
