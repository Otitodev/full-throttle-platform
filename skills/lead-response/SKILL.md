---
name: lead-response
description: Respond to inbound leads in seconds and sync them to CRM.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [leads, speed-to-lead, crm, sms, marketing]
    category: marketing
---

# Lead Response Skill

Wins jobs on **speed-to-lead**: when a lead arrives, reply to the customer within seconds with
an approved first-touch message, then qualify and sync the lead to the client's CRM. 78% of
customers hire the first responder; a sub-60s reply lifts conversion ~391%. This skill owns the
*mechanics* (normalize, dedup, first-touch template, CRM sync); the agent handles qualification
and booking; nothing here mutates the client's website.

Leads arrive through the Hermes **`webhook` gateway adapter** (a `POST /webhooks/lead` from a
web form or LSA export) — see `references/webhook_setup.md`. CRM sync goes through an **adapter**:
- `manual` (default) — leads appended to `leads_crm.jsonl` for the operator to import. Demo path.
- `jobber` — creates a client in Jobber (gated; see `references/crm_setup.md`). Flip is a flag.

## When to Use

- A lead POSTs to the gateway `webhook` route → this skill is loaded for that turn (L1).
- A customer replies to a first-touch → qualify and offer booking.
- You need a lead recorded in the CRM (L2).

## Prerequisites

- The gateway `webhook` route configured in the profile (`platforms.webhook.extra.routes.lead`)
  with an HMAC `secret` and `skills: ["lead-response"]` — see `references/webhook_setup.md`.
- Delivery via the `send_message` tool (SMS/Twilio + email/SMTP): `TWILIO_*` / `EMAIL_*` in `.env`.
- `clarify` for owner escalation; `terminal` to run scripts; `read_file` for results.
- Phone numbers should be **E.164** (`+1850…`) so SMS delivery works.
- `jobber` adapter: OAuth token (see `references/crm_setup.md`).

## How to Run (the webhook-triggered turn)

1. `python <skill_dir>/scripts/intake.py --payload-file <lead.json> --business "<Client>"` →
   structured lead + a `first_touch` `{target, message}`; logs to `leads.jsonl`; reports `duplicate`.
2. **If not duplicate, immediately** deliver the first-touch via the tool:
   `send_message(target="sms:+1850…", message="<first_touch.message>")`. (Skip if duplicate.)
3. `python <skill_dir>/scripts/sync_lead.py --adapter manual --name … --phone … --email … --source … --message …`
   → records the lead in the CRM (idempotent).
4. Notify the owner: `send_message(target="sms:+<owner>", message="New lead: …")`.
5. When the customer replies (a fresh inbound turn for that number), qualify and offer a booking
   time. Escalate with `clarify` only when you need the owner.

## Quick Reference

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `intake.py` | Normalize + dedup + first-touch | `--payload-file` or `--name/--phone/--email/--message/--source`; `--business --template` |
| `sync_lead.py` | Record lead in CRM | `--adapter {manual,jobber}` + lead flags; `--crm-dir` / `--token-path` |

## Procedure

1. Lead hits the webhook → agent gets the rendered payload + this skill.
2. `intake.py` → if new, `send_message` the templated first-touch **fast** (the whole point).
3. `sync_lead.py` → CRM; notify owner.
4. Converse to qualify (services, location, timeline, budget) → offer a booking → escalate only if needed.

## Pitfalls

- **First-touch is a template, not free text.** Speed + the governance "restricted templates"
  guardrail — don't compose a novel first message; deliver `intake.py`'s rendered copy.
- **Respect `duplicate`.** `intake.py` (plus the webhook's built-in delivery_id idempotency) prevents
  double-replying; if `duplicate=true`, do not re-send the first-touch.
- **<60s matters.** Send the first-touch before doing slower work (CRM sync, owner notify).
- **Phones must be E.164** for SMS; the webhook payload should supply `+1…` numbers.
- **No website edits here** — this skill only messages + records leads.
- **Profile isolation:** state under `<HERMES_HOME>/lead-response/`; scripts read `HERMES_HOME`
  from the env — never hardcode `~/.hermes`.

## Verification

- `intake.py` on a sample lead prints a structured lead + first-touch and logs to `leads.jsonl`;
  a second identical lead → `duplicate: true`.
- `sync_lead.py --adapter manual` appends to `leads_crm.jsonl`; rerun → `duplicate: true`.
- `description` ≤ 60 chars; only native tools (`send_message`, `clarify`) named for reply/approval.
- Integration (running gateway): a signed `POST /webhooks/lead` triggers a first-touch within
  seconds and is idempotent on replay (see `references/webhook_setup.md`).
