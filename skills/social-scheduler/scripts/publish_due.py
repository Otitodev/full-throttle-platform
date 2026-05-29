#!/usr/bin/env python3
"""Publish approved posts that are now due, via the chosen adapter (cron step).

Reads <state>/queue.json, publishes posts where status=="approved" and
scheduled_at <= now, marks them "posted" (dedup), and prints a JSON summary.
Intended to run as a daily cron job.

Example:
    python publish_due.py --adapter manual
    python publish_due.py --adapter gbp --location accounts/123/locations/456
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_adapter_args, build_adapter, fail, load_json, save_json, state_dir
from adapters.base import Post


def _parse_iso(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> None:
    p = argparse.ArgumentParser(description="Publish due approved posts.")
    add_adapter_args(p)
    p.add_argument("--now", help="override 'now' (ISO) for testing")
    p.add_argument("--dry-run", action="store_true", help="report due posts without publishing")
    args = p.parse_args()

    now = _parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        fail("invalid --now timestamp")

    sdir = state_dir(args.state_dir)
    queue_path = sdir / "queue.json"
    queue = load_json(queue_path, [])

    try:
        adapter = build_adapter(args)
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
        return

    published, skipped, errors = [], 0, []
    for entry in queue:
        if entry.get("status") != "approved":
            skipped += 1
            continue
        due = _parse_iso(entry.get("scheduled_at", ""))
        if due is None or due > now:
            skipped += 1
            continue
        if args.dry_run:
            published.append({"post_id": entry.get("id"), "dry_run": True})
            continue
        try:
            result = adapter.publish(Post.from_dict(entry))
            entry["status"] = "posted"
            published.append(result)
        except Exception as exc:  # isolate per-post failures; leave status for retry
            errors.append({"post_id": entry.get("id"), "error": f"{type(exc).__name__}: {exc}"})

    if not args.dry_run:
        save_json(queue_path, queue)

    print(json.dumps({
        "success": True,
        "adapter": adapter.name,
        "published": len(published),
        "skipped": skipped,
        "errors": errors,
        "details": published,
    }, indent=2))


if __name__ == "__main__":
    main()
