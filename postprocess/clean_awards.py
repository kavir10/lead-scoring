"""
Data cleaning pass on output/awards_all_*.csv.

Inputs:  output/awards_all_<YYYYMMDD>.csv (latest)
Outputs:
  output/awards_all_clean_<YYYYMMDD>.csv         — same row count, normalized fields
  output/awards_businesses_<YYYYMMDD>.csv        — one row per (name, city, state) with
                                                    all distinctions joined + award_count
Notes:
- Backs up nothing — caller is expected to keep the source file.
- Idempotent: rewrite-safe.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
TODAY = datetime.now().strftime("%Y%m%d")

YEAR_RE = re.compile(r"\b(19[6-9]\d|20\d{2})\b")
CURLY_TABLE = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2013: "-", 0x2014: "-"}
NYC_ALIASES = {"new york city": "New York", "manhattan": "New York", "nyc": "New York"}
NUMERIC_BLURB_RE = re.compile(r"^\s*\d+\s*$")


def latest_master() -> Path:
    files = sorted(OUT.glob("awards_all_2*.csv"))
    files = [p for p in files if "_clean_" not in p.name and not p.name.endswith(".bak.csv")]
    if not files:
        sys.exit("No awards_all_*.csv found")
    return files[-1]


def fix_quotes(s: str) -> str:
    if not isinstance(s, str):
        return s
    return s.translate(CURLY_TABLE)


def squash_ws(s: str) -> str:
    if not isinstance(s, str):
        return s
    return re.sub(r"\s+", " ", s).strip()


def extract_year(distinction: str) -> str:
    if not isinstance(distinction, str):
        return ""
    m = YEAR_RE.search(distinction)
    return m.group(1) if m else ""


def normalize_city(city: str) -> str:
    if not isinstance(city, str) or not city.strip():
        return city
    key = city.strip().lower()
    return NYC_ALIASES.get(key, city.strip())


def clear_numeric_michelin_blurb(row: pd.Series) -> str:
    blurb = row.get("blurb", "")
    if row.get("source") == "michelin" and isinstance(blurb, str) and NUMERIC_BLURB_RE.match(blurb):
        return ""
    return blurb


def norm_key(name: str, city: str, state: str) -> str:
    def n(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.lower().strip()
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"^the\s+", "", s)
        return s
    return f"{n(name)}|{n(city)}|{n(state)}"


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ("name", "city", "state", "distinction", "blurb", "source", "source_url"):
        if col in out.columns:
            out[col] = out[col].apply(lambda v: squash_ws(fix_quotes(v)) if isinstance(v, str) else v)

    out["city"] = out["city"].apply(normalize_city)
    out["year"] = out["distinction"].apply(extract_year)
    out["blurb"] = out.apply(clear_numeric_michelin_blurb, axis=1)

    out["country"] = out["country"].fillna("us").replace({"": "us"})

    if "tier" in out.columns:
        out["tier"] = pd.to_numeric(out["tier"], errors="coerce").fillna(2).astype(int)

    out = out.dropna(subset=["name"])
    out = out[out["name"].astype(str).str.strip() != ""]
    return out.reset_index(drop=True)


def rollup_businesses(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_key"] = df.apply(lambda r: norm_key(r["name"], r.get("city", ""), r.get("state", "")), axis=1)

    def join_unique(series: pd.Series) -> str:
        seen, ordered = set(), []
        for v in series.fillna(""):
            v = str(v).strip()
            if v and v not in seen:
                seen.add(v)
                ordered.append(v)
        return " | ".join(ordered)

    grouped = df.groupby("_key", sort=False).agg(
        name=("name", "first"),
        city=("city", "first"),
        state=("state", "first"),
        country=("country", "first"),
        business_type=("business_type", "first"),
        best_tier=("tier", "min"),
        award_count=("source", "nunique"),
        sources=("source", join_unique),
        distinctions=("distinction", join_unique),
        years=("year", join_unique),
        source_urls=("source_url", join_unique),
    ).reset_index(drop=True)

    return grouped.sort_values(["award_count", "best_tier"], ascending=[False, True]).reset_index(drop=True)


def main() -> None:
    src = latest_master()
    print(f"Source:  {src.relative_to(ROOT)}")
    df = pd.read_csv(src)
    before_rows = len(df)
    before_year_filled = df["year"].notna().sum()
    before_michelin_numeric = (
        (df["source"] == "michelin") & df["blurb"].astype(str).str.match(r"^\s*\d+\s*$")
    ).sum()
    before_curly = df["name"].astype(str).str.contains(r"[‘’“”]").sum()
    before_nyc_alias = df["city"].isin(["New York City", "Manhattan", "NYC", "nyc"]).sum()

    cleaned = clean(df)
    rollup = rollup_businesses(cleaned)

    clean_path = OUT / f"awards_all_clean_{TODAY}.csv"
    rollup_path = OUT / f"awards_businesses_{TODAY}.csv"
    cleaned.to_csv(clean_path, index=False)
    rollup.to_csv(rollup_path, index=False)

    print(f"\nWrote:   {clean_path.relative_to(ROOT)}  ({len(cleaned)} rows)")
    print(f"Wrote:   {rollup_path.relative_to(ROOT)}  ({len(rollup)} businesses)")

    print("\n--- Changes applied ---")
    print(f"  Years extracted from distinction:  +{cleaned['year'].astype(str).str.strip().ne('').sum() - before_year_filled} rows now have a year")
    print(f"  Michelin numeric blurbs cleared:   {before_michelin_numeric} rows")
    print(f"  Curly quotes in name normalized:   {before_curly} rows")
    print(f"  NYC city aliases collapsed:        {before_nyc_alias} rows")
    print(f"  Rows dropped (empty name):         {before_rows - len(cleaned)}")

    print("\n--- Rollup snapshot ---")
    print(f"  Businesses with 2+ awards: {(rollup['award_count'] >= 2).sum()}")
    print(f"  Businesses with 3+ awards: {(rollup['award_count'] >= 3).sum()}")
    print("  Top recognized:")
    for _, r in rollup.head(10).iterrows():
        loc = f"{r['city']}, {r['state']}" if r["city"] and r["state"] else (r["city"] or r["state"] or "—")
        print(f"    {r['award_count']}x  {r['name']:<35} {loc:<25} [{r['sources'][:80]}]")


if __name__ == "__main__":
    main()
