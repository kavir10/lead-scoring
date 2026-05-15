"""Add post context columns to the final CSV:
- post_title:      first sentence of caption, cleaned, max ~120 chars
- post_type:       compilation / spotlight / video / other
- caption_full:    raw caption verbatim
- caption_summary: Haiku-sanitized 1-2 sentence summary (1 LLM call per unique post)
"""
import argparse
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from anthropic import Anthropic, APIConnectionError, APIStatusError
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

SUMMARY_SYSTEM = """You read Instagram captions from @beli_eats (a US restaurant ranking app) and produce a short, sanitized summary.

Rules:
- 1-2 sentences, max 30 words.
- No emojis. No hashtags. No "click here" / "see more" CTA fluff.
- Capture: post theme (e.g. "monthly best-of"), city/region, and what list or spot is featured.
- If non-US, still summarize accurately; downstream filtering handles location.
- Output the summary text only, no quotes, no preamble."""


def clean_first_sentence(caption: str, limit: int = 120) -> str:
    if not caption:
        return ""
    head = caption.split("\n\n", 1)[0]
    head = re.sub(r"\s+", " ", head).strip()
    head = head.rstrip(" .•")
    if len(head) > limit:
        head = head[:limit].rsplit(" ", 1)[0] + "…"
    return head


def classify_post(post: dict) -> str:
    caption = post.get("caption") or ""
    has_carousel = bool(post.get("childPosts"))
    is_video = (post.get("type") or "").lower() == "video"
    list_markers = ["1️⃣", "2️⃣", "3️⃣", "\n1.", "\n2.", "Top 5", "Top 10", "Top 15", "Top 20",
                    "the best", "the top", "ranking", "ranked", "list of"]
    has_list = any(m.lower() in caption.lower() for m in list_markers)
    if is_video and not has_carousel:
        return "video"
    if has_list and has_carousel:
        return "compilation"
    if has_carousel and not has_list:
        return "spotlight"
    if has_list:
        return "compilation"
    return "other"


def summarize_caption(caption: str) -> str:
    if not caption.strip():
        return ""
    last_err = None
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=120,
                system=[{"type": "text", "text": SUMMARY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": caption[:4000]}],
            )
            return resp.content[0].text.strip()
        except (APIConnectionError, APIStatusError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    print(f"    [summary err] {last_err}", flush=True)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--cache", default=None, help="JSON cache for summaries (avoid re-summarizing)")
    args = ap.parse_args()
    cache_path = args.cache or args.csv.replace(".csv", "_summary_cache.json")

    posts = json.load(open(args.raw))
    by_sc = {p["shortCode"]: p for p in posts}

    # Load existing summary cache
    summary_cache = {}
    if os.path.exists(cache_path):
        summary_cache = json.load(open(cache_path))

    # Read CSV
    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        existing_cols = reader.fieldnames or []

    # Determine which shortCodes appear in CSV (only summarize those — saves cost)
    needed_sc = sorted({r.get("shortCode") for r in rows if r.get("shortCode")})
    print(f"  Unique posts referenced in CSV: {len(needed_sc)}", flush=True)

    to_summarize = [sc for sc in needed_sc if sc not in summary_cache]
    print(f"  Need summaries for: {len(to_summarize)} (cached: {len(needed_sc) - len(to_summarize)})", flush=True)

    def _job(sc):
        post = by_sc.get(sc)
        cap = (post.get("caption") if post else "") or ""
        return sc, summarize_caption(cap) if cap else ""

    done = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(_job, sc) for sc in to_summarize]
        for fut in as_completed(futures):
            sc, s = fut.result()
            summary_cache[sc] = s
            done += 1
            if done % 20 == 0 or done == len(to_summarize):
                print(f"    [{done}/{len(to_summarize)}] {sc}: {s[:80]}", flush=True)
                with open(cache_path, "w") as f:
                    json.dump(summary_cache, f, indent=2, ensure_ascii=False)

    with open(cache_path, "w") as f:
        json.dump(summary_cache, f, indent=2, ensure_ascii=False)

    # Build output columns. Insert new cols before source_post_url.
    new_cols = ["post_type", "post_title", "caption_summary", "caption_full"]
    cols_out = [c for c in existing_cols if c not in new_cols]
    if "source_post_url" in cols_out:
        idx = cols_out.index("source_post_url")
        cols_out = cols_out[:idx] + new_cols + cols_out[idx:]
    else:
        cols_out += new_cols

    for r in rows:
        sc = r.get("shortCode")
        post = by_sc.get(sc)
        if post:
            cap = post.get("caption") or ""
            r["post_title"] = clean_first_sentence(cap)
            r["post_type"] = classify_post(post)
            r["caption_full"] = cap
            r["caption_summary"] = summary_cache.get(sc, "")
        else:
            for c in new_cols:
                r[c] = ""

    tmp = args.csv + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols_out, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, args.csv)
    print(f"  Updated {args.csv}: added {new_cols} to {len(rows)} rows", flush=True)

    from collections import Counter
    type_counts = Counter(r["post_type"] for r in rows)
    print(f"  by post_type: {dict(type_counts)}")


if __name__ == "__main__":
    main()
