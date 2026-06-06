"""
Build a focused wine-store lead list from existing lead corpora.

This is intentionally a no-new-API workflow. It uses the wine ICP in
docs/ICP.md to prioritize wine-focused retail shops and suppress wine bars,
wineries, liquor-store-like rows, chains, and weak public-data matches.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CHAIN_KEYWORDS  # noqa: E402


DEFAULT_SOURCES = [
    ROOT / "output" / (
        "custom-serper-scoring_kavir_20260402_"
        "bakery-butcher-cheese-shop-deli-fish-market-specialty-grocer-wine-bar-wine-store_"
        "73915_all_clubs_v2.reclassified_20260422.csv"
    ),
    ROOT / "output" / "fresh_icp_search_tiered_abcd_7761_20260601_033726.csv",
    ROOT / "output" / "wine_directories_cleaned_20260515_dedup.csv",
    ROOT / "output" / "best_wine_shops" / "best_wine_shops_20260525_dedup.csv",
]
DEFAULT_RUN_DIR = ROOT / "output" / "fresh_wine_leads_20260602"

HARD_CHAIN_RE = re.compile(
    r"\b(?:total wine|bevmo|binny'?s|spec'?s|wally'?s|costco|sam'?s club|"
    r"bj'?s|whole foods|trader joe'?s|kroger|safeway|publix|walmart|target)\b",
    re.I,
)
NOT_WINE_SHOP_RE = re.compile(
    r"\b(?:wine bar|cocktail bar|sports bar|pub|gastropub|brewery|distillery|"
    r"winery|vineyard|restaurant|pizza|cafe|coffee|supermarket|grocery store|"
    r"warehouse|discount|wholesale|wholesaler|package store|convenience store)\b",
    re.I,
)
NON_RETAIL_VENUE_RE = re.compile(
    r"\b(?:theatre|theater|cinema|botanical garden|country club|social club|"
    r"golf club|private club|event venue|performing arts|museum|stadium|arena|"
    r"hotel|resort|university|wedding venue|banquet hall)\b",
    re.I,
)
NON_WINE_TYPE_RE = re.compile(
    r"\b(?:bar & grill|book store|greeting card shop|orchestra|bakery|"
    r"aromatherapy|home goods store|candle store|corporate office|"
    r"service establishment|gift shop|farm|florist|clothing store|"
    r"furniture store|jewelry store|art gallery|spa|salon)\b",
    re.I,
)
EXPANDED_NOISE_RE = re.compile(
    r"\b(?:cvs|walgreens|rite aid|sunoco|sheetz|gas station|tobacco|"
    r"smoke shop|vape|book store|greeting card shop|theatre|theater|"
    r"country club|botanical garden|orchestra|hotel|resort|night club|"
    r"sports bar|cigar shop|coffee shop|pizza restaurant)\b",
    re.I,
)
PROSPECTING_TAIL_NOISE_RE = re.compile(
    r"\b(?:cvs|walgreens|rite aid|sunoco|sheetz|gas station|tobacco|"
    r"smoke shop|vape|book store|greeting card shop|theatre|theater|"
    r"country club|botanical garden|orchestra|hotel|resort|night club|"
    r"sports bar|cigar shop|coffee shop|pizza|restaurant|brewery|"
    r"distillery|supermarket|department store|furniture|hardware|bridal|"
    r"car wash|atm|tourist attraction|amusement|stadium|arena)\b",
    re.I,
)
LIQUOR_HEAVY_RE = re.compile(
    r"\b(?:liquor|spirits|beer|beverage depot|tobacco|vape|smoke shop)\b",
    re.I,
)
COMMODITY_WINE_RE = re.compile(
    r"\b(?:tito'?s|smirnoff|veuve|buzzballz|michelob|budweiser|barefoot|"
    r"yellow ?tail|cupcake|apothic|meiomi|josh|bogle|kendall jackson|"
    r"j\.?\s*lohr|andre|andré|cloud break)\b",
    re.I,
)
POSITIVE_WINE_RE = re.compile(
    r"\b(?:natural wine|biodynamic|organic wine|curated|sommelier|wine club|"
    r"wine merchant|wine shop|wine store|bottle shop|wine boutique|"
    r"small[- ]grower|producer|importer|skurnik|louis/?dressner|"
    r"jenny\s*&\s*fran[cç]ois|selection massale|zev rovine|rosenthal|"
    r"polaner|vom boden|t\.?\s*edward|jos[eé] pastor)\b",
    re.I,
)
CORE_WINE_RETAIL_RE = re.compile(
    r"\b(?:wine shop|wine store|wine merchant|wine cellar|wine cellars|"
    r"wine company|wine co\.?|wine academy|wine outlet|wine market|"
    r"bottle shop|bottleshop|vinoteca|vino|natural wine|fine wine|"
    r"champagne|sommelier|cellars?|wines?)\b",
    re.I,
)
PRESTIGE_SOURCE_RE = re.compile(
    r"\b(?:best_wine_shops|wine_directories|wine enthusiast|vinepair|punch|"
    r"wine spectator|world of fine wine|stockist|michelin|sommeliers choice)\b",
    re.I,
)


def present(value: object) -> bool:
    return str(value or "").strip().lower() not in {"", "nan", "none", "null"}


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def number(value: object, default: float = 0.0) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return default
    return float(parsed)


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def host(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    netloc = parsed.netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def clean_phone(value: object) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def parse_city_state(address: object) -> tuple[str, str]:
    text = re.sub(r",?\s*United States\s*$", "", str(address or ""), flags=re.I)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    for i in range(len(parts) - 1, -1, -1):
        match = re.match(r"^([A-Z]{2})\s*\d{0,5}$", parts[i])
        if match:
            return (parts[i - 1] if i else "", match.group(1))
    return "", ""


def looks_like_chain(name: object) -> bool:
    text = str(name or "").lower()
    return HARD_CHAIN_RE.search(text) is not None or any(keyword in text for keyword in CHAIN_KEYWORDS)


def source_label(path: Path) -> str:
    rel = path.relative_to(ROOT) if path.is_absolute() and ROOT in path.parents else path
    return str(rel)


def read_source(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["_source_file"] = source_label(path)

    if "business_type" in df.columns:
        mask = df["business_type"].fillna("").astype(str).str.lower().eq("wine_store")
    else:
        text_cols = [c for c in ["name", "category", "source", "distinction", "all_sources"] if c in df.columns]
        text = df[text_cols].fillna("").astype(str).agg(" ".join, axis=1) if text_cols else pd.Series("", index=df.index)
        mask = text.str.contains(r"\bwine\b", case=False, regex=True)

    out = df[mask].copy()
    if out.empty:
        return out

    rename_map = {
        "lat": "latitude",
        "lng": "longitude",
        "serper_address": "address",
        "all_sources": "source_tags",
        "all_distinctions": "distinctions",
    }
    for src, dest in rename_map.items():
        if src in out.columns and dest not in out.columns:
            out[dest] = out[src]

    for col in [
        "name", "address", "city", "state", "phone", "website", "rating", "review_count",
        "business_type", "google_type", "google_types", "search_query", "search_city",
        "price_level", "price_tier", "lead_score", "tier", "has_email_signup",
        "has_ecommerce", "instagram_url", "facebook_url", "ig_followers", "fb_likes",
        "follower_count", "press_mentions", "press_sources", "awards_count",
        "awards_list", "has_club_final", "club_type_final", "club_url_final",
        "club_signals_final", "cid", "latitude", "longitude", "source_tags",
        "distinctions", "blurb", "icp_tier", "tier_reason", "fresh_icp_score",
    ]:
        if col not in out.columns:
            out[col] = ""

    missing_location = out["city"].fillna("").astype(str).str.strip().eq("") | out["state"].fillna("").astype(str).str.strip().eq("")
    if missing_location.any() and "address" in out.columns:
        parsed = out.loc[missing_location, "address"].apply(parse_city_state)
        out.loc[missing_location, "city"] = parsed.apply(lambda item: item[0])
        out.loc[missing_location, "state"] = parsed.apply(lambda item: item[1])

    return out


def load_candidates(sources: list[Path]) -> pd.DataFrame:
    frames = []
    missing = []
    for source in sources:
        if not source.exists():
            missing.append(str(source))
            continue
        frame = read_source(source)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise SystemExit(f"No wine-store rows loaded. Missing sources: {missing}")
    candidates = pd.concat(frames, ignore_index=True, sort=False)
    candidates["_missing_sources"] = "; ".join(missing)
    return candidates


def row_text(row: pd.Series) -> str:
    fields = [
        "name", "business_type", "google_type", "google_types", "search_query",
        "page_title", "source_tags", "distinctions", "blurb", "tier_reason",
    ]
    return " ".join(str(row.get(field, "")) for field in fields)


def is_prestige_row(row: pd.Series) -> bool:
    text = f"{row.get('_source_file', '')} {row.get('source_tags', '')} {row.get('distinctions', '')}"
    return PRESTIGE_SOURCE_RE.search(text) is not None


def has_core_wine_retail_evidence(row: pd.Series) -> bool:
    if is_prestige_row(row):
        return True
    business_type = str(row.get("business_type", "")).strip().lower()
    if business_type != "wine_store":
        return False
    fields = [
        "name", "google_type", "google_types", "page_title", "website",
        "source_tags", "distinctions", "blurb",
    ]
    evidence_text = " ".join(str(row.get(field, "")) for field in fields)
    if re.search(r"\bwine (?:store|shop|club)\b", evidence_text, flags=re.I):
        return True
    return CORE_WINE_RETAIL_RE.search(evidence_text) is not None


def rejection_reason(row: pd.Series) -> str:
    name = str(row.get("name", ""))
    text = row_text(row)
    lower_text = text.lower()
    prestige = is_prestige_row(row)

    if not present(name):
        return "missing_name"
    if looks_like_chain(name):
        return "chain_or_big_box"
    if (not present(row.get("city")) or not present(row.get("state"))) and not prestige:
        return "missing_location"
    if NON_RETAIL_VENUE_RE.search(text):
        return "non_retail_venue"
    if NON_WINE_TYPE_RE.search(text) and not has_core_wine_retail_evidence(row):
        return "non_wine_business_type"
    if not has_core_wine_retail_evidence(row):
        return "weak_wine_retail_evidence"
    if NOT_WINE_SHOP_RE.search(text):
        return "not_wine_store"
    if LIQUOR_HEAVY_RE.search(text) and not POSITIVE_WINE_RE.search(text):
        return "liquor_or_beer_heavy"
    if COMMODITY_WINE_RE.search(text):
        return "commodity_brand_signal"
    if not present(row.get("website")) and not prestige:
        return "missing_website"

    rating = number(row.get("rating"), default=0)
    reviews = number(row.get("review_count"), default=0)
    if reviews and reviews < 20 and not prestige:
        return "review_floor"
    if rating and rating < 4.0 and not prestige:
        return "rating_floor"
    if "coming soon" in lower_text:
        return "coming_soon"
    return ""


def expanded_recovery_reason(row: pd.Series) -> str:
    reason = str(row.get("wine_reject_reason", ""))
    if not reason or not has_core_wine_retail_evidence(row) or looks_like_chain(row.get("name")):
        return ""

    text = row_text(row)
    google_type = str(row.get("google_type", ""))
    primary_wine_type = re.search(
        r"\b(?:wine store|wine cellar|wine club|wine wholesaler and importer|wine storage facility)\b",
        google_type,
        flags=re.I,
    ) is not None
    rating = number(row.get("rating"))
    reviews = number(row.get("review_count"))

    if reason == "review_floor" and rating >= 4.0 and reviews >= 5:
        return "expanded_low_review_count"
    if reason == "missing_website" and primary_wine_type and rating >= 4.0 and reviews >= 10:
        return "expanded_missing_website"
    if reason == "missing_location" and primary_wine_type and present(row.get("website")):
        return "expanded_missing_location"
    if reason == "rating_floor" and primary_wine_type and rating >= 3.4 and reviews >= 20:
        return "expanded_rating_exception"
    if reason == "not_wine_store" and primary_wine_type and rating >= 4.0 and reviews >= 20:
        if EXPANDED_NOISE_RE.search(text):
            return ""
        return "expanded_hybrid_wine_retail"
    if reason == "liquor_or_beer_heavy" and primary_wine_type and rating >= 4.0 and reviews >= 20:
        if EXPANDED_NOISE_RE.search(text):
            return ""
        return "expanded_liquor_beer_hybrid"
    if reason == "non_retail_venue" and primary_wine_type and present(row.get("website")):
        if re.search(r"\b(?:theatre|theater|country club|botanical garden|orchestra|hotel|resort)\b", text, flags=re.I):
            return ""
        return "expanded_event_or_programming_flag"
    return ""


def prospecting_tail_reason(row: pd.Series) -> str:
    reason = str(row.get("wine_reject_reason", ""))
    if not reason or looks_like_chain(row.get("name")):
        return ""
    if reason in {"chain_or_big_box", "non_wine_business_type", "non_retail_venue", "commodity_brand_signal", "coming_soon"}:
        return ""

    text = row_text(row)
    query = str(row.get("search_query", ""))
    if PROSPECTING_TAIL_NOISE_RE.search(text):
        return ""
    if not re.search(r"\bwine\b", query, flags=re.I):
        return ""
    if not re.search(r"\b(?:wine store|wine shop|wine merchant|wine boutique|wine cellar|natural wine|fine wine|curated wine|independent wine|organic wine|biodynamic wine|sommelier wine|wine and cheese)\b", query, flags=re.I):
        return ""

    rating = number(row.get("rating"))
    reviews = number(row.get("review_count"))
    has_site = present(row.get("website"))
    if rating >= 4.2 and reviews >= 20:
        return "prospecting_tail_wine_query"
    if has_site and rating >= 4.0 and reviews >= 10:
        return "prospecting_tail_wine_query"
    return ""


def dedupe_key(row: pd.Series) -> str:
    phone = clean_phone(row.get("phone"))
    if len(phone) >= 10:
        return f"phone:{phone[-10:]}"
    website_host = host(row.get("website"))
    if website_host:
        return f"host:{website_host}"
    name_city = "|".join([norm(row.get("name")), norm(row.get("city")), norm(row.get("state"))])
    return f"name:{name_city}"


def score_row(row: pd.Series) -> float:
    rating = number(row.get("rating"))
    reviews = number(row.get("review_count"))
    lead_score = number(row.get("lead_score"))
    fresh_score = number(row.get("fresh_icp_score"))
    followers = max(number(row.get("follower_count")), number(row.get("ig_followers")) + number(row.get("fb_likes")))
    press = number(row.get("press_mentions"))
    awards = number(row.get("awards_count"))
    source_count = number(row.get("source_count"))
    text = row_text(row)

    score = 40.0
    score += min(24.0, math.log1p(reviews) * 4.0)
    score += max(0.0, (rating - 4.0) * 12.0)
    score += min(18.0, math.log1p(followers) * 2.0)
    score += min(14.0, lead_score * 0.14)
    score += min(10.0, fresh_score * 0.12)
    score += min(8.0, press * 1.5)
    score += min(8.0, awards * 2.0)
    score += min(7.0, source_count * 2.5)
    score += 10.0 if is_prestige_row(row) else 0.0
    score += 7.0 if truthy(row.get("has_club_final")) else 0.0
    score += 5.0 if truthy(row.get("has_email_signup")) else 0.0
    score += 4.0 if truthy(row.get("has_ecommerce")) else 0.0
    score += 4.0 if present(row.get("instagram_url")) else 0.0
    score += 4.0 if POSITIVE_WINE_RE.search(text) else 0.0

    if LIQUOR_HEAVY_RE.search(text):
        score -= 8.0
    recovery_reason = str(row.get("expanded_recovery_reason", ""))
    if recovery_reason:
        score -= {
            "expanded_low_review_count": 16.0,
            "expanded_missing_website": 18.0,
            "expanded_missing_location": 20.0,
            "expanded_rating_exception": 20.0,
            "expanded_hybrid_wine_retail": 12.0,
            "expanded_liquor_beer_hybrid": 22.0,
            "expanded_event_or_programming_flag": 18.0,
            "prospecting_tail_wine_query": 34.0,
        }.get(recovery_reason, 18.0)
    return round(score, 2)


def assign_band(score: float) -> str:
    if score >= 90:
        return "A - Hot Lead"
    if score >= 72:
        return "B - Warm Lead"
    if score >= 55:
        return "C - Worth a Look"
    return "D - Low Priority"


def build_leads(candidates: pd.DataFrame, limit: int, expanded: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = candidates.copy()
    work["wine_reject_reason"] = work.apply(rejection_reason, axis=1)
    rejected = work[work["wine_reject_reason"].ne("")].copy()
    accepted = work[work["wine_reject_reason"].eq("")].copy()
    accepted["expanded_recovery_reason"] = ""
    accepted["wine_list_mode"] = "strict"
    accepted["qa_required"] = False

    if expanded and not rejected.empty:
        recovered = rejected.copy()
        recovered["expanded_recovery_reason"] = recovered.apply(expanded_recovery_reason, axis=1)
        recovered = recovered[recovered["expanded_recovery_reason"].ne("")].copy()
        recovered["wine_list_mode"] = "expanded"
        recovered["qa_required"] = True
        recovered_indexes = set(recovered.index)
        tail = rejected[~rejected.index.isin(recovered_indexes)].copy()
        tail["expanded_recovery_reason"] = tail.apply(prospecting_tail_reason, axis=1)
        tail = tail[tail["expanded_recovery_reason"].ne("")].copy()
        tail["wine_list_mode"] = "prospecting_tail"
        tail["qa_required"] = True
        recovered = pd.concat([recovered, tail], ignore_index=True, sort=False)
        accepted = pd.concat([accepted, recovered], ignore_index=True, sort=False)

    accepted["_dedupe_key"] = accepted.apply(dedupe_key, axis=1)
    accepted["wine_priority_score"] = accepted.apply(score_row, axis=1)
    accepted["wine_icp_band"] = accepted["wine_priority_score"].apply(assign_band)
    accepted["_prestige_rank"] = accepted.apply(is_prestige_row, axis=1).astype(int)
    accepted["_club_rank"] = accepted["has_club_final"].apply(truthy).astype(int)
    accepted["_reviews_rank"] = accepted["review_count"].apply(number)
    accepted["_mode_rank"] = accepted["wine_list_mode"].map({"strict": 3, "expanded": 2, "prospecting_tail": 1}).fillna(0)

    accepted = (
        accepted.sort_values(
            ["_mode_rank", "wine_priority_score", "_prestige_rank", "_club_rank", "_reviews_rank", "rating"],
            ascending=[False, False, False, False, False, False],
        )
        .drop_duplicates("_dedupe_key", keep="first")
        .sort_values(
            ["_mode_rank", "wine_priority_score", "_prestige_rank", "_club_rank", "_reviews_rank", "rating"],
            ascending=[False, False, False, False, False, False],
        )
        .reset_index(drop=True)
    )
    accepted.insert(0, "rank", range(1, len(accepted) + 1))
    return accepted.head(limit).copy(), accepted, rejected


def write_outputs(final: pd.DataFrame, accepted: pd.DataFrame, rejected: pd.DataFrame, args: argparse.Namespace) -> None:
    args.run_dir.mkdir(parents=True, exist_ok=True)

    final_cols = [
        "rank", "name", "wine_icp_band", "wine_priority_score", "wine_list_mode",
        "qa_required", "expanded_recovery_reason", "wine_reject_reason", "city", "state",
        "address", "phone", "website", "rating", "review_count",
        "has_club_final", "club_type_final", "club_url_final", "club_signals_final",
        "has_email_signup", "has_ecommerce", "instagram_url", "facebook_url",
        "ig_followers", "fb_likes", "follower_count", "press_mentions",
        "press_sources", "awards_count", "awards_list", "tier", "lead_score",
        "icp_tier", "tier_reason", "google_type", "google_types", "search_query",
        "search_city", "source_tags", "distinctions", "blurb", "cid",
        "latitude", "longitude", "_source_file",
    ]
    final_cols = [col for col in final_cols if col in final.columns]

    top_path = args.run_dir / f"wine_leads_top_{len(final)}.csv"
    accepted_path = args.run_dir / "wine_candidates_ranked.csv"
    rejected_path = args.run_dir / "wine_candidates_rejected.csv"
    qa_path = args.run_dir / "wine_leads_qa_sample.csv"
    summary_path = args.run_dir / "summary.json"

    final[final_cols].to_csv(top_path, index=False)
    accepted.to_csv(accepted_path, index=False)
    rejected.to_csv(rejected_path, index=False)
    final.groupby("wine_icp_band", group_keys=False).head(max(1, args.qa_per_band)).to_csv(qa_path, index=False)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target": int(args.limit),
        "final_rows": int(len(final)),
        "accepted_deduped_rows": int(len(accepted)),
        "rejected_rows": int(len(rejected)),
        "sources": [str(path) for path in args.sources],
        "final_by_band": final["wine_icp_band"].value_counts().to_dict() if not final.empty else {},
        "accepted_by_band": accepted["wine_icp_band"].value_counts().to_dict() if not accepted.empty else {},
        "final_by_mode": final["wine_list_mode"].value_counts().to_dict() if "wine_list_mode" in final else {},
        "final_recovery_reasons": final["expanded_recovery_reason"].replace("", "strict").value_counts().to_dict() if "expanded_recovery_reason" in final else {},
        "rejected_by_reason": rejected["wine_reject_reason"].value_counts().to_dict() if not rejected.empty else {},
        "final_with_website": int(final["website"].apply(present).sum()) if "website" in final else 0,
        "final_with_email_signup": int(final["has_email_signup"].apply(truthy).sum()) if "has_email_signup" in final else 0,
        "final_with_club_signal": int(final["has_club_final"].apply(truthy).sum()) if "has_club_final" in final else 0,
        "final_with_instagram": int(final["instagram_url"].apply(present).sum()) if "instagram_url" in final else 0,
        "median_rating": float(final["rating"].apply(number).replace(0, pd.NA).median()) if "rating" in final else 0,
        "median_review_count": float(final["review_count"].apply(number).replace(0, pd.NA).median()) if "review_count" in final else 0,
        "files": {
            "top_leads": str(top_path),
            "accepted_ranked": str(accepted_path),
            "rejected": str(rejected_path),
            "qa_sample": str(qa_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if len(final) < args.limit:
        raise SystemExit(f"Only built {len(final):,} rows for target {args.limit:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top ICP-aligned wine-store leads from existing corpora.")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--qa-per-band", type=int, default=25)
    parser.add_argument("--expanded", action="store_true", help="Append lower-confidence wine-retail rows with QA flags.")
    parser.add_argument("--sources", type=Path, nargs="*", default=DEFAULT_SOURCES)
    args = parser.parse_args()

    candidates = load_candidates(args.sources)
    final, accepted, rejected = build_leads(candidates, args.limit, expanded=args.expanded)
    write_outputs(final, accepted, rejected, args)


if __name__ == "__main__":
    main()
