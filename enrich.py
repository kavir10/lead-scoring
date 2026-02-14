"""
Phase 2: Enrich leads with website analysis, social media data
"""
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import pandas as pd
from apify_client import ApifyClient
from config import APIFY_API_TOKEN


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
                "ecommerce_platform", "email_platform", "page_title"]:
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
    for col in ["ig_followers", "ig_posts", "ig_is_business"]:
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

    return df


if __name__ == "__main__":
    # Test with a known butcher shop
    result = analyze_website("https://www.publicanqualitymeats.com")
    for k, v in result.items():
        print(f"  {k}: {v}")
