"""
Butcher-specific national discovery helpers.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

import pandas as pd

from config import BANNED_STATES


STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "DC",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}
STATE_ABBREVIATIONS = {name: abbr for abbr, name in STATE_NAMES.items()}

TOP_US_CITIES = [
    ("New York", "NY", "New York", 8478072),
    ("Los Angeles", "CA", "California", 3878704),
    ("Chicago", "IL", "Illinois", 2721308),
    ("Houston", "TX", "Texas", 2390125),
    ("Phoenix", "AZ", "Arizona", 1673164),
    ("Philadelphia", "PA", "Pennsylvania", 1573916),
    ("San Antonio", "TX", "Texas", 1526656),
    ("San Diego", "CA", "California", 1404452),
    ("Dallas", "TX", "Texas", 1326087),
    ("Jacksonville", "FL", "Florida", 1009833),
    ("Fort Worth", "TX", "Texas", 1008106),
    ("San Jose", "CA", "California", 997368),
    ("Austin", "TX", "Texas", 993588),
    ("Charlotte", "NC", "North Carolina", 943476),
    ("Columbus", "OH", "Ohio", 933263),
    ("San Francisco", "CA", "California", 827526),
    ("Seattle", "WA", "Washington", 780995),
    ("Denver", "CO", "Colorado", 729019),
    ("Oklahoma City", "OK", "Oklahoma", 712919),
    ("Nashville", "TN", "Tennessee", 704963),
    ("Washington", "DC", "DC", 702250),
    ("El Paso", "TX", "Texas", 681723),
    ("Boston", "MA", "Massachusetts", 673458),
    ("Detroit", "MI", "Michigan", 645705),
    ("Louisville", "KY", "Kentucky", 640796),
    ("Portland", "OR", "Oregon", 635749),
    ("Memphis", "TN", "Tennessee", 610919),
    ("Baltimore", "MD", "Maryland", 568271),
    ("Milwaukee", "WI", "Wisconsin", 563531),
    ("Albuquerque", "NM", "New Mexico", 560326),
    ("Tucson", "AZ", "Arizona", 554013),
    ("Fresno", "CA", "California", 550105),
    ("Sacramento", "CA", "California", 535798),
    ("Atlanta", "GA", "Georgia", 520070),
    ("Mesa", "AZ", "Arizona", 517151),
    ("Kansas City", "MO", "Missouri", 516032),
    ("Raleigh", "NC", "North Carolina", 499825),
    ("Colorado Springs", "CO", "Colorado", 493554),
    ("Omaha", "NE", "Nebraska", 489265),
    ("Miami", "FL", "Florida", 487014),
    ("Virginia Beach", "VA", "Virginia", 454808),
    ("Long Beach", "CA", "California", 450901),
    ("Oakland", "CA", "California", 443554),
    ("Minneapolis", "MN", "Minnesota", 428579),
    ("Bakersfield", "CA", "California", 417468),
    ("Tulsa", "OK", "Oklahoma", 415154),
    ("Tampa", "FL", "Florida", 414547),
    ("Arlington", "TX", "Texas", 403672),
    ("Aurora", "CO", "Colorado", 403130),
    ("Cleveland", "OH", "Ohio", 365379),
    ("New Orleans", "LA", "Louisiana", 362701),
    ("Anaheim", "CA", "California", 344561),
    ("Orlando", "FL", "Florida", 334854),
    ("Lexington", "KY", "Kentucky", 329437),
    ("Stockton", "CA", "California", 324975),
    ("Riverside", "CA", "California", 323757),
    ("Irvine", "CA", "California", 318683),
    ("Corpus Christi", "TX", "Texas", 317317),
    ("Newark", "NJ", "New Jersey", 317303),
    ("Santa Ana", "CA", "California", 316184),
    ("Cincinnati", "OH", "Ohio", 314915),
    ("Pittsburgh", "PA", "Pennsylvania", 307668),
    ("Saint Paul", "MN", "Minnesota", 307465),
    ("Greensboro", "NC", "North Carolina", 307381),
    ("Jersey City", "NJ", "New Jersey", 302824),
    ("Durham", "NC", "North Carolina", 301870),
    ("Lincoln", "NE", "Nebraska", 300619),
    ("Plano", "TX", "Texas", 293286),
    ("Anchorage", "AK", "Alaska", 289600),
    ("Gilbert", "AZ", "Arizona", 288790),
    ("Madison", "WI", "Wisconsin", 285300),
    ("Chandler", "AZ", "Arizona", 281231),
    ("St. Louis", "MO", "Missouri", 279695),
    ("Chula Vista", "CA", "California", 278546),
    ("Buffalo", "NY", "New York", 276617),
    ("Lubbock", "TX", "Texas", 272086),
    ("St. Petersburg", "FL", "Florida", 267102),
    ("Toledo", "OH", "Ohio", 265638),
    ("Laredo", "TX", "Texas", 261260),
    ("Port St. Lucie", "FL", "Florida", 258575),
    ("Glendale", "AZ", "Arizona", 258143),
    ("Irving", "TX", "Texas", 258060),
    ("Winston-Salem", "NC", "North Carolina", 255769),
    ("Chesapeake", "VA", "Virginia", 254997),
    ("Garland", "TX", "Texas", 250431),
    ("Scottsdale", "AZ", "Arizona", 246170),
    ("Boise", "ID", "Idaho", 237963),
    ("Hialeah", "FL", "Florida", 235388),
    ("Frisco", "TX", "Texas", 235208),
    ("Richmond", "VA", "Virginia", 233655),
    ("Cape Coral", "FL", "Florida", 233025),
    ("Norfolk", "VA", "Virginia", 231105),
    ("Spokane", "WA", "Washington", 230609),
    ("Huntsville", "AL", "Alabama", 230402),
    ("Santa Clarita", "CA", "California", 229159),
    ("Tacoma", "WA", "Washington", 228202),
    ("Fremont", "CA", "California", 228192),
    ("McKinney", "TX", "Texas", 227526),
    ("San Bernardino", "CA", "California", 224775),
    ("Baton Rouge", "LA", "Louisiana", 220907),
    ("Modesto", "CA", "California", 220592),
    ("Fontana", "CA", "California", 218455),
    ("Salt Lake City", "UT", "Utah", 217783),
    ("Moreno Valley", "CA", "California", 213919),
    ("Worcester", "MA", "Massachusetts", 211286),
    ("Yonkers", "NY", "New York", 211040),
    ("Fayetteville", "NC", "North Carolina", 209496),
    ("Grand Prairie", "TX", "Texas", 207331),
    ("Rochester", "NY", "New York", 207282),
    ("Tallahassee", "FL", "Florida", 205089),
    ("Little Rock", "AR", "Arkansas", 204774),
    ("Amarillo", "TX", "Texas", 203729),
    ("Columbus", "GA", "Georgia", 201830),
    ("Augusta", "GA", "Georgia", 201737),
    ("Mobile", "AL", "Alabama", 201367),
    ("Oxnard", "CA", "California", 200616),
    ("Grand Rapids", "MI", "Michigan", 200117),
    ("Peoria", "AZ", "Arizona", 199924),
    ("Vancouver", "WA", "Washington", 198992),
    ("Knoxville", "TN", "Tennessee", 198722),
    ("Birmingham", "AL", "Alabama", 196357),
    ("Montgomery", "AL", "Alabama", 195818),
    ("Providence", "RI", "Rhode Island", 194706),
    ("Huntington Beach", "CA", "California", 193151),
    ("Brownsville", "TX", "Texas", 191967),
    ("Chattanooga", "TN", "Tennessee", 191496),
    ("Fort Lauderdale", "FL", "Florida", 190641),
    ("Tempe", "AZ", "Arizona", 190114),
    ("Akron", "OH", "Ohio", 189664),
    ("Glendale", "CA", "California", 187823),
    ("Clarksville", "TN", "Tennessee", 185690),
    ("Ontario", "CA", "California", 185285),
    ("Newport News", "VA", "Virginia", 183056),
    ("Elk Grove", "CA", "California", 182797),
    ("Cary", "NC", "North Carolina", 182659),
    ("Aurora", "IL", "Illinois", 180710),
    ("Salem", "OR", "Oregon", 180406),
    ("Pembroke Pines", "FL", "Florida", 179326),
    ("Eugene", "OR", "Oregon", 178786),
    ("Santa Rosa", "CA", "California", 177524),
    ("Rancho Cucamonga", "CA", "California", 176675),
    ("Shreveport", "LA", "Louisiana", 176578),
    ("Garden Grove", "CA", "California", 172361),
    ("Oceanside", "CA", "California", 170941),
    ("Fort Collins", "CO", "Colorado", 170924),
    ("Springfield", "MO", "Missouri", 170596),
    ("Murfreesboro", "TN", "Tennessee", 168387),
    ("Surprise", "AZ", "Arizona", 167564),
    ("Lancaster", "CA", "California", 167426),
    ("Denton", "TX", "Texas", 165998),
    ("Roseville", "CA", "California", 163304),
    ("Palmdale", "CA", "California", 162536),
    ("Corona", "CA", "California", 161540),
    ("Salinas", "CA", "California", 160783),
    ("Killeen", "TX", "Texas", 160616),
    ("Paterson", "NJ", "New Jersey", 160463),
    ("Alexandria", "VA", "Virginia", 159102),
    ("Hollywood", "FL", "Florida", 159073),
    ("Hayward", "CA", "California", 158440),
    ("Charleston", "SC", "South Carolina", 157665),
    ("Macon", "GA", "Georgia", 157056),
    ("Lakewood", "CO", "Colorado", 156868),
    ("Sunnyvale", "CA", "California", 156792),
    ("Springfield", "MA", "Massachusetts", 154888),
    ("Bellevue", "WA", "Washington", 154377),
    ("Naperville", "IL", "Illinois", 153124),
    ("Joliet", "IL", "Illinois", 151837),
    ("Bridgeport", "CT", "Connecticut", 151599),
    ("Mesquite", "TX", "Texas", 150140),
    ("Pasadena", "TX", "Texas", 149617),
    ("Escondido", "CA", "California", 148847),
    ("Savannah", "GA", "Georgia", 148808),
    ("McAllen", "TX", "Texas", 148782),
    ("Gainesville", "FL", "Florida", 148720),
    ("Pomona", "CA", "California", 147966),
    ("Rockford", "IL", "Illinois", 147486),
    ("Thornton", "CO", "Colorado", 146689),
    ("Waco", "TX", "Texas", 146608),
    ("Visalia", "CA", "California", 146271),
    ("Syracuse", "NY", "New York", 146097),
    ("Columbia", "SC", "South Carolina", 144788),
    ("Midland", "TX", "Texas", 143687),
    ("Miramar", "FL", "Florida", 143242),
    ("Palm Bay", "FL", "Florida", 142023),
    ("Lakewood", "NJ", "New Jersey", 141985),
    ("Jackson", "MS", "Mississippi", 141449),
    ("Coral Springs", "FL", "Florida", 140808),
    ("Victorville", "CA", "California", 140721),
    ("Elizabeth", "NJ", "New Jersey", 140413),
    ("Fullerton", "CA", "California", 140054),
    ("Meridian", "ID", "Idaho", 139740),
    ("Torrance", "CA", "California", 139576),
    ("Stamford", "CT", "Connecticut", 139134),
    ("West Valley City", "UT", "Utah", 138144),
    ("Orange", "CA", "California", 137941),
    ("Warren", "MI", "Michigan", 137686),
    ("Hampton", "VA", "Virginia", 137596),
    ("New Haven", "CT", "Connecticut", 137562),
    ("Pasadena", "CA", "California", 137195),
    ("Kent", "WA", "Washington", 136588),
    ("Dayton", "OH", "Ohio", 136346),
    ("Lewisville", "TX", "Texas", 135983),
    ("Carrollton", "TX", "Texas", 135456),
    ("Round Rock", "TX", "Texas", 135359),
    ("Sterling Heights", "MI", "Michigan", 134342),
    ("Santa Clara", "CA", "California", 133132),
    ("Norman", "OK", "Oklahoma", 131010),
    ("Columbia", "MO", "Missouri", 130900),
    ("Abilene", "TX", "Texas", 130501),
    ("Pearland", "TX", "Texas", 129620),
    ("Athens", "GA", "Georgia", 128691),
    ("College Station", "TX", "Texas", 128023),
    ("Clovis", "CA", "California", 127993),
    ("West Palm Beach", "FL", "Florida", 127744),
    ("Allentown", "PA", "Pennsylvania", 127138),
    ("North Charleston", "SC", "South Carolina", 126005),
    ("Simi Valley", "CA", "California", 125778),
    ("Wilmington", "NC", "North Carolina", 125284),
    ("Lakeland", "FL", "Florida", 124990),
    ("Thousand Oaks", "CA", "California", 124229),
    ("Concord", "CA", "California", 124016),
    ("Rochester", "MN", "Minnesota", 123624),
    ("Vallejo", "CA", "California", 123475),
    ("Ann Arbor", "MI", "Michigan", 122925),
    ("Broken Arrow", "OK", "Oklahoma", 122756),
    ("Fairfield", "CA", "California", 122646),
    ("Lafayette", "LA", "Louisiana", 122280),
    ("Hartford", "CT", "Connecticut", 122129),
    ("Arvada", "CO", "Colorado", 121873),
    ("Berkeley", "CA", "California", 121749),
    ("Independence", "MO", "Missouri", 121629),
    ("Billings", "MT", "Montana", 121483),
    ("Cambridge", "MA", "Massachusetts", 121186),
    ("Lowell", "MA", "Massachusetts", 120418),
    ("Odessa", "TX", "Texas", 119748),
    ("High Point", "NC", "North Carolina", 118601),
    ("League City", "TX", "Texas", 118456),
    ("Antioch", "CA", "California", 118453),
    ("Richardson", "TX", "Texas", 118221),
    ("Goodyear", "AZ", "Arizona", 118186),
    ("Pompano Beach", "FL", "Florida", 118104),
    ("Nampa", "ID", "Idaho", 117350),
    ("Menifee", "CA", "California", 117041),
    ("Las Cruces", "NM", "New Mexico", 116998),
    ("Clearwater", "FL", "Florida", 116811),
    ("West Jordan", "UT", "Utah", 116688),
    ("New Braunfels", "TX", "Texas", 116477),
    ("Manchester", "NH", "New Hampshire", 116386),
    ("Miami Gardens", "FL", "Florida", 116173),
    ("Waterbury", "CT", "Connecticut", 115908),
]

PLACE_SUFFIX_RE = re.compile(
    r"\s+("
    r"city|town|village|borough|CDP|municipality|metro government|"
    r"urban county|unified government|charter township|township"
    r")$",
    re.I,
)


def _clean_place_name(name: str) -> str:
    """Remove Census legal/statistical suffixes from place names."""
    return PLACE_SUFFIX_RE.sub("", str(name).strip()).strip()


def load_eligible_butcher_cities(
    min_population: int = 25_000,
    cities_path: str | None = None,
) -> pd.DataFrame:
    """Load the static top-city list for butcher discovery."""
    if cities_path:
        raw = pd.read_csv(cities_path, sep=None, engine="python")
        if not {"NAME", "USPS", "POPULATION"}.issubset(raw.columns):
            raise ValueError("City source must include NAME, USPS, and POPULATION columns")
        df = raw[["NAME", "USPS", "POPULATION"]].copy()
        df["state"] = df["USPS"].astype(str).str.upper().str.strip()
        df["population"] = pd.to_numeric(df["POPULATION"], errors="coerce").fillna(0).astype(int)
    else:
        df = pd.DataFrame(TOP_US_CITIES, columns=["NAME", "USPS", "state_name", "POPULATION"])
        df["state"] = df["USPS"]
        df["population"] = df["POPULATION"]

    df["city"] = df["NAME"].apply(_clean_place_name)
    df["state_name"] = df["state"].map(STATE_NAMES).fillna(df["state"])

    df = df[(df["population"] >= min_population) & ~df["state"].isin(BANNED_STATES)]
    df = df[df["city"].str.len() > 0]
    df["location"] = df["city"] + ", " + df["state_name"]

    return (
        df[["city", "state", "state_name", "population", "location"]]
        .drop_duplicates(subset=["city", "state"])
        .sort_values("population", ascending=False)
        .reset_index(drop=True)
    )


def save_eligible_cities(df: pd.DataFrame, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "1_cities_eligible.csv")
    df.to_csv(path, index=False)
    return path


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _to_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def build_why_high_quality(row: pd.Series) -> str:
    """Create a compact outreach rationale from the strongest butcher signals."""
    reasons = []

    bool_reasons = [
        ("has_meat_box", "meat box"),
        ("has_csa_or_share", "CSA/meat share"),
        ("has_preorder", "preorder flow"),
        ("ships_meat", "shipping"),
        ("has_pickup", "pickup"),
        ("has_subscription_language", "subscription language"),
        ("has_ecommerce", "ecommerce"),
        ("has_email_signup", "email signup"),
        ("animal_welfare_signal", "animal welfare positioning"),
        ("whole_animal_signal", "whole-animal positioning"),
        ("dry_aged_signal", "dry-aged positioning"),
    ]
    for col, label in bool_reasons:
        if _truthy(row.get(col, False)):
            reasons.append(label)

    rating = row.get("rating")
    review_count = _to_int(row.get("review_count", 0))
    if rating and review_count:
        reasons.append(f"{rating} stars / {review_count} reviews")

    followers = _to_int(row.get("follower_count", 0))
    if followers >= 5_000:
        reasons.append(f"{followers:,} social followers")

    press_mentions = _to_int(row.get("press_mentions", 0))
    if press_mentions:
        reasons.append(f"{press_mentions} press mentions")

    awards = str(row.get("awards_list", "") or "").strip()
    if awards:
        reasons.append(f"awards: {awards}")

    source = str(row.get("butcher_source", "") or row.get("source", "") or "").strip()
    if source and source != "google_maps":
        reasons.append(f"source: {source}")

    return "; ".join(reasons[:6])


def add_why_high_quality(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["why_high_quality"] = df.apply(build_why_high_quality, axis=1)
    return df


def timestamped_path(output_dir: str, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"{prefix}_{stamp}.csv")
