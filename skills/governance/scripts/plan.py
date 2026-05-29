#!/usr/bin/env python3
"""Emit an execution plan before a mutation, and classify whether it needs approval.

The agent calls this before mutating an external system. It prints a structured
plan {intent, target, actions}, classifies risky intents, and appends a "planned"
row to the audit log. Risky plans must be gated with the `clarify` tool before the
agent proceeds.

    plan.py --intent update_blog_post --target /blog/x --actions "update title,replace CTA,publish"
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import audit_path

# Intents that mutate live, externally-visible state → require owner approval.
RISKY_INTENT_HINTS = ("publish", "delete", "remove", "push", "deploy", "charge",
                      "refund", "send_bulk", "overwrite", "unpublish")


def is_risky(intent: str, actions: list[str]) -> bool:
    blob = (intent + " " + " ".join(actions)).lower()
    return any(h in blob for h in RISKY_INTENT_HINTS)


def main() -> None:
    p = argparse.ArgumentParser(description="Emit + classify an execution plan.")
    p.add_argument("--intent", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--actions", required=True, help="comma-separated action list")
    p.add_argument("--skill", default="")
    p.add_argument("--state-dir")
    args = p.parse_args()

    actions = [a.strip() for a in args.actions.split(",") if a.strip()]
    risky = is_risky(args.intent, actions)
    plan = {
        "id": uuid.uuid4().hex[:12],
        "intent": args.intent,
        "target": args.target,
        "actions": actions,
        "requires_approval": risky,
    }

    # Record the plan as a 'planned' audit row.
    record = {
        "id": plan["id"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": args.skill or "planner",
        "action": f"plan:{args.intent}",
        "target": args.target,
        "status": "planned",
        "rollback_ref": None,
        "approval_state": "pending" if risky else "none",
        "repo": None,
    }
    with audit_path(args.state_dir).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    print(json.dumps({
        "success": True,
        "plan": plan,
        "note": ("RISKY — gate with the clarify tool before executing."
                 if risky else "Low-risk — proceed; the action will be audited."),
    }, indent=2))


if __name__ == "__main__":
    main()
