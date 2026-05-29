#!/usr/bin/env python3
"""Canonical reader/writer for the per-client mutation audit log.

The audit log (<HERMES_HOME>/governance/audit.jsonl) is an append-only record of
every client-facing mutation. The 4 capability skills append to it automatically
via their own audit() helper; this CLI is the canonical interface for the agent /
operator to log ad-hoc entries and to read the log back.

    audit.py log --skill content-publisher --action publish --target /blog/x --status ok --rollback-ref <sha>
    audit.py tail --n 20
    audit.py query --action publish --status ok
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import audit_path, governance_dir, read_audit


def cmd_log(args) -> None:
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": args.skill,
        "action": args.action,
        "target": args.target,
        "status": args.status,
        "rollback_ref": args.rollback_ref or None,
        "approval_state": args.approval_state,
        "repo": args.repo or None,
    }
    path = audit_path(args.state_dir)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    print(json.dumps({"success": True, "id": record["id"], "logged_to": str(path)}))


def cmd_tail(args) -> None:
    rows = read_audit(args.state_dir)[-args.n:]
    print(json.dumps({"success": True, "count": len(rows), "rows": rows}, indent=2))


def cmd_query(args) -> None:
    rows = read_audit(args.state_dir)
    if args.action:
        rows = [r for r in rows if r.get("action") == args.action]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.skill:
        rows = [r for r in rows if r.get("skill") == args.skill]
    print(json.dumps({"success": True, "count": len(rows), "rows": rows}, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Mutation audit log read/write.")
    p.add_argument("--state-dir", help="override governance dir")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="append a mutation record")
    lg.add_argument("--skill", required=True)
    lg.add_argument("--action", required=True)
    lg.add_argument("--target", default="")
    lg.add_argument("--status", default="ok")
    lg.add_argument("--rollback-ref", default="")
    lg.add_argument("--approval-state", default="none", choices=["none", "pending", "approved", "denied"])
    lg.add_argument("--repo", default="", help="repo path for git-based rollback")
    lg.set_defaults(func=cmd_log)

    tl = sub.add_parser("tail", help="show the last N records")
    tl.add_argument("--n", type=int, default=20)
    tl.set_defaults(func=cmd_tail)

    q = sub.add_parser("query", help="filter records")
    q.add_argument("--action")
    q.add_argument("--status")
    q.add_argument("--skill")
    q.set_defaults(func=cmd_query)

    args = p.parse_args()
    governance_dir(args.state_dir)  # ensure dir exists
    args.func(args)


if __name__ == "__main__":
    main()
