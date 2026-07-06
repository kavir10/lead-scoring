#!/usr/bin/env python3
"""Environment & wiring smoke test for the lead-scoring repo.

Run this BEFORE launching any pipeline that costs money. It makes **no API
calls and spends nothing** — it only checks that:

  * the required Python packages are installed,
  * `config.py` loads and has the structures the pipelines expect,
  * the core pipeline modules import without error (catches syntax breaks),
  * the awards / directories / jobs source registries load and are well-formed,

and then reports which `.env` API keys are set (informational only).

Usage:
    python tests/smoke_test.py

Exit code 0 = all required checks passed; 1 = something is broken.
This is intentionally dependency-free (no pytest needed).
"""

import importlib
import os
import sys
from pathlib import Path

# Make the repo root importable no matter where this is run from.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASS, FAIL, WARN, INFO = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m", "\033[93mWARN\033[0m", "INFO"
_failures = 0


def check(label, fn, *, warn_only=False):
    """Run fn(); print PASS/FAIL/WARN. Returns fn()'s value or None on error."""
    global _failures
    try:
        result = fn()
        detail = f" — {result}" if isinstance(result, str) else ""
        print(f"  [{PASS}] {label}{detail}")
        return result
    except Exception as e:  # noqa: BLE001 - smoke test wants every failure surfaced
        tag = WARN if warn_only else FAIL
        print(f"  [{tag}] {label} — {type(e).__name__}: {e}")
        if not warn_only:
            _failures += 1
        return None


# --- 1. Python version -------------------------------------------------------
print("\nPython:")
check(
    "Python >= 3.10",
    lambda: (
        f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.version_info >= (3, 10)
        else (_ for _ in ()).throw(RuntimeError(f"found {sys.version.split()[0]}"))
    ),
    warn_only=True,
)

# --- 2. Third-party dependencies --------------------------------------------
print("\nDependencies (from requirements.txt):")
DEPS = {
    "requests": "requests",
    "httpx": "httpx",
    "selectolax": "selectolax",
    "bs4": "beautifulsoup4",
    "pandas": "pandas",
    "dotenv": "python-dotenv",
    "apify_client": "apify-client",
    "whois": "python-whois",
    "playwright": "playwright",
    "anthropic": "anthropic",
    "curl_cffi": "curl_cffi",
}
for module_name, pkg in DEPS.items():
    check(f"import {pkg}", lambda m=module_name: importlib.import_module(m) and m)

# --- 3. config.py ------------------------------------------------------------
print("\nconfig.py:")
config = check("import config", lambda: importlib.import_module("config") and "config")
if config:
    config = importlib.import_module("config")
    check("BUSINESS_TYPE_MAP is a non-empty dict",
          lambda: f"{len(config.BUSINESS_TYPE_MAP)} entries"
          if isinstance(config.BUSINESS_TYPE_MAP, dict) and config.BUSINESS_TYPE_MAP
          else (_ for _ in ()).throw(AssertionError("missing/empty")))
    check("SCORING_WEIGHTS is a non-empty dict",
          lambda: f"{len(config.SCORING_WEIGHTS)} weights"
          if isinstance(config.SCORING_WEIGHTS, dict) and config.SCORING_WEIGHTS
          else (_ for _ in ()).throw(AssertionError("missing/empty")))
    check("CITIES is a non-empty list",
          lambda: f"{len(config.CITIES)} cities"
          if config.CITIES else (_ for _ in ()).throw(AssertionError("missing/empty")))
    check("SEARCH_QUERIES is a non-empty dict",
          lambda: f"{sum(len(v) for v in config.SEARCH_QUERIES.values())} queries "
                  f"across {len(config.SEARCH_QUERIES)} categories"
          if config.SEARCH_QUERIES else (_ for _ in ()).throw(AssertionError("missing/empty")))

# --- 4. Core pipeline modules import ----------------------------------------
print("\nCore pipeline modules import cleanly:")
for mod in ["discover", "enrich", "score", "main"]:
    check(f"import {mod}", lambda m=mod: importlib.import_module(m) and m)

# --- 5. Source registries ----------------------------------------------------
print("\nSource registries load and are well-formed:")


def _check_registry(pkg_name, min_arity):
    pkg = importlib.import_module(pkg_name)
    sources = pkg.ALL_SOURCES
    assert isinstance(sources, (list, tuple)) and sources, "ALL_SOURCES missing/empty"
    for row in sources:
        assert isinstance(row, tuple) and len(row) >= min_arity, f"bad row: {row!r}"
    return f"{len(sources)} sources"


check("awards.ALL_SOURCES", lambda: _check_registry("awards", 6))
check("directories.ALL_SOURCES", lambda: _check_registry("directories", 6))
check("jobs.ALL_SOURCES", lambda: _check_registry("jobs", 4))

# --- 6. Environment / API keys (informational) ------------------------------
print("\nAPI keys (informational — pipelines need only the keys they use):")
env_path = REPO_ROOT / ".env"
print(f"  [{INFO}] .env file: {'found' if env_path.exists() else 'NOT found (copy from .env.example)'}")
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
except Exception:  # noqa: BLE001
    pass
for key in ["SERPER_API_KEY", "APIFY_API_TOKEN", "ANTHROPIC_API_KEY"]:
    val = os.environ.get(key)
    status = "set" if val else "not set"
    if key == "ANTHROPIC_API_KEY" and val == "":
        status = "set but EMPTY (see the Claude Desktop note in README)"
    print(f"  [{INFO}] {key}: {status}")

# --- Summary -----------------------------------------------------------------
print()
if _failures:
    print(f"\033[91m{_failures} required check(s) failed.\033[0m "
          "Fix these before running a pipeline.")
    sys.exit(1)
print("\033[92mAll required checks passed.\033[0m "
      "Environment looks ready — start with a pipeline's smoke-test command.")
sys.exit(0)
