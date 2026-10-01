"""
Merge the vault Maps lookup with the new Maps sweep into one candidate list,
and (after verify_whole_animal.py has run on it) filter to the final list.

    python scripts/build_whole_animal_list.py merge VAULT_MAPS.csv NEW_MAPS.csv [MORE.csv ...] CANDIDATES.csv
    python scripts/verify_whole_animal.py CANDIDATES.csv VERIFIED.csv
    python scripts/instagram_whole_animal.py VERIFIED.csv VERIFIED_IG.csv
    # directory rows that passed: Maps lookup, then attach
    python scripts/discover_whole_animal.py lookup DIR_STRONG.csv DIR_MAPS.csv
    python scripts/build_whole_animal_list.py attach-maps VERIFIED_IG.csv DIR_MAPS.csv VERIFIED_FULL.csv
    python scripts/build_whole_animal_list.py filter VERIFIED_FULL.csv FINAL.csv

Final-list rule (agreed with Kavir, 2026-09-25):
  - state not in HI, IN, IA, KS, NV, ND, SD
  - the shop's own site says "whole animal", "nose to tail", or that it breaks
    down whole animals in-house, graded "strong" by verify_whole_animal.py (a
    craft claim, not custom processing, bulk sides, or an incidental mention)
  - walk-in retail location: a Google Maps listing with a street address and
    posted hours, typed as retail (butcher shop, meat market, deli...), or a
    non-retail type (processor, wholesaler) whose own site posts retail hours
  - not a farm (Maps type or name) and not a meat-share / CSA business; a
    "whole animal" match that only means buying a whole/half/quarter animal
    does not count
"""
from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import urlparse

import pandas as pd

BANNED_STATES = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}
RETAIL_TYPES = re.compile(
    r"butcher|meat market|meat products store|deli|charcuterie|grocery|market|"
    r"specialty food|gourmet|farm shop|general store|food store|restaurant",
    re.I)
NON_RETAIL_TYPES = re.compile(r"wholesaler|distribution|processor|packer|slaughter", re.I)
STREET_RE = re.compile(r"^\s*\d")

# Farms and meat-share / CSA businesses are out (Kavir, 2026-09-25).
FARM_TYPE_RE = re.compile(r"\bfarm\b|ranch|livestock|cattle|agricultur", re.I)
FARM_NAME_RE = re.compile(r"\b(?:farms?|ranch(?:es)?|acres|cattle co(?:mpany)?|livestock)\b", re.I)
SHARE_NAME_RE = re.compile(r"\b(?:meat share|csa|buying club|meat club|herd ?share|cow ?share)\b", re.I)
# "whole animal" used only in the bulk-purchase sense, not in-house butchery.
BULK_ONLY_RE = re.compile(
    r"whole[\s\-]+animal\s+(?:shares?|purchases?|orders?|sales?)|buy(?:ing)?\s+(?:a\s+)?whole[\s\-]+animal|"
    r"whole,?\s+(?:or\s+)?half(?:,?\s+(?:or|and)\s+quarter)?|half\s+(?:or|and)\s+whole|by the (?:side|half|quarter)|"
    r"freezer (?:beef|pork|meat)|bulk (?:beef|pork|meat)",
    re.I)
RESTAURANT_TYPE_RE = re.compile(r"restaurant|cafe|bar\b", re.I)
BUTCHER_NAME_RE = re.compile(r"butcher|meat|salumeria|charcuterie|boucherie|carne", re.I)
# Sites that matched but are not shops (hand-checked).
NOT_A_SHOP_DOMAINS = {"brightwater.org"}  # culinary school butchery program
OFFERS_SHARE_RE = re.compile(r"meat share|meat club|membership|subscription|butcher box|monthly box|csa", re.I)


def _domain(url) -> str:
    url = str(url or "").strip().lower()
    if not url or url == "nan":
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return urlparse(url).netloc.removeprefix("www.")


def merge(vault_maps: str, new_files: list[str], out: str) -> None:
    v = pd.read_csv(vault_maps, dtype=str)
    v["lead_source"] = "existing (vault ICP list)"
    v["vault_tier"] = v["tier"]
    v["vault_website"] = v["website"]
    # Prefer the Maps website: ~1/4 of vault URLs point at domains that don't resolve.
    v["website"] = v["maps_website"].where(v["maps_website"].fillna("").str.len() > 0, v["website"])
    v["state"] = v["maps_state"].where(v["maps_state"].fillna("").str.len() > 0, v["state"])

    seen_cids = set(v["cid"].dropna())
    seen_domains = {d for d in v["website"].map(_domain) if d} | {d for d in v["vault_website"].map(_domain) if d}
    frames = [v]
    for path in new_files:
        n = pd.read_csv(path, dtype=str)
        if "cid" in n:  # Maps sweep output
            n["lead_source"] = "new (Maps sweep)"
            n["maps_match"] = "ok"
        else:  # directory / source-lane output (name, website, city, state); Maps looked up later
            n["lead_source"] = "new (directories)"
            n["cid"] = pd.NA
        dom = n["website"].map(_domain)
        before = len(n)
        keep = ~n["cid"].isin(seen_cids) & ~(dom.isin(seen_domains) & (dom != ""))
        n = n[keep]
        n = n[n.cid.isna() | ~n.cid.duplicated()]
        seen_cids |= set(n["cid"].dropna())
        seen_domains |= {d for d in n["website"].map(_domain) if d}
        print(f"{path}: {before} rows, {before - len(n)} already seen, {len(n)} net new", file=sys.stderr)
        frames.append(n)

    cols = ["lead_source", "vault_tier", "name", "website", "vault_website", "city", "state", "awards",
            "maps_match", "maps_name", "maps_address", "maps_type", "maps_types", "maps_phone",
            "maps_rating", "maps_reviews", "maps_hours", "cid", "search_query", "search_city"]
    allrows = pd.concat(frames, ignore_index=True).reindex(columns=cols)
    allrows.to_csv(out, index=False)
    print(f"wrote {len(allrows)} candidates to {out}", file=sys.stderr)
    print(allrows.lead_source.value_counts().to_string(), file=sys.stderr)


def attach_maps(verified: str, lookup_out: str, out: str) -> None:
    """Fill Maps fields for rows (directory leads) that were looked up after verification."""
    d = pd.read_csv(verified, dtype=str)
    lk = pd.read_csv(lookup_out, dtype=str)
    maps_cols = [c for c in lk.columns if c.startswith("maps_") or c == "cid"]
    key = lambda df: df["name"].fillna("") + "|" + df["website"].fillna("")
    lk = lk.assign(_k=key(lk)).drop_duplicates("_k").set_index("_k")[maps_cols]
    d["_k"] = key(d)
    hit = d["_k"].isin(lk.index)
    for c in maps_cols:
        d.loc[hit, c] = d.loc[hit, "_k"].map(lk[c])
    d.drop(columns="_k").to_csv(out, index=False)
    print(f"attached Maps fields to {hit.sum()} rows; wrote {out}", file=sys.stderr)


def filter_final(verified: str, out: str, review: str = "") -> None:
    d = pd.read_csv(verified, dtype=str)
    d["whole_animal"] = d["whole_animal"].str.lower() == "true"
    d["links_table22"] = d["links_table22"].str.lower() == "true"

    has_maps = (d.maps_match == "ok") & d.maps_address.fillna("").str.match(STREET_RE)
    has_hours = d.maps_hours.fillna("").str.len() > 2
    retail = d.maps_type.fillna("").str.contains(RETAIL_TYPES) & ~d.maps_type.fillna("").str.contains(NON_RETAIL_TYPES)
    site_hours = d.storefront == "yes"

    d["storefront_basis"] = ""
    d.loc[has_maps & has_hours & retail, "storefront_basis"] = "Google Maps retail listing with hours"
    d.loc[(d.storefront_basis == "") & has_maps & site_hours, "storefront_basis"] = \
        "Maps address + retail hours on own site"
    d.loc[(d.storefront_basis == "") & ~has_maps & site_hours, "storefront_basis"] = \
        "retail hours on own site (no Maps match)"

    name = d.name.fillna("")
    mtype = d.maps_type.fillna("") + " " + d.maps_types.fillna("")
    ev = d.wa_evidence.fillna("")
    is_farm = mtype.str.contains(FARM_TYPE_RE) | name.str.contains(FARM_NAME_RE) | d.maps_name.fillna("").str.contains(FARM_NAME_RE)
    is_share = name.str.contains(SHARE_NAME_RE) | mtype.str.contains(SHARE_NAME_RE)
    bulk_only = ev.str.contains(BULK_ONLY_RE) & (d.wa_terms.fillna("") == "whole animal")
    d["offers_share_or_box"] = (ev + " " + d.storefront_evidence.fillna("")).str.contains(OFFERS_SHARE_RE)

    steps = [
        ("candidates", pd.Series(True, index=d.index)),
        ("allowed state", ~d.state.fillna("").str.upper().isin(BANNED_STATES) & (d.state.fillna("") != "")),
        ("site reachable", d.site_status == "ok"),
        ("advertises whole animal", d.whole_animal),
        ("strong whole-animal claim", d.wa_strength.fillna("") == "strong"),
        ("walk-in retail location", d.storefront_basis != ""),
        ("not a farm", ~is_farm),
        ("not a meat share / CSA", ~is_share & ~bulk_only),
        ("butcher, not just a restaurant", ~mtype.str.contains(RESTAURANT_TYPE_RE) | name.str.contains(BUTCHER_NAME_RE)),
        ("not a school/program page", ~d.website.map(_domain).isin(NOT_A_SHOP_DOMAINS)),
    ]
    mask = pd.Series(True, index=d.index)
    for label, m in steps:
        mask &= m
        print(f"{label:>26}: {mask.sum():>5}  "
              f"(existing {(mask & d.lead_source.str.startswith('existing')).sum()}, "
              f"new {(mask & d.lead_source.str.startswith('new')).sum()})", file=sys.stderr)

    # Matches that said "whole animal" but not as a craft claim: kept aside for review.
    pre_grade = steps[0][1] & steps[1][1] & steps[2][1] & steps[3][1]
    graded_out = d[pre_grade & (d.wa_strength.fillna("") != "strong")]
    review_path = out.replace(".csv", "_review_weak_bulk_processing.csv")
    graded_out[["wa_strength", "name", "lead_source", "maps_type", "maps_address", "website",
                "wa_evidence", "wa_evidence_url"]].sort_values("wa_strength").to_csv(review_path, index=False)
    print(f"wrote {len(graded_out)} non-strong matches to {review_path}", file=sys.stderr)

    reason = pd.Series("", index=d.index)
    reason[bulk_only] = "whole animal only in bulk/share sense"
    reason[is_share] = "meat share / CSA"
    reason[is_farm] = "farm"
    pre = steps[0][1]
    for _, m in steps[:6]:
        pre = pre & m
    excluded = d[pre & (reason != "")].assign(exclusion_reason=reason)
    excl_path = out.replace(".csv", "_excluded_farms_shares.csv")
    excluded[["exclusion_reason", "name", "lead_source", "maps_type", "maps_address", "website", "wa_evidence"]]\
        .to_csv(excl_path, index=False)
    print(f"wrote {len(excluded)} farm/share exclusions to {excl_path}", file=sys.stderr)

    f = d[mask].copy()
    # Blank CIDs (no Maps match) must not collapse into one row.
    f = f[f.cid.isna() | ~f.cid.duplicated(keep="first")]
    f["dup_key"] = f.website.map(_domain) + "|" + f.maps_address.fillna(f.name)
    f = f.drop_duplicates("dup_key").drop(columns="dup_key")
    # A row with no Maps address duplicates any other row on the same domain
    # (the vault list has repeats, and vault rows re-appear in the Maps sweep).
    dom = f.website.map(_domain)
    no_addr = f.maps_address.isna()
    has_addr_domains = set(dom[~no_addr])
    f = f[~(no_addr & dom.isin(has_addr_domains))]
    f = f[~(f.maps_address.isna() & f.website.map(_domain).duplicated(keep="first"))]
    f["evidence_tier"] = "verified: own-site claim + storefront"
    if review:
        # Hand-review decisions (research/whole_animal_butchers/manual_review_*.csv):
        # "remove" drops a domain; "add" pulls a candidate in with its evidence tier.
        r = pd.read_csv(review, dtype=str)
        drop = set(r[r.decision == "remove"].domain)
        before = len(f)
        f = f[~f.website.map(_domain).isin(drop)]
        adds = r[r.decision == "add"].set_index("domain")
        pool = d[d.website.map(_domain).isin(adds.index)].copy()
        pool["_dom"] = pool.website.map(_domain)
        pool = pool[~pool._dom.isin(set(f.website.map(_domain)))].drop_duplicates("_dom")
        pool["evidence_tier"] = pool._dom.map(adds.evidence_tier)
        pool["review_note"] = pool._dom.map(adds.reason)
        f = pd.concat([f, pool.drop(columns="_dom")], ignore_index=True)
        print(f"review: removed {before - len(f) + len(pool)}, added {len(pool)} "
              f"({pool.evidence_tier.value_counts().to_dict()})", file=sys.stderr)
    f = f.sort_values(["state", "city", "name"])
    cols = ["name", "evidence_tier", "review_note", "lead_source", "vault_tier", "links_table22", "offers_share_or_box", "maps_address", "city", "state",
            "maps_phone", "website", "maps_type", "maps_rating", "maps_reviews", "maps_hours",
            "instagram", "ig_followers", "wa_source", "wa_terms", "wa_strength", "wa_evidence", "wa_evidence_url", "storefront_basis", "storefront_evidence",
            "awards", "cid"]
    f.reindex(columns=cols).to_csv(out, index=False)
    print(f"wrote {len(f)} leads to {out}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("vault_maps")
    m.add_argument("new_files", nargs="+", help="Maps sweep and/or directory CSVs")
    m.add_argument("output")
    am = sub.add_parser("attach-maps")
    am.add_argument("verified")
    am.add_argument("lookup_out")
    am.add_argument("output")
    f = sub.add_parser("filter")
    f.add_argument("verified")
    f.add_argument("output")
    f.add_argument("--review", default="", help="hand-review decisions CSV (domain, decision, evidence_tier, reason)")
    args = ap.parse_args()
    if args.cmd == "merge":
        merge(args.vault_maps, args.new_files, args.output)
    elif args.cmd == "attach-maps":
        attach_maps(args.verified, args.lookup_out, args.output)
    else:
        filter_final(args.verified, args.output, args.review)


if __name__ == "__main__":
    main()
