"""
Latent-monetization filters over an enriched CSV (ideas #9, #20 in
docs/INNOVATIVE_LEAD_LIST_BUILDING_IDEAS.md).

Two lists from one pass over a generic-pipeline enriched CSV
(2_enriched_*.csv or a scored custom-serper-scoring_*.csv):

  tech_ready_no_subscription  (#9)  — compatible tech stack already in place
      (email platform, reservation platform, or ecommerce) but no club.
      They understand digital operations; they haven't monetized repeat
      demand yet.

  email_list_no_monetization  (#20) — has an email signup but no club and
      no ecommerce. They own an audience with no repeat-commerce product —
      per docs/ICP.md, email-list presence is the audience-nurturing signal.

If the input lacks club columns, optionally join them from a
detect_clubs*.py output via --clubs (matched on website domain), or run
with --no-club-data to treat club status as unknown (rows kept, flagged).

Usage:
    python postprocess/latent_monetization.py output/2_enriched_availability.csv
    python postprocess/latent_monetization.py scored.csv --clubs output/with_clubs.csv
    python postprocess/latent_monetization.py scored.csv --no-club-data
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

TECH_COLS = ["email_platform", "reservation_url", "has_ecommerce", "has_email_signup"]


def domain_of(url: str) -> str:
    host = (urlparse(str(url) if pd.notna(url) else "").netloc or "").lower()
    return host.removeprefix("www.")


def truthy(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])


def join_club_data(df: pd.DataFrame, clubs_path: str) -> pd.DataFrame:
    clubs = pd.read_csv(clubs_path, dtype=str).fillna("")
    if "has_club" not in clubs.columns or "website" not in clubs.columns:
        sys.exit(f"--clubs file needs has_club + website columns: {clubs_path}")
    clubs["_domain"] = clubs["website"].map(domain_of)
    lookup = (clubs[clubs["_domain"] != ""]
              .drop_duplicates("_domain")[["_domain", "has_club"]])
    df["_domain"] = df["website"].map(domain_of)
    df = df.merge(lookup, on="_domain", how="left", suffixes=("", "_joined"))
    if "has_club_joined" in df.columns:
        df["has_club"] = df["has_club"].fillna("") if "has_club" in df.columns else ""
        df["has_club"] = df["has_club_joined"].fillna(df.get("has_club", ""))
        df = df.drop(columns=["has_club_joined"])
    return df.drop(columns=["_domain"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Enriched or scored CSV (needs website + enrichment columns)")
    ap.add_argument("--clubs", help="detect_clubs*.py output to join has_club from (by website domain)")
    ap.add_argument("--no-club-data", action="store_true", help="Proceed without club data; club status flagged unknown")
    ap.add_argument("-o", "--output-prefix", default="", help="Output path prefix (default: output/<list>_<YYYYMMDD>.csv)")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    missing = [c for c in TECH_COLS if c not in df.columns]
    if missing:
        sys.exit(f"Input is missing enrichment columns {missing} — run the websites "
                 f"enrichment step first (python main.py --enrich <csv>).")

    if args.clubs:
        df = join_club_data(df, args.clubs)

    if "has_club" in df.columns:
        has_club = truthy(df["has_club"])
        club_known = True
    elif args.no_club_data:
        has_club = pd.Series(False, index=df.index)
        club_known = False
    else:
        sys.exit("No has_club column. Either join one with --clubs <detect_clubs output>, "
                 "or pass --no-club-data to proceed with club status unknown.")

    has_email = truthy(df["has_email_signup"]) | (df["email_platform"].str.strip() != "")
    has_resy = df["reservation_url"].str.strip() != ""
    has_ecom = truthy(df["has_ecommerce"])

    stamp = datetime.now().strftime("%Y%m%d")
    prefix = args.output_prefix or "output/"
    Path(prefix).parent.mkdir(parents=True, exist_ok=True) if "/" in prefix else None

    # --- #9: tech-ready, no subscription ---
    tech_ready = df[(has_email | has_resy | has_ecom) & ~has_club].copy()
    tech_ready["latent_reason"] = (
        "tech_ready:"
        + has_email.loc[tech_ready.index].map({True: " email", False: ""})
        + has_resy.loc[tech_ready.index].map({True: " reservations", False: ""})
        + has_ecom.loc[tech_ready.index].map({True: " ecommerce", False: ""})
    )
    tech_ready["club_status"] = "no_club" if club_known else "unknown"
    p1 = f"{prefix}tech_ready_no_subscription_{stamp}.csv"
    tech_ready.to_csv(p1, index=False)
    print(f"#9  tech_ready_no_subscription: {len(tech_ready):>6} rows -> {p1}")

    # --- #20: email audience, no monetization at all ---
    email_only = df[has_email & ~has_ecom & ~has_club].copy()
    email_only["latent_reason"] = "email_list_no_monetization"
    email_only["club_status"] = "no_club" if club_known else "unknown"
    p2 = f"{prefix}email_list_no_monetization_{stamp}.csv"
    email_only.to_csv(p2, index=False)
    print(f"#20 email_list_no_monetization: {len(email_only):>6} rows -> {p2}")


if __name__ == "__main__":
    main()
