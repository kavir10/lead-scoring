"""
Dedupe a fresh restaurant lead CSV against the CIDs already present in prior
output/ CSVs ("existing ones"). Google CID is a stable per-place identifier, so
it is the cleanest cross-run dedupe key.

Writes two date-stamped files next to the input:
  <stem>_netnew_<N>_<stamp>.csv   — CIDs not seen in any prior output CSV
  <stem>_seen_<N>_<stamp>.csv     — CIDs that already exist elsewhere in output/

Never overwrites the input.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"


def collect_existing_cids(exclude: Path) -> tuple[set[str], int]:
    """Union of all non-empty `cid` values across output/**.csv, EXCLUDING every
    file in the input's own run directory. That directory holds this pipeline's
    own raw dump (a superset of the top file's CIDs) and prior re-filter passes,
    so scanning it would self-match every row. "Existing ones" means the broader
    output/ corpus (prior discovered/scored runs), not this run's own artifacts."""
    cids: set[str] = set()
    files_scanned = 0
    exclude = exclude.resolve()
    run_dir = exclude.parent.resolve()
    for path in OUTPUT_DIR.rglob("*.csv"):
        if path.resolve().parent == run_dir:
            continue
        try:
            header = pd.read_csv(path, nrows=0)
        except Exception:
            continue
        if "cid" not in header.columns:
            continue
        try:
            col = pd.read_csv(path, usecols=["cid"], dtype=str, low_memory=False)["cid"]
        except Exception:
            continue
        files_scanned += 1
        cids.update(c.strip() for c in col.dropna() if str(c).strip())
    return cids, files_scanned


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedupe fresh restaurant leads by Google CID against prior output/")
    parser.add_argument("input", type=Path, help="Fresh restaurant CSV ranked by score (must have a `cid` column)")
    parser.add_argument("--target", type=int, default=0,
                        help="Also write the first N net-new rows (input must be score-sorted)")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    df = pd.read_csv(args.input, dtype={"cid": str}, low_memory=False)
    if "cid" not in df.columns:
        raise SystemExit("Input has no `cid` column")

    existing, files_scanned = collect_existing_cids(args.input)
    print(f"Scanned {files_scanned} prior output CSVs with a cid column")
    print(f"Existing distinct CIDs: {len(existing):,}")

    df["cid"] = df["cid"].fillna("").str.strip()

    # Collapse intra-file duplicate CIDs (same Google place that survived the
    # discovery dedupe under different phone/name keys). Input is score-sorted, so
    # keep the first (highest-ranked) occurrence. Blank CIDs are never collapsed.
    has_cid = df["cid"].ne("")
    dup_mask = has_cid & df["cid"].duplicated(keep="first")
    if dup_mask.any():
        print(f"Collapsed {int(dup_mask.sum()):,} intra-file duplicate-CID rows")
        df = df[~dup_mask].reset_index(drop=True)

    has_cid = df["cid"].ne("")
    seen_mask = has_cid & df["cid"].isin(existing)

    netnew = df[~seen_mask].reset_index(drop=True)
    seen = df[seen_mask].reset_index(drop=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = args.input.stem
    netnew_path = args.input.with_name(f"{stem}_netnew_{len(netnew)}_{stamp}.csv")
    seen_path = args.input.with_name(f"{stem}_seen_{len(seen)}_{stamp}.csv")

    netnew.to_csv(netnew_path, index=False)
    seen.to_csv(seen_path, index=False)

    n_no_cid = int((~has_cid).sum())
    print(f"Input rows:        {len(df):,}")
    print(f"  net-new:         {len(netnew):,}  -> {netnew_path.name}")
    print(f"  already seen:    {len(seen):,}  -> {seen_path.name}")
    if n_no_cid:
        print(f"  (rows with no CID kept in net-new: {n_no_cid:,})")

    if args.target:
        top = netnew.head(args.target)
        top_path = args.input.with_name(f"{stem}_netnew_top{len(top)}_{stamp}.csv")
        top.to_csv(top_path, index=False)
        print(f"  net-new top {args.target:,}: {len(top):,}  -> {top_path.name}")
        if len(top) < args.target:
            print(f"  WARNING: only {len(top):,} net-new available (< {args.target:,})")


if __name__ == "__main__":
    main()
