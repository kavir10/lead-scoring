#!/usr/bin/env bash
# Whole-animal butcher list, end to end. Read LEARNINGS.md first.
# Inputs: output/candidates_v2.csv from build_whole_animal_list.py merge.
# Every step checkpoints to *.cache.jsonl, so a rerun resumes where it stopped.
# Run under `caffeinate -i` on macOS so sleep doesn't drop the network mid-run.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/verify_whole_animal.py output/candidates_v2.csv output/candidates_v2_verified.csv --concurrency 32
$PY scripts/instagram_whole_animal.py output/candidates_v2_verified.csv output/candidates_v2_ig.csv
$PY - <<'P'
import pandas as pd
d = pd.read_csv('output/candidates_v2_ig.csv', dtype=str)
s = d[(d.lead_source == 'new (directories)') & (d.wa_strength == 'strong')].copy()
s['city'] = s['city'].fillna('')
s[['name', 'website', 'city', 'state']].to_csv('output/dir_strong.csv', index=False)
print(f'{len(s)} directory rows need a Maps lookup')
P
$PY scripts/discover_whole_animal.py lookup output/dir_strong.csv output/dir_strong_maps.csv
$PY scripts/build_whole_animal_list.py attach-maps output/candidates_v2_ig.csv output/dir_strong_maps.csv output/candidates_v2_full.csv
$PY scripts/build_whole_animal_list.py filter output/candidates_v2_full.csv output/whole_animal_butchers_v2.csv
echo PIPELINE_DONE
