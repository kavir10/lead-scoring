"""
Crawl fresh butcher websites for subscription, email-list, ecommerce, and social signals.

Inputs:
  output/fresh_butcher_leads_20260531/fresh_butcher_new_candidates.csv

Outputs:
  output/fresh_butcher_leads_20260531/fresh_butcher_email_crawled.csv
  output/fresh_butcher_leads_20260531/fresh_butcher_final_all_ranked.csv
  output/fresh_butcher_leads_20260531/fresh_butcher_clay_input_top_5000.csv
"""
from __future__ import annotations

import argparse
import json
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests
except ImportError:  # pragma: no cover
    import requests  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "output" / "fresh_butcher_leads_20260531"

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
    "exclusive offers",
]

EMAIL_PROVIDERS = {
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

ECOMMERCE_TERMS = [
    "order online",
    "shop online",
    "shop now",
    "online ordering",
    "add to cart",
    "cart",
    "checkout",
    "shipping",
    "delivery",
    "pickup",
    "local pickup",
]
ECOMMERCE_PROVIDERS = {
    "cdn.shopify.com": "Shopify",
    "myshopify.com": "Shopify",
    "woocommerce": "WooCommerce",
    "bigcommerce": "BigCommerce",
    "squarespace": "Squarespace",
    "squareup.com": "Square",
    "toasttab.com": "Toast",
    "bentobox": "BentoBox",
    "lightspeed": "Lightspeed",
}

SUBSCRIPTION_PATTERNS = {
    "subscription": re.compile(
        r"\b(?:meat|beef|pork|lamb|poultry|chicken|farm|ranch|butcher)\s+subscription\b"
        r"|\bsubscription\s+(?:box|service|program|members?|plan)\b"
        r"|\brecurring (?:order|delivery|box|shipment)\b"
        r"|\bauto[- ]?ship\b",
        re.I,
    ),
    "meat_club": re.compile(r"\bmeat club\b|\bbutcher(?:'s)? club\b|\bfarm club\b|\bbeef club\b|\bpork club\b|\bsteak club\b", re.I),
    "meat_share_csa": re.compile(r"\bCSA\b|\bmeat share\b|\bbeef share\b|\bpork share\b|\bbuying club\b|\bherd share\b", re.I),
    "monthly_box": re.compile(r"\bmonthly box\b|\bmeat box\b|\bbox of (?:beef|meat|pork|lamb)\b|\bquarterly box\b|\bcurated box\b", re.I),
    "membership": re.compile(r"\b(?:meat|beef|farm|ranch|butcher)\s+members?(?:hip)?\b|\bbecome a member\b|\bmembers? only\b", re.I),
    "preorder": re.compile(r"\bpre[- ]?order\b|\bholiday order\b|\bthanksgiving turkey\b", re.I),
}

PREMIUM_PATTERNS = {
    "pasture_raised": re.compile(r"\bpasture[- ]raised\b|\bpastured\b", re.I),
    "heritage_breed": re.compile(r"\bheritage\b|\bberkshire\b|\bmangalitsa\b|\btamworth\b|\bduroc\b|\bwagyu\b", re.I),
    "dry_aged": re.compile(r"\bdry[- ]aged\b", re.I),
    "whole_animal": re.compile(r"\bwhole[- ]animal\b|\bnose[- ]to[- ]tail\b", re.I),
    "grass_fed": re.compile(r"\bgrass[- ]fed\b|\bgrass[- ]finished\b", re.I),
    "charcuterie": re.compile(r"\bcharcuterie\b|\bsalumi\b|\bsalami\b|\bprosciutto\b|\bsmoked\b", re.I),
}

FOLLOW_LINK_TERMS = (
    "newsletter",
    "subscribe",
    "signup",
    "sign-up",
    "shop",
    "store",
    "order",
    "membership",
    "club",
    "share",
    "box",
    "contact",
    "about",
)
SOCIAL_SKIP_RE = re.compile(r"/(?:p|reel|reels|stories|explore|accounts|share)/", re.I)
USERNAME_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")
SKIP_USERNAMES = {"p", "reel", "reels", "stories", "explore", "accounts", "share"}
BANNED_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}
STRICT_BUTCHER_TYPE_RE = re.compile(
    r"\b(?:butcher shop|meat products store|meat market|meat processor|"
    r"poultry store|meat wholesaler)\b",
    re.I,
)
STRICT_BUTCHER_NAME_RE = re.compile(
    r"\b(?:butcher|butchery|meat market|meat shop|meats|carniceria|"
    r"carnicería|sausage|smokehouse|smoked meats|salumi|salumeria|"
    r"halal meat|kosher meat|prime meats|poultry|game meat)\b",
    re.I,
)
RESTAURANT_TYPE_RE = re.compile(
    r"\b(?:restaurant|wine bar|bar|grill|steakhouse|cafe|coffee shop|"
    r"creperie|brewery|distillery)\b",
    re.I,
)

_print_lock = threading.Lock()


def clean_url(url: object) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if not re.match(r"https?://", text, flags=re.I):
        text = "https://" + text
    return text


def same_host(a: str, b: str) -> bool:
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb


def visible_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def first_instagram_url(soup: BeautifulSoup) -> str:
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if "instagram.com/" not in href.lower():
            continue
        if SOCIAL_SKIP_RE.search(href):
            continue
        return href.split("?")[0].rstrip("/")
    return ""


def extract_username(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = USERNAME_RE.search(text)
    if not match:
        return ""
    username = match.group(1).strip(".").lower()
    return "" if username in SKIP_USERNAMES else username


def detect_email_signup(html: str, soup: BeautifulSoup, page_url: str) -> dict:
    html_l = html.lower()
    terms = [term for term in EMAIL_TERMS if term in html_l]
    providers = sorted({label for key, label in EMAIL_PROVIDERS.items() if key in html_l})
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
            if form.get("action") and not form_action:
                form_action = urljoin(page_url, form.get("action"))

    confidence = 0
    if providers:
        confidence += 3
    if email_inputs:
        confidence += 2
    if terms:
        confidence += 1
    if form_score >= 2:
        confidence += 2

    return {
        "has_email_signup": confidence >= 3 or (bool(email_inputs) and bool(terms)),
        "email_signup_confidence": min(confidence, 6),
        "email_platform": "; ".join(providers),
        "email_signal_terms": "; ".join(terms[:8]),
        "email_form_action": form_action,
    }


def detect_butcher_commerce(html: str) -> dict:
    html_l = html.lower()
    text = visible_text(html)
    ecommerce_terms = [term for term in ECOMMERCE_TERMS if term in html_l]
    ecommerce_providers = sorted({label for key, label in ECOMMERCE_PROVIDERS.items() if key in html_l})
    subscription_hits = [name for name, pattern in SUBSCRIPTION_PATTERNS.items() if pattern.search(text)]
    premium_hits = [name for name, pattern in PREMIUM_PATTERNS.items() if pattern.search(text)]
    return {
        "has_ecommerce_signal": bool(ecommerce_terms or ecommerce_providers),
        "ecommerce_platform": "; ".join(ecommerce_providers),
        "ecommerce_signal_terms": "; ".join(ecommerce_terms[:8]),
        "has_subscription_signal": bool(subscription_hits),
        "subscription_signals": "; ".join(subscription_hits),
        "premium_signals": "; ".join(premium_hits),
        "premium_signal_count": len(premium_hits),
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
    return links[:5]


def fetch(url: str) -> tuple[int, str, str]:
    kwargs = {
        "timeout": 14,
        "allow_redirects": True,
        "headers": {"Accept-Language": "en-US,en;q=0.9"},
    }
    try:
        resp = requests.get(url, impersonate="chrome120", **kwargs)
    except TypeError:
        resp = requests.get(url, **kwargs)
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
        "ig_username": "",
        "has_ecommerce_signal": False,
        "ecommerce_platform": "",
        "ecommerce_signal_terms": "",
        "has_subscription_signal": False,
        "subscription_signals": "",
        "premium_signals": "",
        "premium_signal_count": 0,
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
        result["instagram_url"] = first_instagram_url(soup)
        result["ig_username"] = extract_username(result["instagram_url"])
        result.update(detect_email_signup(html, soup, final_url))
        result.update(detect_butcher_commerce(html))

        if result["has_email_signup"] and result["has_subscription_signal"] and result["has_ecommerce_signal"]:
            result["newsletter_url"] = final_url
            return result

        for follow_url in candidate_follow_links(soup, final_url):
            try:
                status2, final2, html2 = fetch(follow_url)
                if status2 >= 400 or not html2:
                    continue
                soup2 = BeautifulSoup(html2, "html.parser")
                if not result["instagram_url"]:
                    result["instagram_url"] = first_instagram_url(soup2)
                    result["ig_username"] = extract_username(result["instagram_url"])

                email2 = detect_email_signup(html2, soup2, final2)
                commerce2 = detect_butcher_commerce(html2)
                if email2["email_signup_confidence"] > result["email_signup_confidence"]:
                    result.update(email2)
                    result["newsletter_url"] = final2 if email2["has_email_signup"] else result["newsletter_url"]
                for key in [
                    "has_ecommerce_signal",
                    "ecommerce_platform",
                    "ecommerce_signal_terms",
                    "has_subscription_signal",
                    "subscription_signals",
                    "premium_signals",
                    "premium_signal_count",
                ]:
                    if commerce2.get(key) and not result.get(key):
                        result[key] = commerce2[key]
                if result["has_email_signup"] and result["has_subscription_signal"] and result["has_ecommerce_signal"]:
                    break
            except Exception:
                continue
    except Exception as exc:
        result["crawl_error"] = type(exc).__name__

    return result


def bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(False, index=df.index)
    return df[col].fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y"})


def present_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(False, index=df.index)
    return df[col].fillna("").astype(str).str.strip().ne("")


def numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(0, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def butcher_seed_score(df: pd.DataFrame) -> pd.Series:
    rating = numeric_series(df, "rating")
    reviews = numeric_series(df, "review_count")
    type_bonus = df.get("verification_reason", "").map(
        {
            "keep_strong_google_type": 28,
            "keep_adjacent_type_plus_name": 22,
            "keep_strong_name_signal": 18,
            "keep_butcher_text_signal": 14,
        }
    ).fillna(0)
    email_bonus = bool_series(df, "has_email_signup").astype(int) * 10
    ig_bonus = present_series(df, "instagram_url").astype(int) * 8
    ecommerce_bonus = bool_series(df, "has_ecommerce_signal").astype(int) * 8
    subscription_bonus = bool_series(df, "has_subscription_signal").astype(int) * 14
    premium_bonus = numeric_series(df, "premium_signal_count").clip(0, 4) * 3
    reachable_bonus = bool_series(df, "website_reachable").astype(int) * 5
    review_score = reviews.apply(lambda x: min(24, math.log10(x + 1) * 6 if x > 0 else 0))
    return (
        type_bonus
        + email_bonus
        + ig_bonus
        + ecommerce_bonus
        + subscription_bonus
        + premium_bonus
        + reachable_bonus
        + rating.clip(0, 5) * 6
        + review_score
    ).round(2)


def likely_butcher_mask(df: pd.DataFrame) -> pd.Series:
    """Final precision gate for Clay exports.

    Discovery intentionally catches adjacent meat/charcuterie rows. Before
    export, require a valid US state plus a stricter butcher/meat signal, and
    drop restaurant/bar-only rows unless the name/type still clearly says meat.
    """
    state = df.get("state", "").fillna("").astype(str).str.upper().str.strip()
    type_text = df.get("google_type", "").fillna("").astype(str) + " " + df.get("google_types", "").fillna("").astype(str)
    name = df.get("name", "").fillna("").astype(str)

    valid_state = state.str.match(r"^[A-Z]{2}$") & ~state.isin(BANNED_STATES)
    strict_butcher = type_text.str.contains(STRICT_BUTCHER_TYPE_RE) | name.str.contains(STRICT_BUTCHER_NAME_RE)
    restaurant_only = type_text.str.contains(RESTAURANT_TYPE_RE) & ~strict_butcher
    return valid_state & strict_butcher & ~restaurant_only


def write_checkpoint(df: pd.DataFrame, output_path: Path) -> None:
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(output_path)


def finalize_outputs(df: pd.DataFrame, run_dir: Path) -> dict:
    input_rows = int(len(df))
    df = df[likely_butcher_mask(df)].copy()
    df["butcher_seed_score"] = butcher_seed_score(df)
    df = df.sort_values(
        [
            "butcher_seed_score",
            "has_subscription_signal",
            "has_ecommerce_signal",
            "has_email_signup",
            "instagram_url",
            "review_count",
            "rating",
        ],
        ascending=[False, False, False, False, False, False, False],
    ).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    all_cols = [
        "rank",
        "name",
        "address",
        "city",
        "state",
        "phone",
        "website",
        "website_reachable",
        "website_final_url",
        "google_type",
        "google_types",
        "verification_reason",
        "butcher_seed_score",
        "fresh_quality_score",
        "rating",
        "review_count",
        "has_subscription_signal",
        "subscription_signals",
        "has_ecommerce_signal",
        "ecommerce_platform",
        "ecommerce_signal_terms",
        "has_email_signup",
        "email_signup_confidence",
        "email_platform",
        "email_signal_terms",
        "newsletter_url",
        "instagram_url",
        "ig_username",
        "premium_signals",
        "premium_signal_count",
        "cid",
        "latitude",
        "longitude",
        "search_query",
        "search_city",
        "page_title",
        "crawl_error",
        "prior_suppression_reason",
    ]
    all_cols = [col for col in all_cols if col in df.columns]

    all_ranked = run_dir / "fresh_butcher_final_all_ranked.csv"
    df[all_cols].to_csv(all_ranked, index=False)

    clay_cols = all_cols.copy()
    for limit in [4000, 5000, 6000, len(df)]:
        if limit <= 0:
            continue
        out = df.head(limit).copy()
        out = out.rename(columns={"rank": "clay_rank"})
        out_cols = ["clay_rank" if col == "rank" else col for col in clay_cols]
        suffix = str(limit)
        out[out_cols].to_csv(run_dir / f"fresh_butcher_clay_input_top_{suffix}.csv", index=False)

    cutoffs = []
    for limit in [2000, 4000, 5000, 6000, len(df)]:
        subset = df.head(limit)
        if subset.empty:
            continue
        cutoffs.append(
            {
                "rows": int(len(subset)),
                "reachable": int(bool_series(subset, "website_reachable").sum()),
                "subscription_signal": int(bool_series(subset, "has_subscription_signal").sum()),
                "ecommerce_signal": int(bool_series(subset, "has_ecommerce_signal").sum()),
                "email_signup": int(bool_series(subset, "has_email_signup").sum()),
                "instagram_url": int(present_series(subset, "instagram_url").sum()),
                "email_and_instagram": int((bool_series(subset, "has_email_signup") & present_series(subset, "instagram_url")).sum()),
                "median_reviews": float(numeric_series(subset, "review_count").median()),
                "median_rating": float(numeric_series(subset, "rating").median()),
                "median_seed_score": float(numeric_series(subset, "butcher_seed_score").median()),
            }
        )

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_rows": input_rows,
        "precision_filtered_rows": int(input_rows - len(df)),
        "source_rows": int(len(df)),
        "goal_rows": 5000,
        "top_5000_available": int(min(5000, len(df))),
        "cutoffs": cutoffs,
        "files": {
            "all_ranked": str(all_ranked),
            "top_5000": str(run_dir / "fresh_butcher_clay_input_top_5000.csv"),
        },
    }
    summary_path = run_dir / "fresh_butcher_clay_input_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl butcher websites and build Clay input files.")
    parser.add_argument("--input", type=Path, default=RUN_DIR / "fresh_butcher_new_candidates.csv")
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_butcher_email_crawled.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    args = parser.parse_args()

    df = pd.read_csv(args.input, low_memory=False)
    if args.limit:
        df = df.head(args.limit).copy()
    df = df.reset_index(drop=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    crawl_cols = [
        "website_reachable",
        "website_status",
        "website_final_url",
        "page_title",
        "has_email_signup",
        "email_signup_confidence",
        "email_platform",
        "email_signal_terms",
        "email_form_action",
        "newsletter_url",
        "instagram_url",
        "ig_username",
        "has_ecommerce_signal",
        "ecommerce_platform",
        "ecommerce_signal_terms",
        "has_subscription_signal",
        "subscription_signals",
        "premium_signals",
        "premium_signal_count",
        "crawl_error",
    ]
    for col in crawl_cols:
        if col not in df.columns:
            df[col] = False if col in {"website_reachable", "has_email_signup", "has_ecommerce_signal", "has_subscription_signal"} else ""
        df[col] = df[col].astype(object)

    already_done = df["website_status"].fillna("").astype(str).str.strip().ne("") | df["crawl_error"].fillna("").astype(str).str.strip().ne("")
    todo_indices = df.index[~already_done].tolist()

    print(f"Crawling {len(todo_indices):,}/{len(df):,} butcher websites with {args.workers} workers")
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
                        f"subscriptions {bool_series(df, 'has_subscription_signal').sum():,} | "
                        f"ecomm {bool_series(df, 'has_ecommerce_signal').sum():,} | "
                        f"email {bool_series(df, 'has_email_signup').sum():,} | "
                        f"IG URLs {present_series(df, 'instagram_url').sum():,}",
                        flush=True,
                    )
            if completed % args.checkpoint_every == 0:
                write_checkpoint(df, args.output)

    write_checkpoint(df, args.output)
    summary = finalize_outputs(df, args.output.parent)

    text_summary = [
        "Fresh butcher crawl summary",
        f"Rows crawled/listed: {len(df):,}",
        f"Reachable websites: {bool_series(df, 'website_reachable').sum():,}",
        f"Subscription signal: {bool_series(df, 'has_subscription_signal').sum():,}",
        f"Ecommerce signal: {bool_series(df, 'has_ecommerce_signal').sum():,}",
        f"Email signup present: {bool_series(df, 'has_email_signup').sum():,}",
        f"Instagram URLs found: {present_series(df, 'instagram_url').sum():,}",
        "",
        f"Full crawled file: {args.output}",
        f"Top 5000 Clay file: {summary['files']['top_5000']}",
    ]
    summary_txt = args.output.parent / "fresh_butcher_email_crawl_summary.txt"
    summary_txt.write_text("\n".join(text_summary) + "\n")
    print("\n".join(text_summary))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
