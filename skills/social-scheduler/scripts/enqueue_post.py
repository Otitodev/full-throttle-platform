#!/usr/bin/env python3
"""Add an agent-captioned post to the publish queue.

Called after the agent drafts a caption from a real pick_content candidate and
the owner approves the batch. Appends to <state>/queue.json and records the
source_ref in used.json so pick_content won't resurface it.

Example:
    python enqueue_post.py --kind photo --source-ref asset:a1 \
        --image /assets/a1.jpg --caption "Fresh board-on-board install in Lynn Haven." \
        --targets gbp,facebook --scheduled-at 2026-06-02T14:00:00Z --status approved
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import fail, load_json, save_json, state_dir


def main() -> None:
    p = argparse.ArgumentParser(description="Enqueue an approved social post.")
    p.add_argument("--kind", choices=["photo", "review"], required=True)
    p.add_argument("--caption", required=True)
    p.add_argument("--source-ref", default="", help="asset:<id> or review:<id> this came from")
    p.add_argument("--image", default="", help="local path or public URL to a REAL photo")
    p.add_argument("--targets", default="gbp", help="comma list, e.g. gbp,facebook,nextdoor")
    p.add_argument("--scheduled-at", required=True, help="ISO timestamp to publish")
    p.add_argument("--status", choices=["pending", "approved"], default="pending")
    p.add_argument("--state-dir", help="override profile state dir")
    args = p.parse_args()

    if args.kind == "photo" and not args.image:
        fail("photo posts require --image (a real job photo)")

    sdir = state_dir(args.state_dir)
    queue_path = sdir / "queue.json"
    queue = load_json(queue_path, [])

    post = {
        "id": uuid.uuid4().hex[:12],
        "kind": args.kind,
        "caption": args.caption,
        "image_path": args.image,
        "source_ref": args.source_ref,
        "targets": [t.strip() for t in args.targets.split(",") if t.strip()],
        "scheduled_at": args.scheduled_at,
        "status": args.status,
    }
    queue.append(post)
    save_json(queue_path, queue)

    # Mark the source consumed so pick_content won't resurface it.
    if args.source_ref:
        used_path = sdir / "used.json"
        used = load_json(used_path, [])
        if args.source_ref not in used:
            used.append(args.source_ref)
            save_json(used_path, used)

    print(json.dumps({"success": True, "post_id": post["id"], "status": post["status"], "queued_to": str(queue_path)}))


if __name__ == "__main__":
    main()
