"""Shared helpers for the social-scheduler entry scripts.

Dependency-free and decoupled from Hermes internals: profile state is read from
the HERMES_HOME env var with a ~/.hermes fallback (no Hermes import). Mirrors the
review-automation skill's _common.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NoReturn


def state_dir(override: str | None = None) -> Path:
    """Profile-aware state dir: --state-dir, else <HERMES_HOME>/social-scheduler."""
    if override:
        base = Path(override).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        base = home / "social-scheduler"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def audit(skill: str, action: str, target: str = "", status: str = "ok",
          rollback_ref=None, repo=None, approval_state: str = "none") -> None:
    """Append one mutation row to the shared governance audit log (best-effort)."""
    import uuid
    from datetime import datetime, timezone
    try:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        gov = home / "governance"
        gov.mkdir(parents=True, exist_ok=True)
        row = {
            "id": uuid.uuid4().hex[:12],
            "ts": datetime.now(timezone.utc).isoformat(),
            "skill": skill, "action": action, "target": target, "status": status,
            "rollback_ref": rollback_ref, "approval_state": approval_state, "repo": repo,
        }
        with (gov / "audit.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def build_adapter(args):
    """Construct the chosen SocialAdapter from parsed argparse args."""
    if args.adapter == "manual":
        from adapters.manual import ManualAdapter
        # outbox defaults to the profile state dir when not overridden
        outbox = getattr(args, "outbox_dir", None) or str(state_dir(getattr(args, "state_dir", None)))
        return ManualAdapter(outbox_dir=outbox)
    if args.adapter == "gbp":
        from adapters.gbp_post import GBPPostAdapter
        return GBPPostAdapter(
            location=getattr(args, "location", None),
            token_path=getattr(args, "token_path", None),
        )
    raise ValueError(f"unknown adapter: {args.adapter}")


def add_adapter_args(parser):
    parser.add_argument("--adapter", choices=["manual", "gbp"], default="manual")
    parser.add_argument("--outbox-dir", help="[manual] dir for outbox.jsonl")
    parser.add_argument("--location", help="[gbp] accounts/{a}/locations/{l}")
    parser.add_argument("--token-path", help="[gbp] OAuth token json path")
    parser.add_argument("--state-dir", help="override profile state dir")


def fail(message: str) -> NoReturn:
    print(json.dumps({"success": False, "error": message}))
    raise SystemExit(1)
