"""
Post-process: add `domain_tier` column to the output CSV.

  tier 1 — editorial publications (Food & Wine, VinePair, Eater, etc.)
  tier 2 — community/social (Reddit, Quora, Instagram, Facebook, Twitter, YouTube)
  tier 3 — everything else (Yelp lists, TripAdvisor, local biz directories, blogs)

Run:
    python -m best_wine_shops.tag_domain_tier output/best_wine_shops/best_wine_shops_20260515.csv
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

EDITORIAL_DOMAINS = {
    # Seeded
    "chowhound.com", "vinepair.com", "sokolin.com", "usawineratings.com",
    "foodandwine.com", "10best.usatoday.com", "usatoday.com", "imbibemagazine.com",
    # Major food/drink editorial
    "eater.com", "bonappetit.com", "nytimes.com", "saveur.com",
    "theinfatuation.com", "tastingtable.com", "seriouseats.com",
    "thrillist.com", "timeout.com", "wineenthusiast.com", "winemag.com",
    "decanter.com", "winespectator.com", "punchdrink.com",
    "wsj.com", "washingtonpost.com", "latimes.com", "sfgate.com",
    "sfchronicle.com", "chicagotribune.com", "bostonglobe.com",
    "houstonchronicle.com", "miamiherald.com", "seattletimes.com",
    "oregonlive.com", "denverpost.com", "azcentral.com",
    "philly.com", "inquirer.com", "njmonthly.com", "newyorker.com",
    "vogue.com", "gq.com", "esquire.com", "departures.com",
    "travelandleisure.com", "cntraveler.com", "robbreport.com",
    "forbes.com", "bloomberg.com", "time.com", "townandcountrymag.com",
    "afar.com", "thrillist.com", "vice.com", "munchies.tv", "grubstreet.com",
    "nymag.com", "vulture.com", "the-take.com", "secretnyc.co",
    "secretla.co", "secretchicago.com", "secrethouston.com",
    "washingtonian.com", "bostonmagazine.com", "phillymag.com",
    "chicagomag.com", "atlantamagazine.com", "5280.com",
    "sandiegomagazine.com", "modernluxury.com", "edibleseattle.com",
    "edibleboston.com", "edibledc.com", "edibleportland.com",
    "vinology.com", "winemag.com", "wineanorak.com", "tablemagazine.com",
    # Regional magazines & local editorials that appeared in this run
    "texasmonthly.com", "bkmag.com", "cbsnews.com", "nbcnews.com", "abcnews.go.com",
    "portlandfoodanddrink.com", "uncovercolorado.com", "onmilwaukee.com",
    "thewashingtonlobbyist.com", "gayot.com", "wsj.com", "axios.com",
    "houstoniamag.com", "atxwoman.com", "austinchronicle.com",
    "do512.com", "westword.com", "milehighmag.com", "5280.com",
    "miamimag.com", "miaminewtimes.com", "ocweekly.com", "laweekly.com",
    "lamag.com", "sfweekly.com", "sfmag.com", "boston.com",
    "improper.com", "metro.us", "voicemediagroup.com",
    "northjersey.com", "philadelphiamagazine.com",
    "njmonthly.com", "njdotcom.com", "nj.com",
    "dallasobserver.com", "dmagazine.com", "fwtx.com",
    "modernluxury.com", "edible-communities.com", "ediblemanhattan.com",
}

COMMUNITY_DOMAINS = {
    "reddit.com", "quora.com", "yelp.com", "tripadvisor.com",
    "instagram.com", "facebook.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com", "linkedin.com",
}


def _root_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    host = host.lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _registrable(host: str) -> str:
    """Crude TLD-aware reduction: bbc.co.uk -> bbc.co.uk; sub.eater.com -> eater.com."""
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # Common 2-level TLDs we care about (.co.uk etc.) — none in our set, simplify to last 2 parts.
    return ".".join(parts[-2:])


def classify(url: str) -> int:
    host = _root_domain(url)
    if not host:
        return 3
    reg = _registrable(host)
    if reg in EDITORIAL_DOMAINS or host in EDITORIAL_DOMAINS:
        return 1
    if reg in COMMUNITY_DOMAINS or host in COMMUNITY_DOMAINS:
        return 2
    return 3


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m best_wine_shops.tag_domain_tier <csv>")
        return 1
    path = Path(argv[1])
    df = pd.read_csv(path, dtype=str).fillna("")
    df["domain_tier"] = df["source_url"].map(classify).astype(int)
    df.to_csv(path, index=False)
    print(f"Tagged {path}")
    counts = df["domain_tier"].value_counts().sort_index()
    for tier, n in counts.items():
        label = {1: "editorial", 2: "community/social", 3: "other"}.get(int(tier), "?")
        print(f"  tier {tier} ({label}): {n}")
    print(f"  total: {len(df)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
