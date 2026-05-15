"""
Basic data cleaning for the best_wine_shops output CSV.

Operations:
 1. Strip whitespace on all string columns.
 2. Normalize city names ("New York City" -> "New York", "Washington, DC" ->
    "Washington", title-case, etc.).
 3. Strip stray punctuation from names; collapse internal whitespace.
 4. Drop rows that are obviously not a single shop:
    - empty name
    - name AND no city AND no state (can't enrich, can't verify)
 5. Smarter dedupe: collapse variants like "Astor Wine & Spirits" /
    "Astor Wines & Spirits", "3 Parks Wine" / "3 Parks Wine Shop",
    "Domestique" / "Domestique Wine". Keep the longest canonical name and the
    best (lowest-numbered) domain_tier; merge `distinction` and `source_url`
    across collapsed rows (semicolon-joined).
 6. Re-write the CSV in place.

Run:
    python -m best_wine_shops.clean output/best_wine_shops/best_wine_shops_20260515.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from awards._lib import normalize_state

# Tokens stripped from the dedupe key but not from the displayed name.
_NOISE_TOKENS = [
    "wine shop", "wine store", "wine cellars", "wine cellar",
    "wine merchants", "wine merchant", "wine company", "wine co",
    "wines & spirits", "wine & spirits", "wines and spirits",
    "wine and spirits", "wine bar", "fine wines", "fine wine",
    "wines", "wine", "spirits", "spirit", "liquors", "liquor",
    "& co", "and co", "the ",
]

_PUNCT_RX = re.compile(r"[^\w\s&]")
_WS_RX = re.compile(r"\s+")


def _key(name: str) -> str:
    s = (name or "").lower().strip()
    s = _PUNCT_RX.sub(" ", s)
    s = s.replace(" and ", " & ")
    for tok in _NOISE_TOKENS:
        s = s.replace(tok, " ")
    s = _WS_RX.sub(" ", s).strip()
    return s


def _clean_city(city: str) -> str:
    c = (city or "").strip()
    if not c:
        return ""
    # Strip trailing state suffix that snuck in: "Brooklyn, NY"
    c = re.sub(r",\s*[A-Z]{2}\.?$", "", c)
    c = re.sub(r"\s*\([^)]*\)\s*$", "", c)
    # Canonicalize common variants
    canon = {
        "new york city": "New York",
        "nyc": "New York",
        "manhattan": "New York",
        "washington dc": "Washington",
        "washington d.c.": "Washington",
        "washington, dc": "Washington",
        "san fran": "San Francisco",
        "sf": "San Francisco",
        "la": "Los Angeles",
        "l.a.": "Los Angeles",
    }
    low = c.lower().strip(" .")
    if low in canon:
        return canon[low]
    # Title-case if it's all lower
    if c == c.lower():
        c = c.title()
    return c.strip()


def _clean_name(name: str) -> str:
    n = (name or "").strip()
    n = n.strip(" .,;:-—")
    n = _WS_RX.sub(" ", n)
    return n


def _merge_sources(values: list[str]) -> str:
    seen: list[str] = []
    for v in values:
        for piece in re.split(r"\s*;\s*", str(v) if v else ""):
            piece = piece.strip()
            if piece and piece not in seen:
                seen.append(piece)
    return "; ".join(seen)


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {"input": len(df)}

    # 1) Strip whitespace on every string col.
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # 2) Per-column normalizers.
    df["name"] = df["name"].map(_clean_name)
    df["city"] = df["city"].map(_clean_city)
    df["state"] = df["state"].map(lambda s: normalize_state(s))
    df["country"] = df["country"].str.lower().replace({"": "us"})
    df["distinction"] = df["distinction"].map(_clean_name)
    df["blurb"] = df["blurb"].str.replace(r"\s+", " ", regex=True).str.strip()

    # 3) Drop empty / unverifiable.
    before = len(df)
    df = df[df["name"].str.len() > 1].copy()
    df = df[~((df["city"] == "") & (df["state"] == ""))].copy()
    stats["dropped_empty_or_unverifiable"] = before - len(df)

    # 4) Build dedupe key. Group by (key, city|state-if-no-city).
    df["_key"] = df["name"].map(_key)
    df["_loc"] = df["city"].str.lower().where(df["city"] != "", df["state"].str.lower())
    df["_dedupe"] = df["_key"] + "||" + df["_loc"].fillna("")

    # Sort so the row we want to keep is first in each group:
    #   - lower domain_tier (editorial before reddit before other)
    #   - longer name (richer canonical form)
    #   - non-empty city before empty city
    df["_tier"] = pd.to_numeric(df.get("domain_tier", 3), errors="coerce").fillna(3)
    df["_namelen"] = df["name"].str.len()
    df["_hascity"] = (df["city"] != "").astype(int)
    df = df.sort_values(
        ["_dedupe", "_tier", "_hascity", "_namelen"],
        ascending=[True, True, False, False],
    )

    # Aggregate within each group.
    def _agg(group: pd.DataFrame) -> pd.Series:
        head = group.iloc[0].copy()
        head["distinction"] = _merge_sources(group["distinction"].tolist())
        head["source_url"] = _merge_sources(group["source_url"].tolist())
        head["blurb"] = next(
            (b for b in group["blurb"].tolist() if b),
            "",
        )
        head["is_large_indie"] = str(any(str(v).lower() == "true" for v in group.get("is_large_indie", [])))
        head["is_online_only"] = str(any(str(v).lower() == "true" for v in group.get("is_online_only", [])))
        head["domain_tier"] = int(group["_tier"].min())
        return head

    merged = df.groupby("_dedupe", as_index=False, sort=False).apply(_agg, include_groups=False)
    # `apply` may return a DataFrame or Series-of-Series depending on pandas version.
    if not isinstance(merged, pd.DataFrame):
        merged = pd.DataFrame(merged)
    merged = merged.drop(columns=[c for c in ("_key", "_loc", "_dedupe", "_tier", "_namelen", "_hascity") if c in merged.columns])

    stats["after_dedupe"] = len(merged)
    stats["dupes_merged"] = before - stats["dropped_empty_or_unverifiable"] - len(merged)
    return merged.reset_index(drop=True), stats


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m best_wine_shops.clean <csv>")
        return 1
    path = Path(argv[1])
    raw = pd.read_csv(path, dtype=str).fillna("")
    cleaned, stats = clean(raw)
    cleaned.to_csv(path, index=False)
    print(f"Cleaned {path}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    print("Tier breakdown after clean:")
    print(cleaned["domain_tier"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
