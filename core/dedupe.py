"""
Dedupe strategies shared across pipelines.

Two generic flavors live here:

  dedupe_by_name_city                   awards/_lib.dedupe; first wins by
                                        case-insensitive (name, city)
  dedupe_by_phone_or_name_address       main.py:merge_discovery rule;
                                        phone-first, fall back to (name,
                                        address) for no-phone rows

Pipeline-specific dedupes (Michelin tier-aware, Beli ig_handle-first,
butcher domain-first) stay local because they carry business logic.
"""
from __future__ import annotations

import pandas as pd


def dedupe_by_name_city(df: pd.DataFrame) -> pd.DataFrame:
    """Keep first row per case-insensitive (name, city). No-op on empty df.

    Across-source duplicates are intentionally NOT collapsed here — multiple
    awards reinforce a lead. Use `build_master`-style cross-source dedupe at
    the union step if needed.
    """
    if df.empty or "name" not in df.columns:
        return df
    city_col = df["city"] if "city" in df.columns else pd.Series([""] * len(df), index=df.index)
    key = (
        df["name"].fillna("").str.lower().str.strip()
        + "||"
        + city_col.fillna("").str.lower().str.strip()
    )
    df = df.assign(_dedupe_key=key)
    df = df.drop_duplicates("_dedupe_key", keep="first")
    return df.drop(columns="_dedupe_key").reset_index(drop=True)


def dedupe_by_phone_or_name_address(df: pd.DataFrame) -> pd.DataFrame:
    """Phone-first dedupe; rows without a phone fall back to (name, address).

    Used by the generic Serper pipeline (main.py:merge_discovery) and useful
    anywhere a phone column is reliably populated.
    """
    if df.empty:
        return df

    df = df.copy()
    if "phone" not in df.columns:
        df["phone"] = ""
    df["_phone_clean"] = df["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)

    deduped = df.drop_duplicates(subset=["_phone_clean"], keep="first")
    no_phone_mask = deduped["_phone_clean"] == ""
    with_phone = deduped[~no_phone_mask]

    name_col = "name" if "name" in df.columns else None
    address_col = "address" if "address" in df.columns else None
    if name_col and address_col:
        no_phone = (
            deduped[no_phone_mask]
            .drop_duplicates(subset=[name_col, address_col], keep="first")
        )
    else:
        no_phone = deduped[no_phone_mask]

    out = pd.concat([with_phone, no_phone], ignore_index=True)
    return out.drop(columns=["_phone_clean"]).reset_index(drop=True)
