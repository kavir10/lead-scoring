"""
American Cheesemonger Invitational. Note: as of writing this is often the same
event as CMI; we keep the module so future organizers can be tracked separately.
"""
from __future__ import annotations

import pandas as pd

from awards._lib import to_dataframe


def scrape(**_kwargs) -> pd.DataFrame:
    print("  [american_cmi] stub — assumed alias of cheesemonger_invitational; confirm with American Cheese Society", flush=True)
    return to_dataframe([])
