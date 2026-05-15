"""Filter raw_posts_800.json to only posts not in raw_posts_200.json."""
import json
import sys

prior = json.load(open("scrape_beli/raw_posts_200.json"))
big = json.load(open("scrape_beli/raw_posts_800.json"))

prior_codes = {p["shortCode"] for p in prior}
new = [p for p in big if p.get("shortCode") not in prior_codes]
print(f"Prior: {len(prior)}  Big: {len(big)}  New (not in prior): {len(new)}")

with open("scrape_beli/raw_posts_new_600.json", "w") as f:
    json.dump(new, f, indent=2, default=str)
print("Saved scrape_beli/raw_posts_new_600.json")

# date range
ts = sorted([p.get("timestamp") for p in new if p.get("timestamp")])
print(f"Date range: {ts[0]} -> {ts[-1]}")
