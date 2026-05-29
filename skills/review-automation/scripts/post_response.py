#!/usr/bin/env python3
"""Post an owner-approved reply to one review via the chosen adapter (story R2).

Called by the agent AFTER the owner approves a drafted reply (via the `clarify`
tool). Prints a JSON result.

Example (manual adapter):
    python post_response.py --adapter manual --reviews-file reviews.csv \
        --review-id r-102 --text "Thanks so much, Jane! ..."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_adapter_args, audit, build_adapter, fail


def main() -> None:
    p = argparse.ArgumentParser(description="Post an approved reply to a review.")
    add_adapter_args(p)
    p.add_argument("--review-id", required=True)
    p.add_argument("--text", help="reply text (inline)")
    p.add_argument("--text-file", help="reply text from a file")
    args = p.parse_args()

    text = args.text
    if args.text_file:
        tf = Path(args.text_file).expanduser()
        if not tf.is_file():
            fail(f"--text-file not found: {tf}")
        text = tf.read_text(encoding="utf-8")
    text = (text or "").strip()
    if not text:
        fail("reply text is empty (pass --text or --text-file)")

    try:
        adapter = build_adapter(args)
        result = adapter.post_reply(args.review_id, text)
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
        return

    audit("review-automation", action="review_reply", target=args.review_id,
          status="ok", rollback_ref=result.get("review_id"), approval_state="approved")
    print(json.dumps({"success": True, **result}))


if __name__ == "__main__":
    main()
