#!/usr/bin/env python3
"""Sync a structured lead into the client's CRM via the chosen adapter (story L2).

Idempotent on lead id. Run after intake.py + the first-touch reply.

Example:
    python sync_lead.py --adapter manual --name "Jane D" --phone "+18505551234" \
        --email jane@example.com --source web-form --message "wants vinyl privacy fence"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_adapter_args, build_adapter, fail
from adapters.base import Lead, lead_fingerprint


def main() -> None:
    p = argparse.ArgumentParser(description="Sync a lead to the CRM.")
    add_adapter_args(p)
    p.add_argument("--id", default="")
    p.add_argument("--name", default="")
    p.add_argument("--phone", default="")
    p.add_argument("--email", default="")
    p.add_argument("--message", default="")
    p.add_argument("--source", default="web-form")
    args = p.parse_args()

    lead = Lead.from_dict({
        "id": args.id, "name": args.name, "phone": args.phone, "email": args.email,
        "message": args.message, "source": args.source,
    })
    if not (lead.phone or lead.email):
        fail("lead has no phone or email")
    if not lead.id:
        lead.id = lead_fingerprint(lead)

    try:
        adapter = build_adapter(args)
        result = adapter.sync_lead(lead)
        print(json.dumps({"success": True, **result}))
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
