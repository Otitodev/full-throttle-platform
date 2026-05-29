"""Shared helpers for the lead-response entry scripts.

Dependency-free and decoupled from Hermes internals: profile state is read from
the HERMES_HOME env var with a ~/.hermes fallback. Mirrors the review/social
skills' _common.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NoReturn


def state_dir(override: str | None = None) -> Path:
    """Profile-aware state dir: --state-dir, else <HERMES_HOME>/lead-response."""
    if override:
        base = Path(override).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        base = home / "lead-response"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def build_adapter(args):
    """Construct the chosen CRMAdapter from parsed argparse args."""
    if args.adapter == "manual":
        from adapters.manual import ManualAdapter
        crm_dir = getattr(args, "crm_dir", None) or str(state_dir(getattr(args, "state_dir", None)))
        return ManualAdapter(crm_dir=crm_dir)
    if args.adapter == "jobber":
        from adapters.jobber import JobberAdapter
        return JobberAdapter(token_path=getattr(args, "token_path", None))
    raise ValueError(f"unknown adapter: {args.adapter}")


def add_adapter_args(parser):
    parser.add_argument("--adapter", choices=["manual", "jobber"], default="manual")
    parser.add_argument("--crm-dir", help="[manual] dir for leads_crm.jsonl")
    parser.add_argument("--token-path", help="[jobber] OAuth token json path")
    parser.add_argument("--state-dir", help="override profile state dir")


def fail(message: str) -> NoReturn:
    print(json.dumps({"success": False, "error": message}))
    raise SystemExit(1)
