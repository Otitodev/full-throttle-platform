#!/usr/bin/env python3
"""Validate a profile's tool-permission scope (G1) against the governance matrix.

Checks that a client profile caps dangerous tools at the profile level and that
the scope matrix's expectations hold. The runtime enforcement is Hermes'
(`agent.disabled_toolsets`, `tools.<platform>.disabled`, and per-worker
`delegate_task(toolsets=..., role="leaf")`); this is a lint that the config
actually applies the policy. See ../references/scope_matrix.md.

    scopes.py check --config <profile>/config.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import fail

# Toolsets that must be capped at the profile level unless explicitly justified —
# no production worker should have unrestricted shell / arbitrary code execution.
REQUIRED_DISABLED = {"code_execution"}


def main() -> None:
    p = argparse.ArgumentParser(description="Check a profile config against the scope matrix.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--config", required=True, help="path to a profile config.yaml")
    args = p.parse_args()

    cfg_path = Path(args.config).expanduser()
    if not cfg_path.is_file():
        fail(f"config not found: {cfg_path}")
    cfg: dict = {}
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        fail(f"invalid YAML: {exc}")

    disabled = set((cfg.get("agent") or {}).get("disabled_toolsets") or [])
    missing = sorted(REQUIRED_DISABLED - disabled)
    violations = []
    if missing:
        violations.append(f"agent.disabled_toolsets is missing required caps: {missing}")

    ok = not violations
    print(json.dumps({
        "success": True,
        "passed": ok,
        "disabled_toolsets": sorted(disabled),
        "violations": violations,
        "note": "Per-worker scoping is enforced at delegate_task time (role=leaf + toolsets); "
                "this lint covers the profile-level caps only.",
    }, indent=2))
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
