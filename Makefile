# Convenience shortcuts. These are optional — every command has a plain
# copy-paste equivalent in README.md. On Windows without `make`, use those.
#
# `make setup` bootstraps the venv with the system Python; every other target
# runs through the venv's Python, so you do NOT need to activate the venv first
# for `make` targets.

PYTHON  ?= python           # system Python, only used to create the venv
VENV_PY := .venv/bin/python # venv Python, used by everything else

.DEFAULT_GOAL := help

.PHONY: help setup test smoke \
        smoke-generic smoke-awards smoke-directories smoke-wineshops \
        smoke-butcher smoke-jobs smoke-iggraph

help: ## Show this help
	@echo "lead-scoring — common commands (see README.md for the full menu):"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv, install pinned deps, install Chromium, seed .env
	$(PYTHON) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements.txt
	$(VENV_PY) -m playwright install chromium
	@test -f .env || cp .env.example .env
	@echo "Setup done. Edit .env to add your API keys, then run: make test"

test: ## Validate environment & wiring (no API calls, no spend)
	$(VENV_PY) tests/smoke_test.py

smoke: test ## Alias for `make test`

# --- Cheapest safe validation for each pipeline (see README cost notes) ------

smoke-generic: ## Generic pipeline: 5 Serper searches (needs SERPER_API_KEY)
	$(VENV_PY) main.py --discover --types butcher --max-searches 5

smoke-awards: ## Awards: free Michelin scrape (no API keys)
	$(VENV_PY) discover_michelin_direct.py --smoke

smoke-directories: ## Directories: free Raisin source (no API keys)
	$(VENV_PY) discover_directories.py --source raisin_app

smoke-wineshops: ## Best wine shops: dry run, spends nothing
	$(VENV_PY) -m best_wine_shops.discover --dry-run

smoke-butcher: ## Butcher lane: full run is free (public pages only)
	$(VENV_PY) discover_butchers.py

smoke-jobs: ## Job boards: list sources only (free)
	$(VENV_PY) discover_jobs.py --list

smoke-iggraph: ## IG social graph: aggregate cached posts only (free)
	$(VENV_PY) discover_ig_graph.py --aggregate
