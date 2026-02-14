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
from config import APIFY_API_TOKEN, RESERVATION_PLATFORMS


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

        # Check for reservation platforms
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            for platform, difficulty in RESERVATION_PLATFORMS.items():
                if platform in href:
                    result["reservation_difficulty"] = max(
                        result["reservation_difficulty"], difficulty
                    )

        # Domain age via python-whois
        try:
            import whois
            domain = urlparse(url).netloc.replace("www.", "")
            w = whois.whois(domain)
            if w.creation_date:
                created = w.creation_date
                if isinstance(created, list):
                    created = created[0]
                age_years = (datetime.now() - created).days / 365.25
                result["domain_age"] = round(age_years, 1)
        except Exception:
            pass

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
                "reservation_difficulty", "domain_age"]:
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


if __name__ == "__main__":
    result = analyze_website("https://www.publicanqualitymeats.com")
    for k, v in result.items():
        print(f"  {k}: {v}")
