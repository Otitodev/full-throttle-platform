"""Shared helpers for the governance skill.

Dependency-free, decoupled from Hermes internals (HERMES_HOME-aware). The audit
log is the per-client append-only record of client-facing mutations at
<HERMES_HOME>/governance/audit.jsonl — the same path the other skills append to
via their own tiny audit() helper.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NoReturn


def governance_dir(override: str | None = None) -> Path:
    if override:
        base = Path(override).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        base = home / "governance"
    base.mkdir(parents=True, exist_ok=True)
    return base


def audit_path(state_dir: str | None = None) -> Path:
    return governance_dir(state_dir) / "audit.jsonl"


def read_audit(state_dir: str | None = None) -> list[dict]:
    path = audit_path(state_dir)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def fail(message: str) -> NoReturn:
    print(json.dumps({"success": False, "error": message}))
    raise SystemExit(1)
