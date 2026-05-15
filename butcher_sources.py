"""
Source-only butcher lead discovery.

Uses httpx + selectolax to scrape alternative source lanes. This intentionally
does not run Google/Serper discovery or any enrichment phases.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import pandas as pd

from core.geo import BANNED_STATES, STATE_SLUGS
from core.http_fetch import HEADERS

try:
    import httpx
    from selectolax.parser import HTMLParser
except ImportError:  # pragma: no cover - runtime guard for missing deps.
    httpx = None
    HTMLParser = None

GOOD_MEAT_FINDER_URL = "https://goodmeatproject.org/finder"
GOOD_FOOD_CHARCUTERIE_URL = "https://goodfoodfdn.org/awards/winners/2025/charcuterie/"
AGA_URL = "https://www.americangrassfed.org/aga-membership/producer-members/"
EATWILD_BASE = "https://www.eatwild.com/products/"

# Butcher/meat-specific directories (EatWild equivalents) — verified working
REAL_ORGANIC_URL = "https://realorganicproject.org/directory/"
NMPAN_STATE_HELP_URL = "https://www.nichemeatprocessing.org/state-help/"
AMERICAN_LAMB_URL = "https://americanlamb.com/where-to-buy/"

STOCKIST_URLS = [
    # Grass-fed beef / heritage ranches
    "https://whiteoakpastures.com/pages/where-to-buy",
    "https://www.nimanranch.com/where-to-buy/",
    "https://porterroad.com/pages/where-to-buy",
    "https://grasslandbeef.com/where-to-buy",
    "https://www.dartagnan.com/where-to-buy.html",
    "https://www.creekstonefarms.com/where-to-buy/",
    "https://joyce-farms.com/pages/where-to-buy",
    "https://www.marinsunfarms.com/locations",
    "https://www.thomasfarms.com/where-to-buy/",
    "https://www.alderspring.com/pages/where-to-buy",
    "https://forceofnaturemeats.com/pages/store-locator",
    "https://teton-waters-ranch.com/pages/store-locator",
    # Heritage pork / charcuterie producers + importers
    "https://laquercia.us/pages/find-our-products",
    "https://olympiaprovisions.com/pages/find-our-products",
    "https://smokinggoose.com/pages/store-locator",
    "https://framani.com/where-to-buy/",
    "https://www.charlitoscocina.com/pages/find-us",
    "https://www.brooklyncured.com/find-us",
    "https://heritagefoodsusa.com/where-to-buy",
    "https://www.fossilfarms.com/pages/where-to-buy",
    "https://www.berkshirepork.com/where-to-buy/",
    # Wagyu / premium beef importers
    "https://snakeriverfarms.com/pages/where-to-buy",
    "https://mishimareserve.com/pages/where-to-buy",
    "https://holygrailsteak.com/pages/where-to-buy",
    # Lamb / specialty
    "https://www.shepherdsongfarm.com/where-to-buy/",
    "https://anderson-ranches.com/where-to-buy/",
]

FARMERS_MARKET_URLS = [
    # NYC / Northeast
    "https://www.grownyc.org/greenmarket/our-farmers",
    "https://www.grownyc.org/greenmarket/manhattan/union-square-monday",
    "https://www.thefoodtrust.org/headhouse-farmers-market",
    # Boston / New England
    "https://bostonpublicmarket.org/our-vendors/",
    "https://copleysquaremarket.com/vendors/",
    "https://www.somervillefarmersmarket.org/vendors",
    # Mid-Atlantic / DC
    "https://easternmarket-dc.org/find-vendors",
    "https://freshfarm.org/vendors/",
    # Bay Area / West Coast
    "https://cuesa.org/vendors",
    "https://www.smgov.net/portals/farmersmarket/",
    "https://www.farmernet.com/markets/hollywood-farmers-market",
    "https://www.portlandfarmersmarket.org/our-vendors/",
    "https://sfmtafarmersmarket.org/vendors/",
    # Midwest
    "https://dcfm.org/vendors/",
    "https://www.greencitymarket.org/vendors",
    "https://www.minneapolisfarmersmarket.com/vendors",
    # South
    "https://www.crescentcityfarmersmarket.org/vendors",
    "https://www.peachtreeroadfarmersmarket.com/vendors",
    "https://www.austinfarmersmarket.org/vendors",
]

PHONE_RE = re.compile(r"(?<!\d)(?:\+1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
STATE_RE = re.compile(r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b")
NOISE_NAME_RE = re.compile(
    r"\b(home|about|contact|privacy|terms|facebook|instagram|twitter|youtube|"
    r"sign up|newsletter|donate|cart|shop|search|menu|learn more)\b",
    re.I,
)

PREMIUM_SIGNAL_PATTERNS = {
    "pasture_raised": re.compile(r"\bpasture[- ]raised\b|\bpastured\b", re.I),
    "heritage_breed": re.compile(r"\bheritage\b|\bberkshire\b|\bmangalitsa\b|\btamworth\b|\bduroc\b|\bwagyu\b", re.I),
    "dry_aged": re.compile(r"\bdry[- ]aged\b", re.I),
    "whole_animal": re.compile(r"\bwhole[- ]animal\b|\bnose[- ]to[- ]tail\b", re.I),
    "grass_fed": re.compile(r"\bgrass[- ]fed\b|\bgrass[- ]finished\b", re.I),
    "online_ordering": re.compile(r"\bshop online\b|\bonline (?:order|store|shop)\b|\border online\b", re.I),
    "csa_meat_share": re.compile(r"\bCSA\b|\bmeat share\b|\bmeat box\b|\bsubscription\b|\bmonthly box\b", re.I),
    "pickup": re.compile(r"\bpick[- ]up\b|\bpickup location\b|\bfarm pickup\b", re.I),
    "holiday_preorder": re.compile(r"\bholiday (?:pre)?order\b|\bthanksgiving (?:turkey|preorder)\b", re.I),
    "email_capture": re.compile(r"\bnewsletter\b|\bemail list\b|\bsubscribe\b|\bsign up\b", re.I),
    "charcuterie": re.compile(r"\bcharcuterie\b|\bsalumi\b|\bsalami\b|\bprosciutto\b|\bsmoked\b", re.I),
}


def _premium_signals(text: str) -> str:
    if not text:
        return ""
    hits = [name for name, pattern in PREMIUM_SIGNAL_PATTERNS.items() if pattern.search(text)]
    return "|".join(hits)


@dataclass
class ScrapeResult:
    rows: list[dict]
    status: dict


def _require_scraper_deps() -> None:
    if httpx is None or HTMLParser is None:
        raise RuntimeError(
            "Missing scraper dependencies. Run `.venv/bin/pip install -r requirements.txt` "
            "after approval is available; source scraping requires httpx and selectolax."
        )


def _client() -> "httpx.Client":
    _require_scraper_deps()
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30)


def _tree(html: str) -> "HTMLParser":
    _require_scraper_deps()
    return HTMLParser(html)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _clean_name(name: str) -> str:
    name = _clean_text(re.sub(r"\s*\[[^\]]+\]", "", name or ""))
    name = re.sub(r"^(visit|website|email|phone|contact)\s+", "", name, flags=re.I)
    return name.strip(" :-|")


def _valid_name(name: str) -> bool:
    return 3 <= len(name) <= 90 and not NOISE_NAME_RE.search(name)


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _external_url(base_url: str, href: str) -> str:
    if not href or href.startswith(("mailto:", "tel:", "#")):
        return ""
    url = urljoin(base_url, href)
    host = _domain(url)
    base_host = _domain(base_url)
    if not host or host == base_host:
        return ""
    return url


def _state_from_text(text: str, default_state: str = "") -> str:
    match = STATE_RE.search(text or "")
    return match.group(1) if match else default_state


def _row(
    *,
    name: str,
    source: str,
    source_url: str,
    state: str = "",
    city: str = "",
    website: str = "",
    phone: str = "",
    email: str = "",
    description: str = "",
) -> dict:
    cleaned_desc = _clean_text(description)[:1000]
    signals = _premium_signals(f"{name} {cleaned_desc}")
    return {
        "name": _clean_name(name),
        "business_type": "butcher",
        "butcher_source": source,
        "source": source,
        "source_url": source_url,
        "city": city,
        "state": state,
        "website": website,
        "phone": phone,
        "email": email,
        "description": cleaned_desc,
        "premium_signals": signals,
        "premium_signal_count": len(signals.split("|")) if signals else 0,
    }


def _rows_from_external_links(html: str, base_url: str, source: str, default_state: str = "") -> list[dict]:
    tree = _tree(html)
    rows = []
    seen = set()
    for link in tree.css("a[href]"):
        href = link.attributes.get("href", "")
        website = _external_url(base_url, href)
        if not website:
            continue
        text = _clean_text(link.text())
        parent = link.parent
        context = _clean_text(parent.text()) if parent else text
        name = _clean_name(text or _domain(website).split(".")[0].replace("-", " ").title())
        if not _valid_name(name):
            continue
        key = (_domain(website), name.lower())
        if key in seen:
            continue
        seen.add(key)
        phone = (PHONE_RE.search(context) or [""])[0] if PHONE_RE.search(context) else ""
        email = (EMAIL_RE.search(context) or [""])[0] if EMAIL_RE.search(context) else ""
        rows.append(_row(
            name=name,
            source=source,
            source_url=base_url,
            state=_state_from_text(context, default_state),
            website=website,
            phone=phone,
            email=email,
            description=context,
        ))
    return rows


def _extract_json_candidates(html: str) -> list[object]:
    """Extract parseable JSON blobs from script tags."""
    tree = _tree(html)
    out = []
    for script in tree.css("script"):
        text = script.text() or ""
        if not text.strip():
            continue
        if script.attributes.get("type") == "application/ld+json":
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError:
                pass
        if "__NEXT_DATA__" in script.attributes.get("id", ""):
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    return out


def _walk_json(value) -> list[dict]:
    rows = []
    if isinstance(value, dict):
        keys = {str(k).lower(): k for k in value}
        name_key = next((keys[k] for k in ["name", "title", "businessname", "business_name"] if k in keys), None)
        url_key = next((keys[k] for k in ["url", "website", "websiteurl", "website_url"] if k in keys), None)
        if name_key:
            rows.append(value)
        for child in value.values():
            rows.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_walk_json(child))
    return rows


def scrape_good_meat_finder(client: "httpx.Client") -> ScrapeResult:
    url = GOOD_MEAT_FINDER_URL
    resp = client.get(url)
    rows = _rows_from_external_links(resp.text, url, "good_meat_finder")
    for blob in _extract_json_candidates(resp.text):
        for item in _walk_json(blob):
            name = item.get("name") or item.get("title") or item.get("businessName") or item.get("business_name")
            website = item.get("website") or item.get("url") or item.get("websiteUrl") or item.get("website_url") or ""
            if name and _valid_name(str(name)):
                rows.append(_row(
                    name=str(name),
                    source="good_meat_finder",
                    source_url=url,
                    state=str(item.get("state") or item.get("region") or ""),
                    city=str(item.get("city") or ""),
                    website=str(website),
                    phone=str(item.get("phone") or ""),
                    email=str(item.get("email") or ""),
                    description=json.dumps(item, ensure_ascii=True)[:1000],
                ))
    return ScrapeResult(rows=rows, status={"source": "good_meat_finder", "url": url, "status": resp.status_code, "rows": len(rows)})


def scrape_eatwild(client: "httpx.Client", *, states_filter: set[str] | None = None) -> ScrapeResult:
    """Scrape EatWild's per-state pages.

    If `states_filter` is provided (set of 2-letter codes), restrict to those
    states; otherwise iterate all non-banned states.
    """
    rows = []
    statuses = []
    state_items = [(abbr, name, slug) for abbr, (name, slug) in STATE_SLUGS.items() if abbr not in BANNED_STATES]
    if states_filter:
        wanted = {s.upper() for s in states_filter}
        state_items = [item for item in state_items if item[0] in wanted]
    for abbr, state_name, slug in state_items:
        url = urljoin(EATWILD_BASE, f"{slug}.html")
        try:
            resp = client.get(url)
            state_rows = _rows_from_external_links(resp.text, url, "eatwild", default_state=abbr)
            for r in state_rows:
                if not r["state"]:
                    r["state"] = abbr
                if state_name.lower() not in r["description"].lower():
                    r["description"] = f"{state_name}. {r['description']}"
            rows.extend(state_rows)
            statuses.append({"source": "eatwild", "url": url, "status": resp.status_code, "rows": len(state_rows)})
        except Exception as exc:
            statuses.append({"source": "eatwild", "url": url, "status": "error", "rows": 0, "error": str(exc)})
    return ScrapeResult(rows=rows, status={"source": "eatwild", "url": EATWILD_BASE, "status": "multi", "rows": len(rows), "pages": statuses})


def scrape_good_food_awards(client: "httpx.Client") -> ScrapeResult:
    url = GOOD_FOOD_CHARCUTERIE_URL
    resp = client.get(url)
    rows = []
    if resp.status_code == 200 and "Cloudflare" not in resp.text[:2000]:
        tree = _tree(resp.text)
        for heading in tree.css("h2,h3,h4"):
            name = _clean_name(heading.text())
            if _valid_name(name):
                parent = heading.parent
                context = _clean_text(parent.text()) if parent else name
                rows.append(_row(name=name, source="good_food_awards", source_url=url, description=context))
    return ScrapeResult(rows=rows, status={"source": "good_food_awards", "url": url, "status": resp.status_code, "rows": len(rows)})


def scrape_aga(client: "httpx.Client") -> ScrapeResult:
    url = AGA_URL
    resp = client.get(url)
    rows = _rows_from_external_links(resp.text, url, "aga")
    return ScrapeResult(rows=rows, status={"source": "aga", "url": url, "status": resp.status_code, "rows": len(rows)})


MEAT_VENDOR_RE = re.compile(
    r"\b(meat|butcher|beef|pork|lamb|poultry|chicken|sausage|charcuterie|salumi|"
    r"farm|ranch|livestock|cattle|hog|pasture|grass[- ]fed|heritage|wagyu|bison)\b",
    re.I,
)

CERTIFICATION_NOISE_RE = re.compile(
    r"\b(certified|certification|approved|verified|standard|label|usda organic|"
    r"animal welfare|food alliance|demeter|grain millers|naturally grown|"
    r"environmental assurance|humane raised|bloom check|seal|logo|badge)\b",
    re.I,
)


def _scrape_simple_directory(
    client: "httpx.Client",
    urls: list[str],
    source_name: str,
    meat_filter: bool = False,
) -> ScrapeResult:
    """Generic scraper for directory pages where leads are external <a> links.

    If meat_filter is True, restrict to rows whose name+description matches MEAT_VENDOR_RE
    (for multi-category directories like Eat Well Guide / LocalHarvest catch-all pages).
    """
    rows = []
    statuses = []
    for url in urls:
        try:
            resp = client.get(url)
            page_rows = _rows_from_external_links(resp.text, url, source_name)
            if meat_filter:
                page_rows = [
                    r for r in page_rows
                    if MEAT_VENDOR_RE.search(f"{r['name']} {r['description']}")
                    and not CERTIFICATION_NOISE_RE.search(r["name"])
                ]
            rows.extend(page_rows)
            statuses.append({"source": source_name, "url": url, "status": resp.status_code, "rows": len(page_rows)})
        except Exception as exc:
            statuses.append({"source": source_name, "url": url, "status": "error", "rows": 0, "error": str(exc)})
    return ScrapeResult(
        rows=rows,
        status={"source": source_name, "url": "curated", "status": "multi", "rows": len(rows), "pages": statuses},
    )


def scrape_real_organic(client: "httpx.Client") -> ScrapeResult:
    """Real Organic Project directory — external 'Buy Now' links point to farm shops."""
    return _scrape_simple_directory(client, [REAL_ORGANIC_URL], "real_organic", meat_filter=True)


def scrape_niche_meat_processors(client: "httpx.Client") -> ScrapeResult:
    """NMPAN State Help page — external links to state meat associations + processors."""
    return _scrape_simple_directory(client, [NMPAN_STATE_HELP_URL], "nmpan")


def scrape_american_lamb(client: "httpx.Client") -> ScrapeResult:
    return _scrape_simple_directory(client, [AMERICAN_LAMB_URL], "american_lamb")


def scrape_farmers_markets(client: "httpx.Client") -> ScrapeResult:
    rows = []
    statuses = []
    for url in FARMERS_MARKET_URLS:
        try:
            resp = client.get(url)
            page_rows = _rows_from_external_links(resp.text, url, "farmers_market")
            # Filter to vendors that look like meat businesses (page has produce/flowers/cheese too)
            # and exclude certification/badge links that the page may also list.
            meat_rows = [
                r for r in page_rows
                if MEAT_VENDOR_RE.search(f"{r['name']} {r['description']}")
                and not CERTIFICATION_NOISE_RE.search(r["name"])
            ]
            rows.extend(meat_rows)
            statuses.append({
                "source": "farmers_market",
                "url": url,
                "status": resp.status_code,
                "rows": len(meat_rows),
            })
        except Exception as exc:
            statuses.append({"source": "farmers_market", "url": url, "status": "error", "rows": 0, "error": str(exc)})
    return ScrapeResult(rows=rows, status={"source": "farmers_market", "url": "curated", "status": "multi", "rows": len(rows), "pages": statuses})


def scrape_stockist_pages(client: "httpx.Client") -> ScrapeResult:
    rows = []
    statuses = []
    for url in STOCKIST_URLS:
        try:
            resp = client.get(url)
            page_rows = _rows_from_external_links(resp.text, url, "stockist_page")
            rows.extend(page_rows)
            statuses.append({"source": "stockist_page", "url": url, "status": resp.status_code, "rows": len(page_rows)})
        except Exception as exc:
            statuses.append({"source": "stockist_page", "url": url, "status": "error", "rows": 0, "error": str(exc)})
    return ScrapeResult(rows=rows, status={"source": "stockist_page", "url": "curated", "status": "multi", "rows": len(rows), "pages": statuses})


def dedupe_source_rows(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df[df["name"].fillna("").map(_valid_name)]
    df = df[~df["state"].isin(BANNED_STATES)]
    df["domain"] = df["website"].fillna("").map(_domain)
    df["dedupe_key"] = df.apply(
        lambda r: r["domain"] if r["domain"] else f"{r['name'].lower()}|{r.get('state', '')}",
        axis=1,
    )
    df = df.sort_values(["domain", "name"]).drop_duplicates("dedupe_key", keep="first")
    return df.drop(columns=["dedupe_key"]).reset_index(drop=True)


SUBSCRIPTION_PATTERNS = {
    # Tied to product / box / program context — excludes generic "subscribe to newsletter" noise.
    "subscription": re.compile(
        r"\b(?:meat|beef|pork|lamb|poultry|chicken|farm|ranch|butcher)\s+subscription\b"
        r"|\bsubscription\s+(?:box|service|program|members?|plan)\b"
        r"|\brecurring (?:order|delivery|box|shipment)\b"
        r"|\bauto[- ]?ship\b",
        re.I,
    ),
    "meat_club": re.compile(r"\bmeat club\b|\bbutcher(?:'s)? club\b|\bfarm club\b|\bbeef club\b|\bpork club\b|\bsteak club\b", re.I),
    "meat_share_csa": re.compile(r"\bCSA\b|\bmeat share\b|\bbeef share\b|\bpork share\b|\bbuying club\b|\bherd share\b", re.I),
    "monthly_box": re.compile(r"\bmonthly box\b|\bmeat box\b|\bbox of (?:beef|meat|pork|lamb)\b|\bquarterly box\b|\bcurated box\b", re.I),
    "membership": re.compile(r"\b(?:meat|beef|farm|ranch|butcher)\s+members?(?:hip)?\b|\bbecome a member\b|\bmembers? only\b", re.I),
}

CONTACT_PAGE_HINTS = re.compile(r"contact|about", re.I)


def _extract_vendor_signals(html: str) -> dict:
    """Pull contact info and subscription/club markers from a vendor homepage."""
    text = html or ""
    # Strip script/style to reduce noise
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    visible = _clean_text(re.sub(r"<[^>]+>", " ", text))

    phones = list(dict.fromkeys(PHONE_RE.findall(visible)))[:3]
    emails = list(dict.fromkeys(EMAIL_RE.findall(visible)))
    # Filter common asset/CDN false positives
    emails = [e for e in emails if not e.lower().endswith((".png", ".jpg", ".svg", ".webp", ".gif"))][:3]

    sub_hits = [name for name, pat in SUBSCRIPTION_PATTERNS.items() if pat.search(visible)]
    return {
        "site_phone": phones[0] if phones else "",
        "site_phones_all": "|".join(phones),
        "site_email": emails[0] if emails else "",
        "site_emails_all": "|".join(emails),
        "has_subscription_offering": bool(sub_hits),
        "subscription_signals": "|".join(sub_hits),
    }


def verify_vendor_websites(df: pd.DataFrame, max_workers: int = 12, timeout: float = 10.0) -> pd.DataFrame:
    """Fetch each unique vendor homepage; extract contact info + subscription/club signals.

    Bounded lightweight pass: one HEAD-like GET per unique website, concurrent, short timeout.
    """
    if df.empty or "website" not in df.columns:
        return df

    from concurrent.futures import ThreadPoolExecutor, as_completed

    sites = sorted({w for w in df["website"].fillna("").tolist() if w.startswith("http")})
    print(f"  Verifying {len(sites)} unique vendor websites (contact info + subscription detection)...")

    results: dict[str, dict] = {}

    def fetch(url: str) -> tuple[str, dict]:
        try:
            with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=timeout) as c:
                r = c.get(url)
            if r.status_code == 200 and r.text:
                return url, {**_extract_vendor_signals(r.text), "site_status": r.status_code}
            return url, {"site_status": r.status_code}
        except Exception as exc:
            return url, {"site_status": "error", "site_error": str(exc)[:80]}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch, u): u for u in sites}
        done = 0
        for fut in as_completed(futures):
            url, data = fut.result()
            results[url] = data
            done += 1
            if done % 50 == 0:
                print(f"    ...{done}/{len(sites)}")

    enrich_df = pd.DataFrame.from_dict(results, orient="index").reset_index().rename(columns={"index": "website"})
    merged = df.merge(enrich_df, on="website", how="left")
    return merged


def run_butcher_source_scrape(
    output_dir: str,
    *,
    states_filter: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run all butcher source scrapers; optionally restrict per-state scrapers
    (EatWild) to a subset.

    Args:
        output_dir: directory to write CSV outputs.
        states_filter: optional set of 2-letter state codes. Only affects
            sources that iterate per state (currently just EatWild). National
            directory sources (Good Meat Finder, AGA, stockist pages) always
            run in full because they aren't state-sliced.
    """
    os.makedirs(output_dir, exist_ok=True)
    raw_rows = []
    status_rows = []
    with _client() as client:
        for fn in [
            scrape_good_meat_finder,
            lambda c: scrape_eatwild(c, states_filter=states_filter),
            scrape_good_food_awards,
            scrape_aga,
            scrape_stockist_pages,
            scrape_farmers_markets,
            scrape_real_organic,
            scrape_niche_meat_processors,
            scrape_american_lamb,
        ]:
            result = fn(client)
            raw_rows.extend(result.rows)
            status = result.status.copy()
            pages = status.pop("pages", None)
            status_rows.append(status)
            if pages:
                status_rows.extend(pages)

    raw_df = pd.DataFrame(raw_rows)
    deduped_df = dedupe_source_rows(raw_rows)
    status_df = pd.DataFrame(status_rows)

    # Per-vendor homepage fetch: contact info + subscription/club signals
    deduped_df = verify_vendor_websites(deduped_df)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_df.to_csv(os.path.join(output_dir, f"source_raw_butchers_{stamp}.csv"), index=False)
    deduped_df.to_csv(os.path.join(output_dir, f"source_discovered_butchers_{stamp}.csv"), index=False)
    deduped_df.to_csv(os.path.join(output_dir, "1_discovered_butchers.csv"), index=False)
    status_df.to_csv(os.path.join(output_dir, f"source_scrape_status_{stamp}.csv"), index=False)

    return deduped_df, status_df
