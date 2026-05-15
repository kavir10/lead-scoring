"""Phase 2: Extract candidates from captions + tagged users using Claude."""
import argparse
import json
import os
import sys
import time

from anthropic import Anthropic, APIConnectionError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

# Hard non-US blocklist (cities, countries). Conservative — better to drop a US match
# than keep a London one. We only check post locationName, not free-text city guesses.
NON_US_LOCATION_TOKENS = [
    "united kingdom", "uk,", " uk ", "england", "scotland", "wales",
    "london", "manchester", "edinburgh", "dublin", "ireland",
    "paris", "france", "lyon", "marseille",
    "tokyo", "japan", "osaka", "kyoto",
    "sydney", "australia", "melbourne",
    "toronto", "canada", "montreal", "vancouver",
    "mexico city", "cdmx", "mexico,",
    "berlin", "germany", "munich", "hamburg",
    "rome", "italy", "milan", "florence",
    "madrid", "spain", "barcelona",
    "amsterdam", "netherlands",
    "dubai", "uae", "abu dhabi",
    "singapore", "hong kong", "shanghai", "beijing",
    "bangkok", "thailand",
    "seoul", "korea",
    "lisbon", "portugal", "porto",
    "copenhagen", "denmark", "stockholm", "sweden",
    "vienna", "austria",
    "zurich", "switzerland",
    "buenos aires", "argentina",
    "lima", "peru",
    "rio de janeiro", "brazil", "sao paulo",
]


def is_non_us_location(loc: str) -> bool:
    if not loc:
        return False
    s = f" {loc.lower()} "
    return any(tok in s for tok in NON_US_LOCATION_TOKENS)


SYSTEM_PROMPT = """You extract food & beverage business mentions from Instagram posts by @beli_eats (a US restaurant ranking app).

You receive:
- caption (text)
- tagged_users (list of {full_name, username})
- post_location (string or null)

Return a STRICT JSON object with this shape:
{
  "is_us_relevant": bool,
  "reason_if_skip": string|null,
  "candidates": [
    {
      "business_name": "Exact name as written",
      "ig_handle": "username or null if not in tagged list and not @-mentioned",
      "city": "Best inferred city, US format e.g. 'New York' / 'Brooklyn' / 'Chicago' / null",
      "state": "Two-letter US state code if confident else null",
      "cuisine": "Free text: italian, japanese pizza, ramen, cocktail bar, bakery, coffee, etc. Or null.",
      "type_signal": "neighborhood|destination|fast_casual|bakery|coffee|bar|dessert|other|unclear",
      "confidence": "high|med|low",
      "source": "tagged|caption|both"
    }
  ]
}

Rules:
- If the post is clearly about a non-US city (London, Paris, Tokyo, etc.), set is_us_relevant=false, reason_if_skip="non_us_<city>", candidates=[].
- Only include candidates that are actual F&B businesses (restaurants, bars, bakeries, coffee shops, dessert spots). Skip media outlets, photographers, the @beli_eats handle itself, generic mentions.
- If the caption splits by city (e.g., "Chicago: 1. X 2. Y\\nLA: 1. Z..."), assign each restaurant to its block's city.
- Match tagged_users to caption names by fuzzy similarity (handle suffix often hints city: 'deans.newyork' = New York; 'maillards.sf' = San Francisco; 'bome.coffee' is ambiguous, defer to caption block).
- For type_signal: 'destination' = high-end / hard-to-get-into / "best of" framing; 'neighborhood' = local gem / casual sit-down; 'fast_casual' = grab-and-go / counter-service. Default to 'unclear' when ambiguous.
- confidence='high' if tagged AND city resolved; 'med' if either tagged OR city resolved; 'low' if just caption mention.
- Output JSON only. No prose."""


def extract_post(post: dict) -> dict:
    """Run Claude extraction on a single post."""
    caption = post.get("caption") or ""
    tagged = [
        {"full_name": t.get("full_name", ""), "username": t.get("username", "")}
        for t in (post.get("taggedUsers") or [])
    ]
    location = post.get("locationName")
    short_code = post.get("shortCode")
    post_url = post.get("url") or f"https://www.instagram.com/p/{short_code}/"

    # Pre-filter cheap: if location is clearly non-US AND no tagged users with US handles,
    # we still let LLM decide because handle suffixes might save us.
    pre_skip = is_non_us_location(location or "") and not any(
        any(suf in t["username"].lower() for suf in ("nyc", ".sf", "boston", "chicago", "la", ".usa", "newyork"))
        for t in tagged
    )
    if pre_skip:
        return {
            "post_url": post_url,
            "shortCode": short_code,
            "is_us_relevant": False,
            "reason_if_skip": f"prefilter_non_us:{location}",
            "candidates": [],
        }

    user_msg = json.dumps({
        "caption": caption,
        "tagged_users": tagged,
        "post_location": location,
    }, ensure_ascii=False)

    last_err = None
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=8192,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_msg}],
            )
            break
        except (APIConnectionError, APIStatusError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/4 in {wait}s] {type(e).__name__}: {str(e)[:120]}", flush=True)
            time.sleep(wait)
    else:
        raise last_err
    raw = resp.content[0].text.strip()
    # strip markdown fences if model added them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON decode failed for {short_code}: {e}", flush=True)
        print(f"  raw: {raw[:300]}", flush=True)
        parsed = {"is_us_relevant": False, "reason_if_skip": "parse_error", "candidates": []}

    parsed["post_url"] = post_url
    parsed["shortCode"] = short_code
    return parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="raw_posts JSON")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = args.out or args.input.replace("raw_posts", "candidates_captions").replace(".json", ".json")

    with open(args.input) as f:
        posts = json.load(f)

    results = []
    for i, p in enumerate(posts):
        sc = p.get("shortCode")
        print(f"  [{i+1}/{len(posts)}] {sc}", flush=True)
        try:
            r = extract_post(p)
        except Exception as e:
            print(f"    [ERROR] {e}", flush=True)
            r = {"shortCode": sc, "post_url": p.get("url"), "is_us_relevant": False,
                 "reason_if_skip": f"exception:{e}", "candidates": []}
        n_cand = len(r.get("candidates") or [])
        skip = r.get("reason_if_skip")
        print(f"    -> us={r.get('is_us_relevant')} skip={skip} candidates={n_cand}", flush=True)
        results.append(r)

    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Saved -> {out_path}", flush=True)

    total = sum(len(r.get("candidates") or []) for r in results)
    print(f"  Total candidates: {total}", flush=True)


if __name__ == "__main__":
    main()
