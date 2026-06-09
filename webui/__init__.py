"""Local web UI for building lead lists.

Wraps the generic Serper pipeline (main.py) in a browser form so anyone with
the repo installed can create a lead list without touching the CLI. The server
binds to 127.0.0.1 only — it is meant for localhost use, never deployment.

Run with:
    python -m webui            # http://127.0.0.1:8722
    python -m webui --port 9000
"""
