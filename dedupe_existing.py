"""
Dedupe new pipeline results against previously discovered leads.
Removes any companies already present in prior scored/discovered files.
"""
import os
import sys
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def load_existing_leads() -> pd.DataFrame:
    """Load all previously discovered/scored leads for dedup comparison."""
    existing_files = [
        os.path.join(OUTPUT_DIR, "3_scored_all_combined_final.csv"),
        os.path.join(OUTPUT_DIR, "1_discovered_merged.csv"),
    ]
    frames = []
    for f in existing_files:
        if os.path.exists(f):
            df = pd.read_csv(f)
            print(f"  Loaded {len(df)} leads from {os.path.basename(f)}")
            frames.append(df)

    if not frames:
        print("  No existing lead files found.")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Dedup the existing set itself
    combined["phone_clean"] = combined["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
    combined = combined.drop_duplicates(subset=["phone_clean"], keep="first")
    mask_no_phone = combined["phone_clean"] == ""
    with_phone = combined[~mask_no_phone]
    no_phone = combined[mask_no_phone].drop_duplicates(subset=["name", "address"], keep="first")
    combined = pd.concat([with_phone, no_phone], ignore_index=True)
    print(f"  Total unique existing leads: {len(combined)}")
    return combined


def dedupe_against_existing(new_path: str) -> None:
    """Remove leads from new_path that already exist in prior files."""
    print(f"\n{'='*60}")
    print("DEDUPLICATION AGAINST EXISTING LEADS")
    print(f"{'='*60}")

    new_df = pd.read_csv(new_path)
    print(f"\nNew leads to dedupe: {len(new_df)}")

    print("\nLoading existing leads...")
    existing = load_existing_leads()
    if existing.empty:
        print("No existing leads to dedupe against. Skipping.")
        return

    # Build lookup sets from existing leads
    existing["phone_clean"] = existing["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
    existing_phones = set(existing["phone_clean"][existing["phone_clean"] != ""])
    existing_name_addr = set(
        zip(
            existing["name"].str.lower().str.strip(),
            existing["address"].str.lower().str.strip(),
        )
    )

    # Mark duplicates in new data
    new_df["phone_clean"] = new_df["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
    is_phone_dupe = new_df["phone_clean"].isin(existing_phones) & (new_df["phone_clean"] != "")
    is_name_addr_dupe = pd.Series(
        [
            (str(n).lower().strip(), str(a).lower().strip()) in existing_name_addr
            for n, a in zip(new_df["name"], new_df["address"])
        ],
        index=new_df.index,
    )

    is_dupe = is_phone_dupe | is_name_addr_dupe
    n_dupes = is_dupe.sum()

    deduped = new_df[~is_dupe].drop(columns=["phone_clean"]).reset_index(drop=True)

    print(f"\nDuplicates found: {n_dupes}")
    print(f"Leads after dedup: {len(deduped)}")

    # Show breakdown by type
    print("\nBy business type:")
    for bt in sorted(deduped["business_type"].unique()):
        n = (deduped["business_type"] == bt).sum()
        print(f"  {bt}: {n}")

    # Save deduped file
    base, ext = os.path.splitext(os.path.basename(new_path))
    deduped_path = os.path.join(OUTPUT_DIR, f"{base}_deduped{ext}")
    deduped.to_csv(deduped_path, index=False)
    print(f"\nSaved deduped results to {deduped_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Auto-find the most recent scored "all" file
        import glob
        pattern = os.path.join(OUTPUT_DIR, "custom-serper-scoring_*_all.csv")
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if files:
            path = files[0]
            print(f"Auto-detected latest scored file: {os.path.basename(path)}")
        else:
            print("Usage: python dedupe_existing.py <path_to_scored_csv>")
            print("  Or run without args to auto-detect the latest scored file.")
            sys.exit(1)
    else:
        path = sys.argv[1]

    dedupe_against_existing(path)
