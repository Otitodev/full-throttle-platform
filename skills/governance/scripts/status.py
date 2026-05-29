#!/usr/bin/env python3
"""Observability: synthesize the audit log into a human (or --json) status view.

Shows a recent-mutation timeline, the approval queue (rows awaiting owner sign-off),
and counts by action/status. Optionally folds in Hermes' own cron job status
(<HERMES_HOME>/cron/jobs.json) if present, so one view answers "what has the agent
done / is waiting / is scheduled."

    status.py            # human-readable
    status.py --json     # machine-readable
    status.py --n 30     # timeline depth
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_audit


def _cron_jobs() -> list[dict]:
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    jobs_file = home / "cron" / "jobs.json"
    if not jobs_file.is_file():
        return []
    try:
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    return jobs if isinstance(jobs, list) else []


def main() -> None:
    p = argparse.ArgumentParser(description="Governance status / timeline.")
    p.add_argument("--state-dir")
    p.add_argument("--n", type=int, default=20, help="timeline depth")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rows = read_audit(args.state_dir)
    timeline = rows[-args.n:]
    approval_queue = [r for r in rows if r.get("approval_state") == "pending"]
    by_action = Counter(r.get("action", "?") for r in rows)
    by_status = Counter(r.get("status", "?") for r in rows)
    crons = [{"name": j.get("name") or j.get("id"), "schedule": j.get("schedule"),
              "state": j.get("state"), "last_status": j.get("last_status"),
              "next_run_at": j.get("next_run_at")} for j in _cron_jobs()]

    summary = {
        "success": True,
        "total_mutations": len(rows),
        "approval_queue": approval_queue,
        "counts_by_action": dict(by_action),
        "counts_by_status": dict(by_status),
        "cron_jobs": crons,
        "timeline": timeline,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"Mutations logged: {len(rows)}")
    print(f"Awaiting approval: {len(approval_queue)}")
    if approval_queue:
        for r in approval_queue:
            print(f"  · [{r.get('id')}] {r.get('action')} → {r.get('target')}")
    print("By action:", ", ".join(f"{k}={v}" for k, v in by_action.items()) or "none")
    print("By status:", ", ".join(f"{k}={v}" for k, v in by_status.items()) or "none")
    if crons:
        print("Cron:")
        for c in crons:
            print(f"  · {c['name']} [{c['schedule']}] state={c['state']} last={c['last_status']}")
    print(f"\nLast {len(timeline)} mutations:")
    for r in timeline:
        print(f"  {r.get('ts','')[:19]}  {r.get('skill','?'):16} {r.get('action','?'):16} "
              f"{r.get('status','?'):10} {r.get('target','')}")


if __name__ == "__main__":
    main()
