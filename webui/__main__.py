"""Entry point: python -m webui [--port N]"""
import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Lead list builder UI (localhost only)")
    parser.add_argument("--port", type=int, default=8722, help="Port to listen on (default 8722)")
    args = parser.parse_args()

    print(f"\n  Lead list builder running at:  http://127.0.0.1:{args.port}\n")
    # 127.0.0.1 on purpose: this UI is local-only and must not be exposed.
    uvicorn.run("webui.server:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
