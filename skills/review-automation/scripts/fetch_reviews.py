#!/usr/bin/env python3
"""Fetch NEW customer reviews via the chosen adapter (cron data-collection step).

Prints a JSON object to stdout listing reviews not seen on a previous run, so a
cron job can inject them into the agent prompt for drafting replies (story R2).
De-dup state lives in <state-dir>/seen.json.

Example (manual adapter, demo path):
    python fetch_reviews.py --adapter manual --reviews-file reviews.csv

Flags of note:
    --peek    list new reviews WITHOUT marking them seen (no state write)
    --all     ignore seen.json and return every review
    --reset   clear seen.json before running
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make adapters/_common importable

from _common import add_adapter_args, build_adapter, fail, load_json, state_dir


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch new customer reviews.")
    add_adapter_args(p)
    p.add_argument("--peek", action="store_true", help="don't persist seen state")
    p.add_argument("--all", action="store_true", help="ignore seen.json")
    p.add_argument("--reset", action="store_true", help="clear seen.json first")
    args = p.parse_args()

    sdir = state_dir(args.state_dir)
    seen_path = sdir / "seen.json"
    if args.reset and seen_path.exists():
        seen_path.unlink()

    try:
        adapter = build_adapter(args)
        reviews = adapter.list_reviews()
    except Exception as exc:  # surface adapter/setup errors as JSON, not a traceback
        fail(f"{type(exc).__name__}: {exc}")
        return

    seen = set(load_json(seen_path, []))
    new = reviews if args.all else [r for r in reviews if r.id not in seen]

    if not args.peek and not args.all:
        seen.update(r.id for r in new)
        seen_path.write_text(json.dumps(sorted(seen)), encoding="utf-8")

    print(json.dumps({
        "success": True,
        "adapter": adapter.name,
        "new_count": len(new),
        "total_seen": len(seen),
        "reviews": [r.to_dict() for r in new],
    }, indent=2))


if __name__ == "__main__":
    main()
