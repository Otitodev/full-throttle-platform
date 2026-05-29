#!/usr/bin/env python3
"""Roll back a logged mutation by its audit id.

Dispatches on the audited action + rollback_ref:
- git-backed publishes (astro-git / proxy-subdir): `git revert --no-edit <sha>` in the repo.
- WordPress publishes: print the manual delete/unpublish step (needs WP creds to automate).
- everything else: print manual guidance.
A 'revert' row is appended to the audit log.

    revert.py --audit-id <id>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import audit_path, fail, read_audit


def log_revert(state_dir, original: dict, outcome: str) -> None:
    record = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": "governance",
        "action": "revert",
        "target": original.get("target", ""),
        "status": outcome,
        "rollback_ref": original.get("id"),
        "approval_state": "none",
        "repo": original.get("repo"),
    }
    with audit_path(state_dir).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Roll back a logged mutation.")
    p.add_argument("--audit-id", required=True)
    p.add_argument("--state-dir")
    args = p.parse_args()

    rows = read_audit(args.state_dir)
    match = next((r for r in rows if r.get("id") == args.audit_id), None)
    if not match:
        fail(f"audit id not found: {args.audit_id}")
    assert match is not None  # fail() above is NoReturn; narrows for the type checker
    ref = match.get("rollback_ref")
    repo = match.get("repo")
    action = match.get("action", "")

    # git-backed publishes carry a commit SHA + repo
    if repo and ref and len(str(ref)) >= 7 and Path(repo).is_dir():
        r = subprocess.run(["git", "-C", repo, "revert", "--no-edit", ref],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            log_revert(args.state_dir, match, "reverted")
            print(json.dumps({"success": True, "method": "git-revert", "repo": repo, "ref": ref}))
            return
        log_revert(args.state_dir, match, "revert-failed")
        fail(f"git revert failed: {r.stderr.strip() or r.stdout.strip()}")

    # WordPress / API-based — manual step
    log_revert(args.state_dir, match, "manual-required")
    print(json.dumps({
        "success": True,
        "method": "manual",
        "instructions": (
            f"Manually undo {action} on target {match.get('target','')} "
            f"(rollback_ref={ref}). For WordPress: delete/unpublish post id {ref} via the admin "
            f"or the wp-json API."
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
