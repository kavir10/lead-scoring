"""
Crawl fresh bakery websites for email-list and social presence.

Inputs:
  output/fresh_bakery_leads_20260525/fresh_bakery_independent_candidates.csv

Outputs:
  output/fresh_bakery_leads_20260525/fresh_bakery_email_crawled.csv
  output/fresh_bakery_leads_20260525/fresh_bakery_email_crawl_summary.txt
  output/fresh_bakery_leads_20260525/fresh_bakery_final_discovery_list.csv
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "output" / "fresh_bakery_leads_20260525"

EMAIL_TERMS = [
    "newsletter",
    "email list",
    "mailing list",
    "join our list",
    "join the list",
    "sign up",
    "signup",
    "subscribe",
    "get updates",
    "stay updated",
    "be the first to know",
    "exclusive offers",
    "smsbump",
]

PROVIDERS = {
    "klaviyo": "Klaviyo",
    "mailchimp": "Mailchimp",
    "list-manage.com": "Mailchimp",
    "constantcontact": "Constant Contact",
    "constant contact": "Constant Contact",
    "mailerlite": "MailerLite",
    "convertkit": "ConvertKit",
    "omnisend": "Omnisend",
    "privy": "Privy",
    "attentive": "Attentive",
    "postscript": "Postscript",
    "hubspot": "HubSpot",
    "sendinblue": "Brevo",
    "brevo": "Brevo",
    "yotpo": "Yotpo",
}

FOLLOW_LINK_TERMS = ("newsletter", "subscribe", "signup", "sign-up", "contact", "about")
SOCIAL_SKIP_RE = re.compile(r"/(?:p|reel|reels|stories|explore|accounts|share)/", re.I)

_print_lock = threading.Lock()


def clean_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    if not re.match(r"https?://", url, flags=re.I):
        url = "https://" + url
    return url


def same_host(a: str, b: str) -> bool:
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb


def first_instagram_url(soup: BeautifulSoup, base_url: str) -> str:
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if "instagram.com/" not in href.lower():
            continue
        if SOCIAL_SKIP_RE.search(href):
            continue
        return href.split("?")[0].rstrip("/")
    return ""


def detect_email_signup(html: str, soup: BeautifulSoup, page_url: str) -> dict:
    html_l = html.lower()
    terms = [term for term in EMAIL_TERMS if term in html_l]
    providers = sorted({label for key, label in PROVIDERS.items() if key in html_l})

    email_inputs = soup.select("input[type='email'], input[name*='email' i], input[placeholder*='email' i]")
    form_score = 0
    form_action = ""
    for form in soup.find_all("form"):
        form_text = form.get_text(" ", strip=True).lower()
        form_html = str(form).lower()
        if "email" in form_html:
            form_score += 1
            if any(term in form_text or term in form_html for term in EMAIL_TERMS):
                form_score += 2
            action = form.get("action") or ""
            if action and not form_action:
                form_action = urljoin(page_url, action)

    confidence = 0
    if providers:
        confidence += 3
    if email_inputs:
        confidence += 2
    if terms:
        confidence += 1
    if form_score >= 2:
        confidence += 2

    has_signup = confidence >= 3 or (bool(email_inputs) and bool(terms))

    return {
        "has_email_signup": has_signup,
        "email_signup_confidence": min(confidence, 6),
        "email_platform": "; ".join(providers),
        "email_signal_terms": "; ".join(terms[:8]),
        "email_form_action": form_action,
    }


def candidate_follow_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        text = tag.get_text(" ", strip=True).lower()
        href_l = href.lower()
        if not href or href.startswith(("mailto:", "tel:", "#")):
            continue
        full = urljoin(base_url, href)
        if not same_host(base_url, full):
            continue
        if any(term in href_l or term in text for term in FOLLOW_LINK_TERMS):
            if full not in links:
                links.append(full)
    return links[:3]


def fetch(url: str) -> tuple[int, str, str]:
    resp = requests.get(
        url,
        impersonate="chrome120",
        timeout=14,
        allow_redirects=True,
        headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    return resp.status_code, resp.url, resp.text


def crawl_one(row: dict) -> dict:
    original_url = clean_url(row.get("website", ""))
    result = {
        "website_reachable": False,
        "website_status": "",
        "website_final_url": "",
        "page_title": "",
        "has_email_signup": False,
        "email_signup_confidence": 0,
        "email_platform": "",
        "email_signal_terms": "",
        "email_form_action": "",
        "newsletter_url": "",
        "instagram_url": "",
        "crawl_error": "",
    }
    if not original_url:
        result["crawl_error"] = "missing_website"
        return result

    try:
        status, final_url, html = fetch(original_url)
        result["website_status"] = str(status)
        result["website_final_url"] = final_url
        if status >= 400 or not html:
            result["crawl_error"] = f"http_{status}"
            return result
        result["website_reachable"] = True

        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            result["page_title"] = re.sub(r"\s+", " ", soup.title.string).strip()
        result["instagram_url"] = first_instagram_url(soup, final_url)

        signal = detect_email_signup(html, soup, final_url)
        result.update(signal)
        if result["has_email_signup"]:
            result["newsletter_url"] = final_url
            return result

        for follow_url in candidate_follow_links(soup, final_url):
            try:
                status2, final2, html2 = fetch(follow_url)
                if status2 >= 400 or not html2:
                    continue
                soup2 = BeautifulSoup(html2, "html.parser")
                if not result["instagram_url"]:
                    result["instagram_url"] = first_instagram_url(soup2, final2)
                signal2 = detect_email_signup(html2, soup2, final2)
                if signal2["email_signup_confidence"] > result["email_signup_confidence"]:
                    result.update(signal2)
                    result["newsletter_url"] = final2 if signal2["has_email_signup"] else ""
                if result["has_email_signup"]:
                    break
            except Exception:
                continue
    except Exception as exc:
        result["crawl_error"] = type(exc).__name__

    return result


def priority_score(df: pd.DataFrame) -> pd.Series:
    rating = pd.to_numeric(df.get("rating", 0), errors="coerce").fillna(0)
    reviews = pd.to_numeric(df.get("review_count", 0), errors="coerce").fillna(0)
    type_bonus = df.get("verification_reason", "").map(
        {
            "keep_strong_google_type": 28,
            "keep_adjacent_type_plus_name": 20,
            "keep_strong_name_signal": 16,
        }
    ).fillna(0)
    email_bonus = df.get("has_email_signup", False).fillna(False).astype(bool).astype(int) * 14
    ig_bonus = df.get("instagram_url", "").fillna("").astype(str).str.strip().ne("").astype(int) * 6
    website_bonus = df.get("website_reachable", False).fillna(False).astype(bool).astype(int) * 5
    review_score = reviews.apply(lambda x: min(24, math.log10(x + 1) * 6 if x > 0 else 0))
    return (type_bonus + email_bonus + ig_bonus + website_bonus + rating.clip(0, 5) * 6 + review_score).round(2)


def write_checkpoint(df: pd.DataFrame, output_path: Path) -> None:
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl bakery websites for email-list presence.")
    parser.add_argument("--input", type=Path, default=RUN_DIR / "fresh_bakery_independent_candidates.csv")
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_bakery_email_crawled.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if args.limit:
        df = df.head(args.limit).copy()
    df = df.reset_index(drop=True)

    crawl_cols = [
        "website_reachable", "website_status", "website_final_url", "page_title",
        "has_email_signup", "email_signup_confidence", "email_platform",
        "email_signal_terms", "email_form_action", "newsletter_url",
        "instagram_url", "crawl_error",
    ]
    for col in crawl_cols:
        if col not in df.columns:
            df[col] = False if col in {"website_reachable", "has_email_signup"} else ""
        df[col] = df[col].astype(object)

    already_done = df["website_status"].fillna("").astype(str).str.strip().ne("") | df["crawl_error"].fillna("").astype(str).str.strip().ne("")
    todo_indices = df.index[~already_done].tolist()

    print(f"Crawling {len(todo_indices):,}/{len(df):,} bakery websites with {args.workers} workers")
    started = time.monotonic()
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(crawl_one, df.loc[i].to_dict()): i for i in todo_indices}
        for future in as_completed(futures):
            i = futures[future]
            result = future.result()
            for col, value in result.items():
                df.at[i, col] = value
            completed += 1
            if completed % 50 == 0 or completed == len(todo_indices):
                elapsed = max(time.monotonic() - started, 1)
                with _print_lock:
                    print(
                        f"  {completed:,}/{len(todo_indices):,} | "
                        f"{completed / elapsed:.1f}/s | "
                        f"email signups {df['has_email_signup'].astype(bool).sum():,} | "
                        f"IG URLs {df['instagram_url'].fillna('').astype(str).str.strip().ne('').sum():,}",
                        flush=True,
                    )
            if completed % args.checkpoint_every == 0:
                write_checkpoint(df, args.output)

    df["discovery_email_priority_score"] = priority_score(df)
    df = df.sort_values(
        ["discovery_email_priority_score", "has_email_signup", "instagram_url", "review_count", "rating"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    df.insert(0, "final_rank", range(1, len(df) + 1))
    write_checkpoint(df, args.output)

    final_cols = [
        "final_rank", "name", "address", "city", "state", "phone", "website",
        "website_reachable", "website_final_url", "has_email_signup",
        "email_signup_confidence", "email_platform", "email_signal_terms",
        "newsletter_url", "instagram_url", "discovery_email_priority_score",
        "fresh_quality_score", "rating", "review_count", "google_type",
        "google_types", "verification_reason", "cid", "latitude", "longitude",
        "search_query", "search_city", "page_title", "crawl_error",
    ]
    final_cols = [col for col in final_cols if col in df.columns]
    final_path = args.output.parent / "fresh_bakery_final_discovery_list.csv"
    df[final_cols].to_csv(final_path, index=False)

    summary = [
        "Fresh bakery email crawl summary",
        f"Rows crawled/listed: {len(df):,}",
        f"Reachable websites: {df['website_reachable'].astype(bool).sum():,}",
        f"Email signup present: {df['has_email_signup'].astype(bool).sum():,}",
        f"Instagram URLs found: {df['instagram_url'].fillna('').astype(str).str.strip().ne('').sum():,}",
        "",
        "Top email platforms:",
        df["email_platform"].replace("", "(unknown/text/form signal)").value_counts().head(15).to_string(),
        "",
        f"Full crawled file: {args.output}",
        f"Final list: {final_path}",
    ]
    summary_path = args.output.parent / "fresh_bakery_email_crawl_summary.txt"
    summary_path.write_text("\n".join(summary) + "\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
