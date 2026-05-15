"""Phase 3: OCR carousel slides via Claude Vision to extract on-image business mentions."""
import argparse
import base64
import json
import os
import time
from pathlib import Path

import requests
from anthropic import Anthropic, APIConnectionError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(OUT_DIR, "images")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

OCR_SYSTEM = """You read Instagram carousel slides from @beli_eats and extract F&B businesses visible on-screen.

Return STRICT JSON: {"is_intro_or_cover": bool, "items": [{"business_name": str, "ig_handle": str|null, "city": str|null, "cuisine": str|null}]}

Rules:
- Read ALL visible business names on the slide. Beli often shows ranked lists or single-spot features.
- ig_handle: only extract if visible on the slide (e.g. shown as "@username"). Strip the @.
- city: read from slide if shown (e.g. "NYC", "Chicago"). Map abbreviations: NYC->New York, LA->Los Angeles, SF->San Francisco, DC->Washington.
- If slide is a cover / intro / outro / brand title with no specific business, set is_intro_or_cover=true and items=[].
- Skip the @beli_eats brand itself.
- Output JSON only."""


def download_image(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"    [download err] {e}", flush=True)
        return False


def ocr_image(image_path: Path) -> dict:
    img_b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
    last_err = None
    for attempt in range(4):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=[{"type": "text", "text": OCR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                        {"type": "text", "text": "Extract businesses from this slide."},
                    ],
                }],
            )
            break
        except (APIConnectionError, APIStatusError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/4 in {wait}s] {type(e).__name__}", flush=True)
            time.sleep(wait)
    else:
        raise last_err
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [parse err] {e} raw={raw[:200]}", flush=True)
        return {"is_intro_or_cover": False, "items": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="raw_posts JSON")
    ap.add_argument("--captions", required=True, help="candidates_captions JSON (used to skip non-US posts)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = args.out or args.raw.replace("raw_posts", "candidates_ocr").replace(".json", ".json")

    posts = json.load(open(args.raw))
    cap_results = {r["shortCode"]: r for r in json.load(open(args.captions))}

    all_results = []
    for i, p in enumerate(posts):
        sc = p["shortCode"]
        post_url = p.get("url") or f"https://www.instagram.com/p/{sc}/"
        cap = cap_results.get(sc, {})

        # skip non-US (already filtered in caption phase)
        if not cap.get("is_us_relevant"):
            print(f"  [{i+1}/{len(posts)}] {sc} SKIP non-US", flush=True)
            all_results.append({"shortCode": sc, "post_url": post_url, "skipped": "non_us", "slides": []})
            continue

        children = p.get("childPosts") or []
        if not children:
            print(f"  [{i+1}/{len(posts)}] {sc} SKIP no carousel", flush=True)
            all_results.append({"shortCode": sc, "post_url": post_url, "skipped": "no_carousel", "slides": []})
            continue

        post_dir = Path(IMG_DIR) / sc
        post_dir.mkdir(parents=True, exist_ok=True)

        slide_results = []
        print(f"  [{i+1}/{len(posts)}] {sc} OCR'ing {len(children)} slides", flush=True)
        for j, ch in enumerate(children):
            url = ch.get("displayUrl")
            if not url:
                continue
            dest = post_dir / f"slide_{j:02d}.jpg"
            if not download_image(url, dest):
                continue
            try:
                r = ocr_image(dest)
            except Exception as e:
                print(f"    slide {j}: [error] {e}", flush=True)
                r = {"is_intro_or_cover": False, "items": []}
            n = len(r.get("items") or [])
            tag = "cover" if r.get("is_intro_or_cover") else f"{n} items"
            print(f"    slide {j:2d}: {tag}", flush=True)
            slide_results.append({"slide_index": j, "image_url": url, **r})
            time.sleep(0.2)  # gentle rate-limit

        all_results.append({
            "shortCode": sc,
            "post_url": post_url,
            "slides": slide_results,
        })

    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"  Saved -> {out_path}", flush=True)

    total_items = sum(len(s.get("items") or []) for r in all_results for s in r.get("slides", []))
    print(f"  Total OCR items: {total_items}", flush=True)


if __name__ == "__main__":
    main()
