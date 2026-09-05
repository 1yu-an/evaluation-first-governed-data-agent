#!/usr/bin/env python3
"""Initialize the deterministic demo database and start the local web UI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "03-governed-mysql-data-agent"
DEMO_DB_PATH = PROJECT_ROOT / "demo.db"
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the governed data-agent web demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = os.environ.get("DATA_AGENT_EXECUTOR", "sqlite").strip().lower()
    if mode == "sqlite":
        from src.demo import initialize_demo

        if not DEMO_DB_PATH.exists():
            initialize_demo(DEMO_DB_PATH)

    from src.executor import executor_from_env
    from src.web import create_app
    import uvicorn

    # Validate the selected backend and required environment before claiming
    # that the demo is ready. This intentionally does not open a DB connection.
    executor_from_env(DEMO_DB_PATH)
    app = create_app(db_path=DEMO_DB_PATH)
    print(f"Demo ready:\nhttp://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
