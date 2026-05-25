"""
TAM calculation for Table22.

Three-way build:
1. Bottom-up from existing partner data (Partner Type × Tier matrix).
2. Top-down from US industry baselines (Census/BLS/IBISWorld).
3. Triangulate the two.

Tier definitions (Peak AGMV):
  Tier 1: >= $80K
  Tier 2: $30K - $80K
  Tier 3: $10K - $30K
  Tier 4: < $10K
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

CSV_PATH = Path(
    "/Users/kavir/Downloads/Past and Existing Partners - Monthly Website Visits - "
    "T22_final_list-Default-view-export-1770858132947 (1).csv"
)


# ---------- HELPERS ----------

def parse_agmv(val) -> float | None:
    if pd.isna(val):
        return None
    s = re.sub(r"[^\d.]", "", str(val))
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def assign_tier(agmv: float | None) -> str:
    if agmv is None:
        return "Unknown"
    if agmv >= 80_000:
        return "T1 (≥$80K)"
    if agmv >= 30_000:
        return "T2 ($30–80K)"
    if agmv >= 10_000:
        return "T3 ($10–30K)"
    return "T4 (<$10K)"


def fmt_int(n) -> str:
    if pd.isna(n):
        return "—"
    return f"{int(n):,}"


def section(title: str) -> None:
    print()
    print("═" * 80)
    print(f"  {title}")
    print("═" * 80)


# ---------- 1. LOAD + CLEAN ----------

df = pd.read_csv(CSV_PATH)
df["agmv"] = df["Peak AGMV"].apply(parse_agmv)
df["tier"] = df["agmv"].apply(assign_tier)
df["partner_type"] = df["Partner Type"].fillna("Unknown").str.strip()
df["general_type"] = df["General Type"].fillna("Unknown").str.strip()

section("1. PARTNER UNIVERSE OVERVIEW")
print(f"Total rows:               {len(df):>6}")
print(f"With AGMV data:           {df['agmv'].notna().sum():>6}")
print(f"Active status:            {(df['Partner Status'] == 'Active').sum():>6}")
print(f"Total AGMV (sum):       ${df['agmv'].sum():>14,.0f}")
print(f"Median AGMV:            ${df['agmv'].median():>14,.0f}")
print(f"Mean AGMV:              ${df['agmv'].mean():>14,.0f}")

section("2. TIER DISTRIBUTION (all partners)")
tier_order = ["T1 (≥$80K)", "T2 ($30–80K)", "T3 ($10–30K)", "T4 (<$10K)", "Unknown"]
tier_dist = df["tier"].value_counts().reindex(tier_order, fill_value=0)
total_known = (df["tier"] != "Unknown").sum()
print(f"{'Tier':<16}{'Count':>8}{'% of known':>14}")
for t in tier_order:
    n = tier_dist[t]
    pct = (n / total_known * 100) if t != "Unknown" else None
    pct_s = f"{pct:>10.1f}%" if pct is not None else "          —"
    print(f"{t:<16}{n:>8}{pct_s:>14}")

# ---------- 3. PARTNER TYPE × TIER MATRIX ----------

section("3. PARTNER TYPE × TIER MATRIX")

ptype = pd.crosstab(
    df["partner_type"],
    df["tier"],
    margins=False,
).reindex(columns=tier_order, fill_value=0)

ptype["Total"] = ptype.sum(axis=1)
ptype = ptype.sort_values("Total", ascending=False)
ptype["T1_pct"] = (ptype["T1 (≥$80K)"] / ptype["Total"] * 100).round(1)

# Display
print(f"{'Partner Type':<32}{'T1':>5}{'T2':>5}{'T3':>5}{'T4':>5}{'?':>5}{'Total':>7}{'T1 %':>8}")
print("─" * 80)
for idx, row in ptype.iterrows():
    print(
        f"{idx[:32]:<32}"
        f"{row['T1 (≥$80K)']:>5}"
        f"{row['T2 ($30–80K)']:>5}"
        f"{row['T3 ($10–30K)']:>5}"
        f"{row['T4 (<$10K)']:>5}"
        f"{row['Unknown']:>5}"
        f"{row['Total']:>7}"
        f"{row['T1_pct']:>7.1f}%"
    )

# Also: General Type × Tier
section("4. GENERAL TYPE × TIER")
gen = pd.crosstab(df["general_type"], df["tier"], margins=False).reindex(
    columns=tier_order, fill_value=0
)
gen["Total"] = gen.sum(axis=1)
gen = gen.sort_values("Total", ascending=False)
print(f"{'General Type':<25}{'T1':>5}{'T2':>5}{'T3':>5}{'T4':>5}{'?':>5}{'Total':>7}")
print("─" * 60)
for idx, row in gen.iterrows():
    print(
        f"{idx[:25]:<25}"
        f"{row['T1 (≥$80K)']:>5}"
        f"{row['T2 ($30–80K)']:>5}"
        f"{row['T3 ($10–30K)']:>5}"
        f"{row['T4 (<$10K)']:>5}"
        f"{row['Unknown']:>5}"
        f"{row['Total']:>7}"
    )

# ---------- 5. TOP-DOWN TAM (US universe baselines) ----------

# US-wide counts from Census Economic Census 2022 / BLS QCEW / IBISWorld
# Numbers are mid-estimates of independent establishment counts.

TOPDOWN = [
    # (group, us_total, independent, premium_pct, premium_count, top30metro_pct)
    {
        "vertical": "Restaurants — full-service",
        "naics": "722511",
        "us_total": 310_000,
        "independent": 220_000,
        "premium_pct": 0.13,    # ~13% of independents are premium-tier
        "top30_pct": 0.50,
    },
    {
        "vertical": "Restaurants — counter / fast-casual (independent quality tier)",
        "naics": "722513",
        "us_total": 200_000,
        "independent": 130_000,
        "premium_pct": 0.06,
        "top30_pct": 0.55,
    },
    {
        "vertical": "Bars / taverns / wine bars",
        "naics": "722410",
        "us_total": 65_000,
        "independent": 55_000,
        "premium_pct": 0.10,
        "top30_pct": 0.55,
    },
    {
        "vertical": "Bakeries (retail)",
        "naics": "311811",
        "us_total": 7_000,
        "independent": 6_500,
        "premium_pct": 0.30,
        "top30_pct": 0.45,
    },
    {
        "vertical": "Butcher shops / specialty meat",
        "naics": "445230",
        "us_total": 6_000,
        "independent": 5_500,
        "premium_pct": 0.18,
        "top30_pct": 0.50,
    },
    {
        "vertical": "Wine / liquor specialty retail",
        "naics": "445320",
        "us_total": 10_000,
        "independent": 9_500,
        "premium_pct": 0.25,
        "top30_pct": 0.50,
    },
    {
        "vertical": "Cheese / specialty dairy shops",
        "naics": "445299",
        "us_total": 500,
        "independent": 500,
        "premium_pct": 0.80,
        "top30_pct": 0.55,
    },
    {
        "vertical": "Specialty coffee (with retail)",
        "naics": "722515",
        "us_total": 35_000,
        "independent": 28_000,
        "premium_pct": 0.10,
        "top30_pct": 0.55,
    },
    {
        "vertical": "Craft breweries (with taproom/retail)",
        "naics": "312120",
        "us_total": 9_500,
        "independent": 9_000,
        "premium_pct": 0.18,
        "top30_pct": 0.35,
    },
    {
        "vertical": "Craft distilleries",
        "naics": "312140",
        "us_total": 2_500,
        "independent": 2_300,
        "premium_pct": 0.25,
        "top30_pct": 0.35,
    },
    {
        "vertical": "Specialty / gourmet grocers",
        "naics": "445110",
        "us_total": 5_500,
        "independent": 4_500,
        "premium_pct": 0.20,
        "top30_pct": 0.50,
    },
    {
        "vertical": "Confectionery / chocolatier",
        "naics": "311351",
        "us_total": 3_500,
        "independent": 3_200,
        "premium_pct": 0.20,
        "top30_pct": 0.45,
    },
]

# Tier mix assumption (top-down): of "premium" operators, what fraction
# would land in each AGMV tier if Table22 fully penetrated?
# Derived later by anchoring to bottom-up.
# Initial guess based on partner data tier distribution:
TIER_MIX_DEFAULT = {
    "T1 (≥$80K)": 0.10,
    "T2 ($30–80K)": 0.20,
    "T3 ($10–30K)": 0.35,
    "T4 (<$10K)": 0.35,
}

# Sub-premium tier expansion: how many "Tier 4-eligible" operators exist
# below the premium ICP? Approximation: roughly 3x the premium count
# becomes Tier 4 candidates (lower brand strength but still subscribable).
SUB_PREMIUM_MULTIPLIER = 3.0

section("5. TOP-DOWN TAM BUILD (US universe)")
topdown_rows = []
print(
    f"{'Vertical':<48}"
    f"{'US tot':>10}"
    f"{'Indep':>10}"
    f"{'Premium':>10}"
    f"{'Top-30':>10}"
    f"{'Sub-prem':>10}"
)
print("─" * 98)
total_premium_top30 = 0
total_subpremium_top30 = 0
for v in TOPDOWN:
    premium = int(v["independent"] * v["premium_pct"])
    top30_premium = int(premium * v["top30_pct"])
    subpremium = int((v["independent"] - premium) * SUB_PREMIUM_MULTIPLIER / 10)
    # Sub-prem = roughly 30% of non-premium independents in top 30 metros
    subpremium_top30 = int(
        (v["independent"] - premium) * 0.30 * v["top30_pct"]
    )
    total_premium_top30 += top30_premium
    total_subpremium_top30 += subpremium_top30
    topdown_rows.append(
        {
            **v,
            "premium": premium,
            "top30_premium": top30_premium,
            "subpremium_top30": subpremium_top30,
        }
    )
    print(
        f"{v['vertical'][:48]:<48}"
        f"{fmt_int(v['us_total']):>10}"
        f"{fmt_int(v['independent']):>10}"
        f"{fmt_int(premium):>10}"
        f"{fmt_int(top30_premium):>10}"
        f"{fmt_int(subpremium_top30):>10}"
    )

print("─" * 98)
print(
    f"{'TOTAL':<48}"
    f"{'':<10}"
    f"{'':<10}"
    f"{'':<10}"
    f"{fmt_int(total_premium_top30):>10}"
    f"{fmt_int(total_subpremium_top30):>10}"
)

# Top-down by tier (apply tier mix to premium + sub-premium pool)
top30_total = total_premium_top30 + total_subpremium_top30

# Premium operators concentrate in T1-T2. Sub-premium concentrate in T3-T4.
PREMIUM_TIER_MIX = {
    "T1 (≥$80K)": 0.20,
    "T2 ($30–80K)": 0.30,
    "T3 ($10–30K)": 0.30,
    "T4 (<$10K)": 0.20,
}
SUBPREMIUM_TIER_MIX = {
    "T1 (≥$80K)": 0.03,
    "T2 ($30–80K)": 0.10,
    "T3 ($10–30K)": 0.30,
    "T4 (<$10K)": 0.57,
}

td_tier = {}
for t, p in PREMIUM_TIER_MIX.items():
    td_tier[t] = (
        total_premium_top30 * p
        + total_subpremium_top30 * SUBPREMIUM_TIER_MIX[t]
    )

section("6. TOP-DOWN TAM BY TIER (top-30 metros)")
print(f"Premium-tier addressable (top-30 metros):     {fmt_int(total_premium_top30)}")
print(f"Sub-premium addressable (top-30 metros):      {fmt_int(total_subpremium_top30)}")
print(f"Combined TAM pool (top-30 metros):            {fmt_int(top30_total)}")
print()
print(f"{'Tier':<16}{'Estimated US TAM':>20}")
print("─" * 36)
for t in ["T1 (≥$80K)", "T2 ($30–80K)", "T3 ($10–30K)", "T4 (<$10K)"]:
    print(f"{t:<16}{fmt_int(td_tier[t]):>20}")
print("─" * 36)
print(f"{'TOTAL':<16}{fmt_int(sum(td_tier.values())):>20}")

# ---------- 7. BOTTOM-UP TAM ----------
# Logic:
# - For each Partner Type present in our data, we already have N partners across tiers.
# - Assume current market penetration of P% for that Partner Type
#   (P = 1-5% depending on how long we've sold into that type).
# - Then implied TAM for that Partner Type at tier T = (our partners at tier T) / P.

section("7. BOTTOM-UP TAM (extrapolated from existing partner mix)")

# Penetration assumptions — informed by how many partners we have today.
# Conservative: 1.5% penetration of the addressable universe.
PENETRATION_BASELINE = 0.015  # 1.5%

# Per-type penetration override (some types we've sold harder into).
PEN_OVERRIDE = {
    "Bakery": 0.020,
    "Butcher Shop": 0.025,
    "Wine Shop": 0.020,
    "Cheese Shop": 0.040,
    "Tasting Menu Restaurant": 0.025,
    "Neighborhood Restaurant": 0.010,
    "Fine Dining": 0.025,
}

print(
    f"{'Partner Type':<32}"
    f"{'T1':>6}"
    f"{'T2':>6}"
    f"{'T3':>6}"
    f"{'T4':>6}"
    f"{'Penetr':>8}"
    f"{'TAM (T1-T4)':>14}"
)
print("─" * 80)

bottomup_by_tier = {t: 0 for t in tier_order if t != "Unknown"}
bottomup_total = 0
for idx, row in ptype.iterrows():
    pen = PEN_OVERRIDE.get(idx, PENETRATION_BASELINE)
    tam = {}
    for t in ["T1 (≥$80K)", "T2 ($30–80K)", "T3 ($10–30K)", "T4 (<$10K)"]:
        # Account for unknown-tier partners by distributing them proportionally
        known = row["Total"] - row["Unknown"]
        unknown_extra = (
            row["Unknown"] * (row[t] / known) if known > 0 else 0
        )
        adj_count = row[t] + unknown_extra
        tam[t] = adj_count / pen if pen > 0 else 0
        bottomup_by_tier[t] += tam[t]
    total_tam = sum(tam.values())
    bottomup_total += total_tam
    print(
        f"{str(idx)[:32]:<32}"
        f"{row['T1 (≥$80K)']:>6}"
        f"{row['T2 ($30–80K)']:>6}"
        f"{row['T3 ($10–30K)']:>6}"
        f"{row['T4 (<$10K)']:>6}"
        f"{pen*100:>7.1f}%"
        f"{fmt_int(total_tam):>14}"
    )

print("─" * 80)
print(f"{'TOTAL':<32}{'':<32}{fmt_int(bottomup_total):>16}")

section("8. BOTTOM-UP TAM BY TIER")
print(f"{'Tier':<16}{'Bottom-up TAM':>20}")
print("─" * 36)
for t in ["T1 (≥$80K)", "T2 ($30–80K)", "T3 ($10–30K)", "T4 (<$10K)"]:
    print(f"{t:<16}{fmt_int(bottomup_by_tier[t]):>20}")

# ---------- 9. TRIANGULATION ----------

section("9. TRIANGULATION (top-down vs bottom-up)")
print(
    f"{'Tier':<16}{'Top-down':>14}{'Bottom-up':>14}"
    f"{'Midpoint':>14}{'Range':>22}"
)
print("─" * 80)
final_tam = {}
for t in ["T1 (≥$80K)", "T2 ($30–80K)", "T3 ($10–30K)", "T4 (<$10K)"]:
    td = td_tier[t]
    bu = bottomup_by_tier[t]
    midpoint = (td + bu) / 2
    lo = min(td, bu) * 0.85
    hi = max(td, bu) * 1.15
    final_tam[t] = (lo, midpoint, hi)
    print(
        f"{t:<16}"
        f"{fmt_int(td):>14}"
        f"{fmt_int(bu):>14}"
        f"{fmt_int(midpoint):>14}"
        f"  {fmt_int(lo)}–{fmt_int(hi):<10}"
    )

print("─" * 80)
total_td = sum(td_tier.values())
total_bu = bottomup_total
total_mid = (total_td + total_bu) / 2
print(
    f"{'TOTAL':<16}"
    f"{fmt_int(total_td):>14}"
    f"{fmt_int(total_bu):>14}"
    f"{fmt_int(total_mid):>14}"
)

# ---------- 10. METHODOLOGY NOTES ----------

section("10. METHODOLOGY NOTES")
print(
    """
TOP-DOWN method:
  - Start with US Census/BLS establishment counts per NAICS.
  - Estimate % independent (vs chains).
  - Estimate % "premium-tier" of independents — operators with brand/quality fit.
  - Estimate % concentrated in top-30 metros (where Table22 is positioned).
  - Apply tier mix (PREMIUM_TIER_MIX vs SUBPREMIUM_TIER_MIX) to allocate
    operators across T1-T4 AGMV bands.

BOTTOM-UP method:
  - For each Partner Type observed in our existing partner list:
    count partners at each tier (Peak AGMV).
  - Assume current market penetration of 1.5% baseline
    (higher for verticals we've sold into longer).
  - Extrapolate: TAM_at_tier = observed_partners_at_tier / penetration.
  - Unknown-AGMV partners distributed proportionally across known tiers.

TRIANGULATION:
  - Midpoint = (top-down + bottom-up) / 2
  - Range = (min*0.85) to (max*1.15) to capture uncertainty.

KEY ASSUMPTIONS TO STRESS-TEST:
  - Penetration rate (1.5-4%): bottom-up TAM scales linearly with this.
  - Premium-tier % per vertical: top-down sensitive to ±5pp swings.
  - Top-30 metro concentration: probably understated for premium operators.
"""
)
