#!/usr/bin/env python3
"""Harvest well-formed lead rows from sub-agent transcripts.

Some research sub-agents returned qualified rows as text in their final
message instead of writing the target CSV (and could not be resumed). This
scans every agent JSONL transcript in the session tasks dir, pulls assistant
text, and recovers any line that parses as a valid lead row in our schema:

    name,city,STATE,website,vertical,source_strategy,source_url,evidence,date

Recovered rows are written per-vertical to
output/innovative_leads/<vertical>/harvested_subagents_<stamp>.csv so the
normal merge step folds + dedupes them. HTML entities are unescaped. Stdlib
only.
"""

import csv
import html
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "innovative_leads"
VERTICALS = {"restaurants", "butchers", "cheese", "bakeries", "wine"}
COLUMNS = [
    "name", "city", "state", "website", "vertical",
    "source_strategy", "source_url", "evidence", "date_added",
]
DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}\s*$")


def iter_assistant_text(jsonl_path: Path):
    try:
        raw = jsonl_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    yield blk.get("text", "")


def parse_row(line: str):
    line = html.unescape(line.strip())
    if "," not in line or not DATE_RE.search(line):
        return None
    try:
        fields = next(csv.reader(io.StringIO(line)))
    except (csv.Error, StopIteration):
        return None
    if len(fields) != len(COLUMNS):
        return None
    row = dict(zip(COLUMNS, (f.strip() for f in fields)))
    if row["vertical"] not in VERTICALS:
        return None
    if row["name"].lower() == "name" or not row["city"]:
        return None
    if not re.fullmatch(r"[A-Za-z]{2}", row["state"]):
        return None
    return row


def main() -> None:
    tasks_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if tasks_dir is None:
        # default: the session tasks dir under /tmp
        cands = list(Path("/tmp").glob("claude-*/**/tasks"))
        tasks_dir = cands[0] if cands else None
    if not tasks_dir or not tasks_dir.exists():
        sys.exit(f"tasks dir not found: {tasks_dir}")

    buckets: dict[str, list[dict]] = {v: [] for v in VERTICALS}
    seen: dict[str, set] = {v: set() for v in VERTICALS}
    files = sorted(set(p.resolve() for p in tasks_dir.glob("*.output")))
    for f in files:
        for text in iter_assistant_text(f):
            for line in text.splitlines():
                row = parse_row(line)
                if not row:
                    continue
                v = row["vertical"]
                key = (row["name"].lower(), row["city"].lower())
                if key in seen[v]:
                    continue
                seen[v].add(key)
                buckets[v].append(row)

    stamp = date.today().strftime("%Y%m%d")
    for v, rows in buckets.items():
        if not rows:
            continue
        out = BASE / v / f"harvested_subagents_{stamp}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"{v:12s} harvested {len(rows):4d} -> {out.name}")


if __name__ == "__main__":
    main()
