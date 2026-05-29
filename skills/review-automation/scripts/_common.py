"""Shared helpers for the review-automation entry scripts.

Kept dependency-free and decoupled from Hermes internals (profile state is read
from the HERMES_HOME env var with a ~/.hermes fallback — no Hermes import).
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def state_dir(override: str | None = None) -> Path:
    """Profile-aware state dir: --state-dir, else <HERMES_HOME>/review-automation."""
    if override:
        base = Path(override).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        base = home / "review-automation"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


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
    """Construct the chosen ReviewAdapter from parsed argparse args."""
    if args.adapter == "manual":
        from adapters.manual import ManualAdapter
        return ManualAdapter(
            reviews_file=getattr(args, "reviews_file", "") or "",
            responses_dir=getattr(args, "responses_dir", None),
        )
    if args.adapter == "gbp":
        from adapters.gbp import GBPAdapter
        return GBPAdapter(
            location=getattr(args, "location", None),
            token_path=getattr(args, "token_path", None),
        )
    raise ValueError(f"unknown adapter: {args.adapter}")


def add_adapter_args(parser):
    parser.add_argument("--adapter", choices=["manual", "gbp"], default="manual")
    parser.add_argument("--reviews-file", help="[manual] CSV/JSON of reviews")
    parser.add_argument("--responses-dir", help="[manual] where replies are written")
    parser.add_argument("--location", help="[gbp] accounts/{a}/locations/{l}")
    parser.add_argument("--token-path", help="[gbp] OAuth token json path")
    parser.add_argument("--state-dir", help="override profile state dir")


def fail(message: str):
    print(json.dumps({"success": False, "error": message}))
    raise SystemExit(1)
