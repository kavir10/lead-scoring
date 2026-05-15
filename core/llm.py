"""
Anthropic client factory.

Three places in the repo currently re-implement the same init pattern:
  awards/llm_extract.py
  best_wine_shops/extractor.py
  scrape_beli/merge_and_finalize.py

Centralize here. Guards against the common gotcha where the shell sets an
empty ANTHROPIC_API_KEY (Claude Desktop side-effect) — `load_dotenv()`
won't override it, so we surface the issue clearly.

Default models:
  DEFAULT_MODEL    claude-sonnet-4-6           (editorial extraction quality)
  CHEAP_MODEL      claude-haiku-4-5-20251001   (high-volume / OCR / caption)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from . import ROOT


DEFAULT_MODEL = "claude-sonnet-4-6"
CHEAP_MODEL = "claude-haiku-4-5-20251001"


def _ensure_env_loaded() -> None:
    # Idempotent. Respects existing env vars (won't override).
    load_dotenv(dotenv_path=Path(ROOT) / ".env")


def anthropic_client(*, api_key: str | None = None):
    """Return an Anthropic SDK client, or None if the SDK / key is missing.

    Prints a clear message (not an exception) when the key is absent so
    callers can decide whether to no-op or hard-fail. Catches the
    empty-key-from-shell case and tells the user how to fix it.
    """
    _ensure_env_loaded()
    try:
        from anthropic import Anthropic
    except ImportError:
        print("  [llm] anthropic SDK not installed; skipping", flush=True)
        return None
    key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
    if not key.strip():
        print(
            "  [llm] ANTHROPIC_API_KEY not set (shell may have an empty "
            "override from Claude Desktop; run with "
            "`unset ANTHROPIC_API_KEY && ...`)",
            flush=True,
        )
        return None
    return Anthropic(api_key=key)
