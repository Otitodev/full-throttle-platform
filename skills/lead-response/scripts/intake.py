#!/usr/bin/env python3
"""Normalize an inbound lead, dedup it, log it, and render the first-touch reply.

Run by the agent on the webhook-triggered turn (story L1). Takes raw lead fields
(flags or --payload-file JSON) → a structured lead, a dedup verdict, an append to
the leads.jsonl audit log, and an APPROVED first-touch message the agent then
sends via the send_message tool. The first-touch copy is a template (not free
text) — the speed-to-lead + governance guardrail.

Example:
    python intake.py --payload-file lead.json --business "Mr. Fence of Florida"
    python intake.py --name "Jane D" --phone "+18505551234" --source web-form --business "Mr. Fence"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import fail, state_dir
from adapters.base import Lead, lead_fingerprint

FIRST_TOUCH = (
    "Hi {name}, thanks for reaching out to {business}! This is our team — we got your "
    "request{about} and want to help. What's the best day/time for a free on-site estimate? "
    "Reply here or call us anytime."
)


def _load_payload(args) -> dict:
    if args.payload_file:
        pf = Path(args.payload_file).expanduser()
        if not pf.is_file():
            fail(f"--payload-file not found: {pf}")
        try:
            return json.loads(pf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"payload is not valid JSON: {exc}")
    return {
        "id": args.id, "name": args.name, "phone": args.phone, "email": args.email,
        "message": args.message, "source": args.source,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Normalize + first-touch an inbound lead.")
    p.add_argument("--payload-file", help="JSON lead payload (from the webhook)")
    p.add_argument("--id", default="", help="source-provided lead id (else derived)")
    p.add_argument("--name", default="")
    p.add_argument("--phone", default="")
    p.add_argument("--email", default="")
    p.add_argument("--message", default="")
    p.add_argument("--source", default="web-form")
    p.add_argument("--business", default="our team", help="business name for the first-touch copy")
    p.add_argument("--template", help="override first-touch template ({name} {business} {about})")
    p.add_argument("--state-dir", help="override profile state dir")
    args = p.parse_args()

    raw = _load_payload(args)
    lead = Lead.from_dict(raw)
    if not (lead.phone or lead.email):
        fail("lead has no phone or email — cannot respond")
    if not lead.id:
        lead.id = lead_fingerprint(lead)
    if not lead.created:
        lead.created = datetime.now(timezone.utc).isoformat()

    # Dedup + audit against leads.jsonl (belt-and-suspenders over the webhook's delivery_id).
    sdir = state_dir(args.state_dir)
    log_path = sdir / "leads.jsonl"
    seen_ids = set()
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                seen_ids.add(json.loads(line).get("id"))
            except json.JSONDecodeError:
                continue
    duplicate = lead.id in seen_ids

    first_name = (lead.name or "there").split()[0]
    about = f" about {lead.message[:60]}" if lead.message else ""
    template = args.template or FIRST_TOUCH
    message = ""
    try:
        message = template.format(name=first_name, business=args.business, about=about)
    except KeyError as exc:
        fail(f"template references unknown field: {exc}")

    if not duplicate:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(lead.to_dict()) + "\n")

    target = f"sms:{lead.phone}" if lead.phone else f"email:{lead.email}"
    print(json.dumps({
        "success": True,
        "duplicate": duplicate,
        "lead": lead.to_dict(),
        "first_touch": {"target": target, "message": message},
        "note": "If duplicate=true, do NOT re-send first-touch. Deliver message via send_message.",
    }, indent=2))


if __name__ == "__main__":
    main()
