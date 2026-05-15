"""
Geographic lookups and filters shared across every discovery pipeline.

Three families of tables:

  STATE_NAMES        2-letter code -> "Full Name"  (51 entries incl. DC)
  STATE_ABBREVIATIONS"Full Name"   -> 2-letter code (reverse of STATE_NAMES)
  STATE_NAME_TO_CODE lowercased    -> 2-letter, with common aliases
                                     ("washington dc", "new york state", ...)
  STATE_SLUGS        2-letter      -> ("Full Name", "lowercase-slug")
                                     (used by sources that take state slugs
                                     in URLs, e.g. EatWild)
  US_STATES          set of 2-letter codes (51)
  BANNED_STATES      states the lead pipelines refuse to ship to
  TOP_US_CITIES      list[(city, state_abbr, state_name, population)]
  CITY_TO_STATE      lowercased common-city -> 2-letter (covers neighborhoods)
  NON_US_CITIES      lowercased non-US-city blocklist (used by Beli)

Filters:

  filter_us(df)              keep rows where country in {us, usa, ...}
  filter_banned_states(df)   drop rows where state in BANNED_STATES
  slice_cities(...)          subset TOP_US_CITIES by name / state / count
  normalize_state(value)     coerce to 2-letter US code when recognizable
  is_us_country(value)
  parse_city_state(text)     "Brooklyn, NY" -> ("Brooklyn", "NY")
"""
from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "DC", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

STATE_ABBREVIATIONS: dict[str, str] = {name: abbr for abbr, name in STATE_NAMES.items()}
US_STATES: set[str] = set(STATE_NAMES.keys())

# Aliases beyond simple "Full Name" -> code. Lowercased keys.
STATE_NAME_TO_CODE: dict[str, str] = {name.lower(): abbr for abbr, name in STATE_NAMES.items()}
STATE_NAME_TO_CODE.update({
    "new york state": "NY",
    "washington state": "WA",
    "district of columbia": "DC",
    "washington dc": "DC",
    "washington d.c.": "DC",
})

# 2-letter -> (full name, lowercase slug used in some site URLs)
STATE_SLUGS: dict[str, tuple[str, str]] = {
    abbr: (name, name.lower().replace(" ", "").replace(".", ""))
    for abbr, name in STATE_NAMES.items()
}
# Beli/EatWild use these specific slug forms — preserve them
STATE_SLUGS["DC"] = ("DC", "dc")
STATE_SLUGS["NH"] = ("New Hampshire", "newhampshire")
STATE_SLUGS["NJ"] = ("New Jersey", "newjersey")
STATE_SLUGS["NM"] = ("New Mexico", "newmexico")
STATE_SLUGS["NY"] = ("New York", "newyork")
STATE_SLUGS["NC"] = ("North Carolina", "northcarolina")
STATE_SLUGS["ND"] = ("North Dakota", "northdakota")
STATE_SLUGS["RI"] = ("Rhode Island", "rhodeisland")
STATE_SLUGS["SC"] = ("South Carolina", "southcarolina")
STATE_SLUGS["SD"] = ("South Dakota", "southdakota")
STATE_SLUGS["WV"] = ("West Virginia", "westvirginia")

# States that the Table22 lead pipelines refuse to ship to. Universal across
# every discovery pipeline (formerly only enforced in the butcher lane).
BANNED_STATES: set[str] = {"HI", "IN", "IA", "KS", "NV", "ND", "SD"}


# Top US cities by population. (name, state_abbr, state_name, population)
# Source: butcher.py — same list used by Serper-based discovery.
TOP_US_CITIES: list[tuple[str, str, str, int]] = [
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


# Lowercased city/neighborhood -> 2-letter state. Includes neighborhoods
# common in Beli's restaurant tagging (e.g. "silver lake" -> "CA").
CITY_TO_STATE: dict[str, str] = {
    "new york": "NY", "nyc": "NY", "brooklyn": "NY", "queens": "NY",
    "manhattan": "NY", "bronx": "NY", "staten island": "NY",
    "los angeles": "CA", "la": "CA", "silver lake": "CA",
    "west hollywood": "CA", "beverly hills": "CA", "sawtelle": "CA",
    "east hollywood": "CA", "santa monica": "CA", "venice": "CA",
    "hollywood": "CA", "san francisco": "CA", "sf": "CA",
    "oakland": "CA", "berkeley": "CA", "san jose": "CA",
    "san diego": "CA", "long beach": "CA", "sacramento": "CA",
    "chicago": "IL",
    "boston": "MA", "cambridge": "MA", "somerville": "MA",
    "washington": "DC", "dc": "DC", "washington dc": "DC", "washington, d.c.": "DC",
    "philadelphia": "PA", "philly": "PA", "pittsburgh": "PA",
    "seattle": "WA", "portland": "OR",
    "miami": "FL", "tampa": "FL", "orlando": "FL", "fort lauderdale": "FL",
    "austin": "TX", "houston": "TX", "dallas": "TX",
    "san antonio": "TX", "fort worth": "TX",
    "atlanta": "GA", "savannah": "GA",
    "nashville": "TN", "memphis": "TN", "knoxville": "TN",
    "denver": "CO", "boulder": "CO",
    "phoenix": "AZ", "scottsdale": "AZ", "tucson": "AZ",
    "minneapolis": "MN", "saint paul": "MN", "st paul": "MN",
    "detroit": "MI", "ann arbor": "MI",
    "new orleans": "LA", "baton rouge": "LA",
    "charleston": "SC", "raleigh": "NC", "charlotte": "NC",
    "asheville": "NC", "durham": "NC",
    "las vegas": "NV", "reno": "NV",
    "salt lake city": "UT",
    "kansas city": "MO", "st louis": "MO", "saint louis": "MO",
    "milwaukee": "WI", "madison": "WI",
    "indianapolis": "IN",
    "columbus": "OH", "cleveland": "OH", "cincinnati": "OH",
    "richmond": "VA", "alexandria": "VA",
    "providence": "RI",
    "honolulu": "HI",
    "anchorage": "AK",
    "albuquerque": "NM", "santa fe": "NM",
    "newark": "NJ", "jersey city": "NJ", "hoboken": "NJ",
}

NON_US_CITIES: set[str] = {
    "london", "paris", "tokyo", "toronto", "montreal", "vancouver",
    "mexico city", "cdmx", "berlin", "munich", "rome", "milan", "florence",
    "madrid", "barcelona", "amsterdam", "dubai", "singapore", "hong kong",
    "shanghai", "beijing", "bangkok", "seoul", "lisbon", "porto",
    "copenhagen", "stockholm", "vienna", "zurich", "buenos aires", "lima",
    "rio de janeiro", "sao paulo", "sydney", "melbourne", "dublin",
    "manchester", "edinburgh",
}


# -- Coercion helpers --------------------------------------------------------

def normalize_state(value: str | None) -> str:
    """Return 2-letter US state code if recognizable, else original trimmed string."""
    if not value:
        return ""
    v = str(value).strip()
    if not v:
        return ""
    upper = v.upper()
    if upper in US_STATES:
        return upper
    code = STATE_NAME_TO_CODE.get(v.lower())
    return code or v


def is_us_country(value: str | None) -> bool:
    if not value:
        return False
    v = str(value).strip().lower()
    return v in {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"}


_CITY_STATE_RE = re.compile(r"\s*([^,]+?)\s*,\s*([^,]+?)\s*$")


def parse_city_state(text: str) -> tuple[str, str]:
    """'Brooklyn, NY' / 'New York, New York' -> ('Brooklyn', 'NY')."""
    if not text:
        return ("", "")
    m = _CITY_STATE_RE.match(text)
    if not m:
        return (text.strip(), "")
    city = m.group(1).strip()
    state = normalize_state(m.group(2).strip())
    return (city, state)


# -- DataFrame filters -------------------------------------------------------

def filter_us(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows whose `country` column reads as US. No-op if column missing or empty."""
    if df.empty or "country" not in df.columns:
        return df
    return df[df["country"].fillna("").str.lower().isin(["us", "usa", "united states"])].copy()


def filter_banned_states(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose `state` is in BANNED_STATES. No-op if column missing or empty."""
    if df.empty or "state" not in df.columns:
        return df
    return df[~df["state"].fillna("").str.upper().isin(BANNED_STATES)].copy()


# -- City slicing ------------------------------------------------------------

def slice_cities(
    cities: Iterable[str] | None = None,
    state: str | None = None,
    max_cities: int = 0,
    *,
    drop_banned: bool = True,
    min_population: int = 0,
) -> list[tuple[str, str, str, int]]:
    """Return a filtered slice of TOP_US_CITIES.

    Args:
        cities: explicit list of city names (case-insensitive). Takes priority.
        state: 2-letter abbr or full name; keep only that state's cities.
        max_cities: cap the result at the first N (by population).
        drop_banned: drop cities whose state is in BANNED_STATES (default True).
        min_population: drop cities below this population threshold.

    Returns rows shaped like TOP_US_CITIES: (city, abbr, full_state, pop).
    """
    rows = list(TOP_US_CITIES)
    if drop_banned:
        rows = [r for r in rows if r[1] not in BANNED_STATES]
    if min_population:
        rows = [r for r in rows if r[3] >= min_population]
    if state:
        s = state.strip()
        if s.upper() in US_STATES:
            abbr = s.upper()
        else:
            abbr = STATE_ABBREVIATIONS.get(s.title()) or s.upper()
        rows = [r for r in rows if r[1] == abbr]
    if cities:
        want = {c.strip().lower() for c in cities}
        rows = [r for r in rows if r[0].lower() in want]
    if max_cities and max_cities > 0:
        rows = rows[:max_cities]
    return rows
