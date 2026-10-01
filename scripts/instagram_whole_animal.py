"""
Instagram-bio lane for the whole-animal butcher list.

Many shops say "whole animal butcher" only in their Instagram bio. For rows
in a verified CSV (verify_whole_animal.py output) whose website did not make
a strong claim but that link an Instagram handle, pull the bio with the Apify
profile scraper and grade it with the same rules as website snippets. Rows
whose bio grades "strong" are upgraded in place (wa_source = instagram_bio).

    python scripts/instagram_whole_animal.py VERIFIED.csv OUT.csv [--batch 200]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time

import pandas as pd
from apify_client import ApifyClient
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTOR_ID = "apify/instagram-profile-scraper"

_spec = importlib.util.spec_from_file_location("verify", os.path.join(ROOT, "scripts", "verify_whole_animal.py"))
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)


def _bio_snippets(bio: str) -> list[tuple[str, str]]:
    text = re.sub(r"\s+", " ", bio or "")
    snips = []
    for _, rx in verify.WHOLE_ANIMAL_PATTERNS:
        for m in rx.finditer(text):
            snips.append((verify._snippet(text, m), ""))
    return snips


def scrape_bios(usernames: list[str], batch: int, cache_path: str) -> pd.DataFrame:
    """Apify profile scrape, checkpointed per profile to JSONL so a dropped run resumes."""
    cols = ["instagram", "ig_bio", "ig_followers", "ig_url"]
    done: dict[str, dict] = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                rec = json.loads(line)
                done[rec["instagram"]] = rec
            except (ValueError, KeyError):
                continue
    todo = [u for u in usernames if u not in done]
    print(f"  {len(done)} profiles cached, {len(todo)} to fetch", file=sys.stderr)
    client = ApifyClient(os.environ["APIFY_API_TOKEN"])
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        print(f"  Apify batch {i // batch + 1}: {len(chunk)} profiles", file=sys.stderr, flush=True)
        for attempt in range(5):
            try:
                run = client.actor(ACTOR_ID).call(run_input={"usernames": chunk}, logger=None)
                # apify_client >= 2 returns a Run model; older versions return a dict.
                dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else run.default_dataset_id
                items = list(client.dataset(dataset_id).iterate_items())
                break
            except Exception as e:  # network drops surface as impit.ConnectError
                wait = 30 * (attempt + 1)
                print(f"  batch failed ({type(e).__name__}); retrying in {wait}s", file=sys.stderr, flush=True)
                time.sleep(wait)
        else:
            raise RuntimeError("Apify batch failed 5 times; rerun to resume from the cache")
        seen = set()
        with open(cache_path, "a") as fh:
            for item in items:
                u = str(item.get("username") or "").lower()
                if not u:
                    continue
                rec = {"instagram": u, "ig_bio": item.get("biography") or "",
                       "ig_followers": item.get("followersCount") or 0,
                       "ig_url": item.get("url") or f"https://www.instagram.com/{u}/"}
                done[u] = rec
                seen.add(u)
                fh.write(json.dumps(rec) + "\n")
            # Private/missing profiles return nothing; record them so reruns skip them.
            for u in set(chunk) - seen:
                rec = {"instagram": u, "ig_bio": "", "ig_followers": 0, "ig_url": ""}
                done[u] = rec
                fh.write(json.dumps(rec) + "\n")
    return pd.DataFrame([done[u] for u in usernames if u in done], columns=cols)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("verified")
    ap.add_argument("output")
    ap.add_argument("--batch", type=int, default=200)
    args = ap.parse_args()
    load_dotenv(os.path.join(ROOT, ".env"))

    d = pd.read_csv(args.verified, dtype=str)
    d["wa_source"] = d["wa_strength"].map(lambda s: "website" if s == "strong" else "")
    need = d[(d.wa_strength.fillna("") != "strong") & (d.instagram.fillna("") != "")]
    handles = sorted(set(need.instagram))
    print(f"{len(handles)} Instagram profiles to check", file=sys.stderr)

    bios = scrape_bios(handles, args.batch, args.output.rsplit(".", 1)[0] + ".cache.jsonl").drop_duplicates("instagram")
    graded = {}
    for r in bios.itertuples():
        snips = _bio_snippets(r.ig_bio)
        if snips:
            strength, (snip, _) = verify._grade(snips)
            graded[r.instagram] = (strength, snip, r.ig_url)
    print(f"{len(bios)} bios fetched, {len(graded)} mention whole animal / nose to tail, "
          f"{sum(1 for v in graded.values() if v[0] == 'strong')} strong", file=sys.stderr)

    upgraded = 0
    for idx in need.index:
        g = graded.get(d.at[idx, "instagram"])
        if g and g[0] == "strong":
            d.at[idx, "whole_animal"] = "True"
            d.at[idx, "wa_strength"] = "strong"
            d.at[idx, "wa_evidence"] = g[1]
            d.at[idx, "wa_evidence_url"] = g[2]
            d.at[idx, "wa_source"] = "instagram_bio"
            upgraded += 1
    d = d.merge(bios[["instagram", "ig_followers"]], on="instagram", how="left")
    d.to_csv(args.output, index=False)
    print(f"upgraded {upgraded} rows to strong from Instagram bios; wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
