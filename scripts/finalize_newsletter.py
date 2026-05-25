"""
Post-process newsletter scrape progress into final CSVs + summary stats.
Merges main scrape with optional recovery-pass results — recovery signals
override the main row when present.

Outputs (dated YYYYMMDD):
  newsletter_merchants/all_results_<DATE>.csv      — full join (seed left-merge)
  newsletter_merchants/newsletter_signal_<DATE>.csv — rows with any signal
  newsletter_merchants/by_platform_<DATE>.csv      — ESP × vertical counts
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS = os.path.join(ROOT, "output/newsletter_merchants/raw/scrape_progress.csv")
RECOVERY = os.path.join(ROOT, "output/newsletter_merchants/raw/recovery_progress.csv")
SEED = os.path.join(ROOT, "output/newsletter_merchants/inputs/seed_100k.csv")
OUT_DIR = os.path.join(ROOT, "output/newsletter_merchants")

# Signal columns to overlay from recovery onto main when recovery found
# something the main scrape missed.
SIGNAL_COLS = [
    "website_status", "final_url", "any_signal",
    "esp_platforms", "esp_count", "form_present", "popup_signal",
    "newsletter_url", "embed_iframe_host", "form_action_host",
    "source_path", "raw_signals",
]

STAMP = datetime.now().strftime("%Y%m%d")


def nonempty(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().ne("")


def main():
    df = pd.read_csv(PROGRESS, dtype=str).fillna("")
    print(f"Loaded main progress (raw): {len(df):,} rows")
    df = df.drop_duplicates(subset=["cid"], keep="last").reset_index(drop=True)
    print(f"After dedupe by cid: {len(df):,} rows")
    df["signal_source"] = df["any_signal"].apply(lambda v: "main" if str(v) else "")

    # Overlay recovery results onto main, where recovery found a signal that
    # main missed (i.e. main row had no any_signal but recovery does).
    if os.path.exists(RECOVERY):
        rec = pd.read_csv(RECOVERY, dtype=str).fillna("")
        rec = rec.drop_duplicates(subset=["cid"], keep="last")
        rec_signal = rec[rec["any_signal"].astype(str) != ""].copy()
        print(f"Recovery progress: {len(rec):,} rows · {len(rec_signal):,} with signal")

        # Build a map cid -> recovery signal row
        rec_signal = rec_signal.set_index("cid")
        df = df.set_index("cid")
        overlay_targets = df.index.intersection(rec_signal.index)
        # Only overlay if the main row didn't already have a signal
        before = (df["any_signal"].astype(str) != "").sum()
        for cid in overlay_targets:
            if str(df.at[cid, "any_signal"]) == "":
                for col in SIGNAL_COLS:
                    if col in rec_signal.columns:
                        df.at[cid, col] = rec_signal.at[cid, col]
                df.at[cid, "signal_source"] = rec_signal.at[cid, "recovered_via"]
        df = df.reset_index()
        after = (df["any_signal"].astype(str) != "").sum()
        print(f"Overlayed recovery signals: {after - before:,} new signal rows")
    else:
        print(f"(No recovery file at {RECOVERY} — skipping merge.)")

    seed = pd.read_csv(SEED, dtype=str).fillna("")
    print(f"Seed rows: {len(seed):,}")

    # Left-join seed onto progress so the all_results file carries name/address/etc.
    merged = seed.merge(
        df.drop(columns=["name", "website", "business_type", "city", "state"], errors="ignore"),
        on="cid", how="left",
    ).fillna("")

    has_signal = nonempty(merged["any_signal"])
    has_esp = nonempty(merged["esp_platforms"])
    has_form = nonempty(merged["form_present"])
    has_popup = nonempty(merged["popup_signal"])
    has_newsletter_url = nonempty(merged["newsletter_url"])

    print("\n=== Detection summary ===")
    n = len(merged)
    if n == 0:
        print("Nothing to summarize.")
        return
    print(f"  Any signal:        {has_signal.sum():,} ({has_signal.mean()*100:.1f}%)")
    print(f"  ESP detected:      {has_esp.sum():,} ({has_esp.mean()*100:.1f}%)")
    print(f"  Newsletter form:   {has_form.sum():,} ({has_form.mean()*100:.1f}%)")
    print(f"  Popup library:    {has_popup.sum():,} ({has_popup.mean()*100:.1f}%)")
    print(f"  Public newsletter URL: {has_newsletter_url.sum():,}")

    print("\n=== Top ESPs ===")
    esp_series = merged["esp_platforms"].fillna("").astype(str)
    explode = esp_series.str.split(";").explode().str.strip()
    explode = explode[explode != ""]
    print(explode.value_counts().head(20).to_string())

    print("\n=== By business_type ===")
    tmp = merged.copy()
    tmp["has_any"] = has_signal
    tmp["has_esp"] = has_esp
    tmp["has_form"] = has_form
    g = tmp.groupby("business_type").agg(
        n=("cid", "size"),
        any_signal=("has_any", "sum"),
        esp=("has_esp", "sum"),
        form=("has_form", "sum"),
    )
    g["any_pct"] = (g["any_signal"] / g["n"] * 100).round(1)
    print(g.to_string())

    print("\n=== Top error statuses ===")
    print(merged["website_status"].value_counts().head(10).to_string())

    if "signal_source" in merged.columns:
        print("\n=== Signal source ===")
        ss = merged.loc[has_signal, "signal_source"].astype(str)
        print(ss.value_counts().to_string())

    # Write outputs
    all_path = os.path.join(OUT_DIR, f"all_results_{STAMP}.csv")
    sig_path = os.path.join(OUT_DIR, f"newsletter_signal_{STAMP}.csv")
    plat_path = os.path.join(OUT_DIR, f"by_platform_{STAMP}.csv")

    merged.to_csv(all_path, index=False)
    merged[has_signal].to_csv(sig_path, index=False)

    # ESP × vertical pivot
    pivot_rows = []
    for vert, sub in merged.groupby("business_type"):
        esp_explode = sub["esp_platforms"].astype(str).str.split(";").explode().str.strip()
        esp_explode = esp_explode[esp_explode != ""]
        for esp, count in esp_explode.value_counts().items():
            pivot_rows.append({"business_type": vert, "esp": esp, "count": int(count)})
    pd.DataFrame(pivot_rows).to_csv(plat_path, index=False)

    print(
        f"\nWrote:\n  {all_path}  ({len(merged):,})"
        f"\n  {sig_path}  ({int(has_signal.sum()):,})"
        f"\n  {plat_path}  ({len(pivot_rows):,} platform/vertical pairs)"
    )


if __name__ == "__main__":
    main()
