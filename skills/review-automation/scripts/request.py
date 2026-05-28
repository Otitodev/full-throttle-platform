#!/usr/bin/env python3
"""Build a post-job review-request message for a customer (story R1).

Produces the templated message + review link and logs the request to state. The
AGENT then delivers it with the `send_message` tool (sms:/email:). This script
does NOT send — delivery is Hermes' job, and keeping it out of the script makes
the message reviewable and the script testable offline.

Example:
    python request.py --name "Jane D." --business "Mr. Fence of Florida" \
        --review-link "https://g.page/r/ABC123/review" --customer "sms:+18505551234"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import fail, state_dir

TEMPLATE = (
    "Hi {name}, thanks for choosing {business}! It was a pleasure working with you. "
    "If you have a moment, a quick Google review really helps our small business — "
    "it only takes 30 seconds: {link}"
)


def build_link(args) -> str:
    if args.review_link:
        return args.review_link
    if args.place_id:
        return f"https://search.google.com/local/writereview?placeid={args.place_id}"
    fail("provide --review-link or --place-id")
    return ""  # unreachable


def main() -> None:
    p = argparse.ArgumentParser(description="Build a review-request message.")
    p.add_argument("--name", required=True, help="customer first name")
    p.add_argument("--business", default="our team", help="business name for the message")
    p.add_argument("--review-link", help="full Google review URL")
    p.add_argument("--place-id", help="Google place id (used to build the review link)")
    p.add_argument("--customer", default="", help="delivery target for logging, e.g. sms:+1… / email:…")
    p.add_argument("--template", help="override message template (use {name} {business} {link})")
    p.add_argument("--state-dir", help="override profile state dir")
    args = p.parse_args()

    link = build_link(args)
    template = args.template or TEMPLATE
    try:
        message = template.format(name=args.name, business=args.business, link=link)
    except KeyError as exc:
        fail(f"template references unknown field: {exc}")
        return

    # Log the request so a later job can send follow-up reminders if no review lands.
    sdir = state_dir(args.state_dir)
    log_path = sdir / "requests.jsonl"
    record = {"name": args.name, "customer": args.customer, "link": link, "sent_at": date.today().isoformat()}
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    print(json.dumps({
        "success": True,
        "message": message,
        "review_link": link,
        "deliver_to": args.customer,
        "logged_to": str(log_path),
    }, indent=2))


if __name__ == "__main__":
    main()
