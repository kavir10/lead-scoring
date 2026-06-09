"""FastAPI backend for the local lead-list builder UI.

Starts pipeline runs as `python main.py ...` subprocesses so the UI is a thin
wrapper around the exact same CLI everyone already uses. Run state and logs
live under output/webui_runs/<run_id>/ so they survive a server restart.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    SEARCH_QUERIES,
    BUSINESS_TYPE_MAP,
    CITIES,
    SERPER_API_KEY,
    APIFY_API_TOKEN,
)

OUTPUT_DIR = ROOT / "output"
RUNS_DIR = OUTPUT_DIR / "webui_runs"
STATIC_DIR = Path(__file__).resolve().parent / "static"

MODES = {"discover", "full", "enrich", "score"}

app = FastAPI(title="Table22 lead list builder", docs_url=None, redoc_url=None)

_lock = threading.Lock()
_processes: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------- run state

def _run_dir(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{4}", run_id):
        raise HTTPException(status_code=400, detail="Bad run id")
    return RUNS_DIR / run_id


def _read_meta(run_dir: Path) -> dict | None:
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    # A run that says "running" but has no live process died with the server.
    if meta.get("status") == "running" and meta["id"] not in _processes:
        meta["status"] = "interrupted"
    return meta


def _write_meta(run_dir: Path, meta: dict) -> None:
    tmp = run_dir / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, indent=2))
    os.replace(tmp, run_dir / "meta.json")


def _watch(run_id: str, proc: subprocess.Popen) -> None:
    """Wait for the subprocess and record its exit status."""
    returncode = proc.wait()
    with _lock:
        _processes.pop(run_id, None)
        run_dir = RUNS_DIR / run_id
        meta = _read_meta(run_dir) or {}
        if meta.get("status") == "stopping":
            meta["status"] = "stopped"
        else:
            meta["status"] = "finished" if returncode == 0 else "failed"
        meta["returncode"] = returncode
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _write_meta(run_dir, meta)


# ---------------------------------------------------------------- meta

def _business_types() -> list[dict]:
    """Canonical types the pipeline accepts via --types, with query counts."""
    types: dict[str, dict] = {}
    for category, queries in SEARCH_QUERIES.items():
        canonical = BUSINESS_TYPE_MAP.get(category)
        if canonical is None:
            continue
        entry = types.setdefault(canonical, {
            "key": canonical,
            "label": canonical.replace("_", " ").title(),
            "query_count": 0,
            "categories": [],
        })
        entry["query_count"] += len(queries)
        entry["categories"].append(category)
    return list(types.values())


def _output_csvs() -> list[dict]:
    files = []
    if OUTPUT_DIR.exists():
        for path in OUTPUT_DIR.rglob("*.csv"):
            rel = path.relative_to(OUTPUT_DIR)
            if rel.parts[0] == "webui_runs":
                continue
            stat = path.stat()
            files.append({
                "name": str(rel),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files


@app.get("/api/meta")
def get_meta():
    return {
        "business_types": _business_types(),
        "city_count": len(CITIES),
        "env": {
            "SERPER_API_KEY": bool(SERPER_API_KEY),
            "APIFY_API_TOKEN": bool(APIFY_API_TOKEN),
            "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
    }


# ---------------------------------------------------------------- runs

class RunRequest(BaseModel):
    mode: str                       # discover | full | enrich | score
    types: list[str] = []           # canonical business types, [] = all
    max_searches: int = 0           # 0 = unlimited
    max_cities: int = 0             # 0 = all ~130 cities
    input_csv: str = ""             # output/-relative path, for enrich/score


def _resolve_input_csv(rel: str) -> Path:
    path = (OUTPUT_DIR / rel).resolve()
    if not str(path).startswith(str(OUTPUT_DIR.resolve()) + os.sep):
        raise HTTPException(status_code=400, detail="Input CSV must be inside output/")
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"No such file: output/{rel}")
    return path


def _build_command(req: RunRequest) -> list[str]:
    cmd = [sys.executable, "main.py"]
    if req.mode in ("discover", "full"):
        if req.mode == "discover":
            cmd.append("--discover")
        if req.types:
            valid = {t["key"] for t in _business_types()}
            unknown = [t for t in req.types if t not in valid]
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown business types: {unknown}")
            cmd += ["--types", ",".join(req.types)]
        if req.max_searches > 0:
            cmd += ["--max-searches", str(req.max_searches)]
        if req.max_cities > 0:
            cmd += ["--max-cities", str(req.max_cities)]
    elif req.mode == "enrich":
        cmd += ["--enrich", str(_resolve_input_csv(req.input_csv))]
    elif req.mode == "score":
        cmd += ["--score", str(_resolve_input_csv(req.input_csv))]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}. Valid: {sorted(MODES)}")
    return cmd


@app.post("/api/runs")
def start_run(req: RunRequest):
    cmd = _build_command(req)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run.log"

    env = dict(os.environ, PYTHONUNBUFFERED="1")
    log_file = open(log_path, "wb")
    try:
        proc = subprocess.Popen(
            cmd, cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT, env=env,
        )
    except OSError as e:
        log_file.close()
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")
    finally:
        # The subprocess holds its own handle to the file descriptor.
        if not log_file.closed:
            log_file.close()

    meta = {
        "id": run_id,
        "mode": req.mode,
        "types": req.types,
        "max_searches": req.max_searches,
        "max_cities": req.max_cities,
        "input_csv": req.input_csv,
        "command": " ".join(["python"] + cmd[1:]),
        "status": "running",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "returncode": None,
    }
    with _lock:
        _processes[run_id] = proc
        _write_meta(run_dir, meta)

    threading.Thread(target=_watch, args=(run_id, proc), daemon=True).start()
    return meta


@app.get("/api/runs")
def list_runs():
    runs = []
    if RUNS_DIR.exists():
        for run_dir in RUNS_DIR.iterdir():
            meta = _read_meta(run_dir)
            if meta:
                runs.append(meta)
    runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return runs


@app.get("/api/runs/{run_id}/log")
def get_log(run_id: str, offset: int = 0):
    run_dir = _run_dir(run_id)
    meta = _read_meta(run_dir)
    if meta is None:
        raise HTTPException(status_code=404, detail="Run not found")
    log_path = run_dir / "run.log"
    content = b""
    size = 0
    if log_path.exists():
        size = log_path.stat().st_size
        if offset < size:
            with open(log_path, "rb") as f:
                f.seek(max(0, offset))
                content = f.read()
    return {
        "status": meta["status"],
        "offset": size,
        "content": content.decode("utf-8", errors="replace"),
    }


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str):
    run_dir = _run_dir(run_id)
    with _lock:
        proc = _processes.get(run_id)
        if proc is None:
            raise HTTPException(status_code=409, detail="Run is not active")
        meta = _read_meta(run_dir)
        meta["status"] = "stopping"
        _write_meta(run_dir, meta)
    proc.terminate()
    return {"ok": True}


# ---------------------------------------------------------------- files

@app.get("/api/files")
def list_files():
    return _output_csvs()


@app.get("/api/files/download")
def download_file(name: str):
    path = (OUTPUT_DIR / name).resolve()
    if not str(path).startswith(str(OUTPUT_DIR.resolve()) + os.sep) or path.suffix != ".csv":
        raise HTTPException(status_code=400, detail="Only CSVs inside output/ can be downloaded")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="text/csv", filename=path.name)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
