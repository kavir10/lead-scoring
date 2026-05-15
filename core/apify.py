"""
Thin wrapper around ApifyClient.

Today every caller does the same dance:

    client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
    run = client.actor(ACTOR_ID).call(run_input={...})
    items = client.dataset(run["defaultDatasetId"]).list_items().items

Encapsulate it so future retries / timeouts / logging happen in one place.
"""
from __future__ import annotations

import os
from typing import Any


def apify_client():
    """Return an ApifyClient initialized from APIFY_API_TOKEN."""
    from apify_client import ApifyClient
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN missing from env / .env")
    return ApifyClient(token)


def run_actor(actor_id: str, run_input: dict[str, Any], *, client=None) -> list[dict[str, Any]]:
    """Run an Apify actor and return the dataset items.

    Args:
        actor_id: e.g. "apify/instagram-profile-scraper"
        run_input: actor input payload
        client: optional pre-built ApifyClient (caller may pool / reuse)

    Returns:
        list of dicts from the run's default dataset.
    """
    client = client or apify_client()
    run = client.actor(actor_id).call(run_input=run_input)
    return client.dataset(run["defaultDatasetId"]).list_items().items
