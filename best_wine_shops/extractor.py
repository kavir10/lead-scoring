"""
LLM extraction tuned for "best wine shops" editorial lists.

Extends the awards.llm_extract prompt with two extra fields:
  - is_online_only:  bool — article frames the shop as online/e-commerce-only.
  - is_large_indie:  bool — well-known multi-location / very high-volume indie.

We let the LLM set these heuristically; downstream filters in filters.py also
apply a name-based blocklist as a backstop.
"""
from __future__ import annotations

import json
import os
import re
import textwrap

from dotenv import load_dotenv

from awards._lib import normalize_state

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

MODEL = "claude-sonnet-4-6"

_SYSTEM = textwrap.dedent("""
You extract structured business listings from articles about the best wine
shops / wine retailers / wine merchants in the United States.

Return ONLY a JSON array (no prose, no markdown fences). Each element:

{
  "name": "<official business name>",
  "city": "<city only — no state, no country>",
  "state": "<2-letter US state code, or empty>",
  "country": "us | other",
  "distinction": "<the specific recognition this shop received in this article, e.g. 'VinePair 50 Best 2017 #12', 'Best Wine Shop in NYC', 'Food & Wine Best Wine Shop'>",
  "blurb": "<one-sentence reason given in the article, paraphrased — under 200 chars>",
  "is_online_only": true | false,
  "is_large_indie": true | false
}

Rules:
- ONLY include businesses the article specifically endorses, ranks, or lists.
  Skip passing mentions, comparisons, or background context.
- Do NOT invent cities or states. If the article doesn't say, leave them blank.
- Do NOT include the publication name itself.
- Map full state names to 2-letter codes ("California" -> "CA").
- "country": "us" if the business is in the United States; otherwise "other".
- "is_online_only": true ONLY if the article explicitly describes the shop as
  online-only / e-commerce-only with no physical retail (e.g. Wine Access,
  Last Bottle). If unclear, false.
- "is_large_indie": true if the shop is a well-known large independent —
  multi-location chains-of-one or very high-volume merchants (K&L Wines,
  Astor Wines, Zachys, Sherry-Lehmann, Flatiron, Italian Wine Merchants,
  Chambers Street Wines, Moore Brothers, Wally's, Acker, Hi-Time Wine
  Cellars, Bounty Hunter). Default false.
- EXCLUDE big-box / national chains (Total Wine, BevMo, Binny's, Spec's,
  Costco, Whole Foods, Trader Joe's, wine.com, Drizly, Vivino).
- If the article is region-specific (e.g. "Best Wine Shops in Chicago"), set
  city = "Chicago" and state = "IL" for entries with no other location given.
- If you cannot find any qualifying businesses, return [].
""").strip()


def _call_claude(text: str, hint: str) -> list[dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [llm] anthropic SDK not installed", flush=True)
        return []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [llm] ANTHROPIC_API_KEY not set (shell may have empty override; "
              "run with `unset ANTHROPIC_API_KEY && ...`)", flush=True)
        return []

    user = (f"Hint: {hint}\n\n" if hint else "") + "Article text:\n\n" + text
    try:
        msg = Anthropic(api_key=api_key).messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:
        print(f"  [llm] api error: {e}", flush=True)
        return []

    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    s, e = raw.find("["), raw.rfind("]")
    if s == -1 or e == -1 or e < s:
        print(f"  [llm] no JSON array in response (len={len(raw)})", flush=True)
        return []
    try:
        data = json.loads(raw[s : e + 1])
    except json.JSONDecodeError as err:
        print(f"  [llm] json decode error: {err}", flush=True)
        return []
    if not isinstance(data, list):
        return []

    out: list[dict] = []
    for d in data:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        out.append({
            "name": str(d.get("name", "")).strip(),
            "city": str(d.get("city", "")).strip(),
            "state": normalize_state(str(d.get("state", "")).strip()),
            "country": str(d.get("country", "us")).strip().lower() or "us",
            "distinction": str(d.get("distinction", "")).strip(),
            "blurb": str(d.get("blurb", "")).strip(),
            "is_online_only": bool(d.get("is_online_only", False)),
            "is_large_indie": bool(d.get("is_large_indie", False)),
        })
    return out


def extract_from_text(text: str, *, source_url: str, hint: str = "") -> list[dict]:
    rows = _call_claude(text, hint)
    for r in rows:
        r["source_url"] = source_url
    return [r for r in rows if r.get("country", "us") == "us"]
