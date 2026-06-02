"""
Augment fresh butcher outputs with Facebook profile URLs and follower counts.

This is intentionally separate from the original crawl so existing discovery
files are not overwritten. It reads the current butcher Clay/top file, finds
Facebook profile links from business websites, scrapes public follower counts
when available, computes `follower_count`, and writes date-stamped outputs.
"""
from __future__ import annotations

import argparse
import json
import re
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
DEFAULT_INPUT = RUN_DIR / "fresh_butcher_clay_input_top_5000.csv"

FACEBOOK_SKIP_RE = re.compile(
    r"/(?:sharer|share|plugins|dialog|events|groups|watch|reel|reels|stories|"
    r"marketplace|login|profile\.php\?id=$)",
    re.I,
)
FOLLOWER_PATTERNS = [
    re.compile(r'"follower_count"\s*:\s*(\d+)', re.I),
    re.compile(r'"followers_count"\s*:\s*(\d+)', re.I),
    re.compile(r'([\d,.]+)\s*(?:K|k|M|m)?\s+followers', re.I),
    re.compile(r'([\d,.]+)\s*(?:K|k|M|m)?\s+people follow this', re.I),
]


def clean_url(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.match(r"https?://", text, flags=re.I):
        text = "https://" + text
    return text


def normalize_facebook_url(value: object, base_url: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    url = urljoin(base_url, text) if base_url else text
    if "facebook.com/" not in url.lower() and "fb.com/" not in url.lower():
        return ""
    url = url.split("#")[0].split("?")[0].rstrip("/")
    if FACEBOOK_SKIP_RE.search(url):
        return ""
    parsed = urlparse(url if re.match(r"https?://", url, re.I) else "https://" + url)
    host = parsed.netloc.lower().replace("m.facebook.com", "www.facebook.com").replace("fb.com", "facebook.com")
    if host.startswith("facebook.com"):
        host = "www." + host
    path = parsed.path.rstrip("/")
    if not path or path == "/":
        return ""
    return f"https://{host}{path}"


def fetch(url: str, timeout: int = 14) -> tuple[int, str, str]:
    kwargs = {
        "timeout": timeout,
        "allow_redirects": True,
        "headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        },
    }
    try:
        resp = requests.get(url, impersonate="chrome120", **kwargs)
    except TypeError:
        resp = requests.get(url, **kwargs)
    return resp.status_code, resp.url, resp.text


def find_facebook_url(row: dict) -> dict:
    existing = normalize_facebook_url(row.get("facebook_url", ""))
    if existing:
        return {"facebook_url": existing, "facebook_source": "existing"}

    for key in ["website_final_url", "website"]:
        url = clean_url(row.get(key, ""))
        if not url:
            continue
        try:
            status, final_url, html = fetch(url)
        except Exception as exc:
            return {"facebook_url": "", "facebook_source": "", "facebook_error": type(exc).__name__}
        if status >= 400 or not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[str] = []
        for tag in soup.find_all("a", href=True):
            fb = normalize_facebook_url(tag["href"], final_url)
            if fb and fb not in candidates:
                candidates.append(fb)
        if candidates:
            return {"facebook_url": candidates[0], "facebook_source": key}

    return {"facebook_url": "", "facebook_source": ""}


def parse_count_token(raw: str, context: str) -> int:
    token = str(raw or "").replace(",", "").strip()
    if not token:
        return 0
    try:
        value = float(token)
    except ValueError:
        return 0
    lower = context.lower()
    if "m followers" in lower or "m people follow" in lower:
        value *= 1_000_000
    elif "k followers" in lower or "k people follow" in lower:
        value *= 1_000
    return int(value)


def scrape_facebook_followers(facebook_url: str) -> dict:
    result = {"fb_likes": 0, "fb_page_name": "", "facebook_status": "", "facebook_error": ""}
    url = normalize_facebook_url(facebook_url)
    if not url:
        return result
    try:
        status, final_url, html = fetch(url, timeout=12)
        result["facebook_status"] = str(status)
        result["facebook_final_url"] = final_url
        if status >= 400 or not html:
            return result

        for pattern in FOLLOWER_PATTERNS:
            match = pattern.search(html)
            if not match:
                continue
            if pattern.pattern.startswith('("follower') or "follower_count" in pattern.pattern:
                result["fb_likes"] = int(match.group(1))
            else:
                start = max(match.start() - 20, 0)
                end = min(match.end() + 40, len(html))
                result["fb_likes"] = parse_count_token(match.group(1), html[start:end])
            if result["fb_likes"]:
                break

        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
        if name_match:
            result["fb_page_name"] = name_match.group(1)
    except Exception as exc:
        result["facebook_error"] = type(exc).__name__
    return result


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int)


def write_checkpoint(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def augment(input_path: Path, output_path: Path, workers: int, checkpoint_every: int) -> pd.DataFrame:
    df = pd.read_csv(input_path, low_memory=False)
    for col, default in [
        ("facebook_url", ""),
        ("facebook_source", ""),
        ("fb_likes", 0),
        ("fb_page_name", ""),
        ("facebook_status", ""),
        ("facebook_final_url", ""),
        ("facebook_error", ""),
        ("follower_count", 0),
    ]:
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].astype(object)

    pending = df.index[
        df["facebook_url"].fillna("").astype(str).str.strip().eq("")
        | df["facebook_status"].fillna("").astype(str).str.strip().eq("")
    ].tolist()

    print(f"Augmenting {len(pending):,}/{len(df):,} rows with Facebook profiles/counts")
    started = time.monotonic()
    completed = 0

    def process(idx: int) -> tuple[int, dict]:
        row = df.loc[idx].to_dict()
        found = find_facebook_url(row)
        fb_url = found.get("facebook_url", "")
        counts = scrape_facebook_followers(fb_url) if fb_url else {}
        return idx, {**found, **counts}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process, idx): idx for idx in pending}
        for future in as_completed(futures):
            idx, data = future.result()
            for col, value in data.items():
                if col not in df.columns:
                    df[col] = ""
                df.at[idx, col] = value
            completed += 1
            if completed % 50 == 0 or completed == len(pending):
                elapsed = max(time.monotonic() - started, 1)
                fb_urls = df["facebook_url"].fillna("").astype(str).str.strip().ne("").sum()
                fb_counts = numeric(df["fb_likes"]).gt(0).sum()
                print(
                    f"  {completed:,}/{len(pending):,} | {completed / elapsed:.1f}/s | "
                    f"facebook URLs {fb_urls:,} | follower counts {fb_counts:,}",
                    flush=True,
                )
            if completed % checkpoint_every == 0:
                write_checkpoint(df, output_path)

    ig = numeric(df["ig_followers"]) if "ig_followers" in df.columns else pd.Series(0, index=df.index, dtype=int)
    fb = numeric(df["fb_likes"])
    df["follower_count"] = ig + fb
    write_checkpoint(df, output_path)
    return df


def write_outputs(df: pd.DataFrame, output_path: Path, custom_output_path: Path | None) -> dict:
    df = df.copy()

    if custom_output_path:
        custom_cols = [
            "name", "address", "city", "state", "phone", "website", "business_type",
            "lead_score", "tier",
            "follower_count", "review_count", "rating",
            "instagram_url", "ig_followers",
            "facebook_url", "fb_likes",
            "has_email_signup", "has_ecommerce",
        ]
        if "business_type" not in df.columns:
            df["business_type"] = "butcher"
        if "lead_score" not in df.columns and "butcher_seed_score" in df.columns:
            df["lead_score"] = df["butcher_seed_score"]
        if "tier" not in df.columns:
            df["tier"] = "Fresh Butcher Lead"
        if "has_ecommerce" not in df.columns and "has_ecommerce_signal" in df.columns:
            df["has_ecommerce"] = df["has_ecommerce_signal"]
        custom_cols = [col for col in custom_cols if col in df.columns]
        df[custom_cols].to_csv(custom_output_path, index=False)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(df)),
        "facebook_url": int(df["facebook_url"].fillna("").astype(str).str.strip().ne("").sum()),
        "fb_likes": int(numeric(df["fb_likes"]).gt(0).sum()),
        "follower_count": int(numeric(df["follower_count"]).gt(0).sum()),
        "median_fb_likes_for_counted": float(numeric(df.loc[numeric(df["fb_likes"]).gt(0), "fb_likes"]).median()) if numeric(df["fb_likes"]).gt(0).any() else 0,
        "files": {"augmented": str(output_path)},
    }
    if custom_output_path:
        summary["files"]["custom_serper_top"] = str(custom_output_path)
    summary_path = output_path.with_name(output_path.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment fresh butcher files with Facebook profile/follower data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=RUN_DIR / "fresh_butcher_facebook_augmented_20260601.csv")
    parser.add_argument(
        "--custom-output",
        type=Path,
        default=ROOT / "output" / "custom-serper-scoring_kavir_20260601_butcher_5000_top.csv",
    )
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df = augment(args.input, args.output, args.workers, args.checkpoint_every)
    write_outputs(df, args.output, args.custom_output)


if __name__ == "__main__":
    main()
