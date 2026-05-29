# Tool-permission scope matrix & governance policy

The constraint-first contract (G1) plus the surrounding policy (plans, idempotency, approvals,
rollback). Runtime enforcement is Hermes' — this doc + `scopes.py` keep configs honest.

## Per-agent tool scope (G1)

Workers are spawned by the Supervisor with `delegate_task(toolsets=[...], role="leaf")`. Leaf role
strips `delegate_task / clarify / memory / send_message / execute_code`, and a child's toolsets are
intersected with the parent's. Give each worker only what its job needs:

| Worker | Allowed toolsets / tools | Explicitly NOT allowed |
|--------|--------------------------|------------------------|
| **Supervisor** (orchestrator) | delegation, clarify, reporting, send_message | direct site/CRM mutation |
| **Lead-Response** | send_message (SMS/email), terminal (run lead-response scripts) | website edits, CRM schema changes, code_execution |
| **Reputation** | terminal (review scripts), clarify | site edits, ad spend, code_execution |
| **GBP** | terminal (GBP scripts) | business-detail edits without approval, code_execution |
| **Content** | terminal (content-publisher) | page redesign, nav/homepage overwrite, code_execution |
| **Social** | terminal (social-scheduler) | anything beyond scheduling real content, code_execution |

Profile-level caps (written by onboarding into `config.yaml`):

```yaml
agent:
  disabled_toolsets: [code_execution]   # no unrestricted code exec in production
```

`scopes.py check --config <profile>/config.yaml` lints that these caps are present.

## Execution plans (G2)

Before mutating an external system, emit a plan with `plan.py`:
`{intent, target, actions, requires_approval}`. Risky intents (publish, delete, push, deploy,
charge, refund, overwrite, unpublish) are flagged `requires_approval` — gate them with the
`clarify` tool and only proceed on owner approval. The plan is recorded as a `planned` audit row.

## Idempotency (G3)

Every external action is dedup'd + retry-safe — already practiced per skill:
- content-publisher: slug-collision guard; `--overwrite` required to replace.
- review-automation: `seen.json` (reviews handled once).
- social-scheduler: `posted` status + `used.json` (no re-post / re-use).
- lead-response: webhook delivery_id idempotency + phone/email dedup in `intake.py`.

Do not add retry loops that defeat these.

## Audit log (G4)

Append-only `<HERMES_HOME>/governance/audit.jsonl`, one row per mutation:
`{id, ts, skill, action, target, status, rollback_ref, approval_state, repo}`. Written
automatically by the capability skills + the governance `audit.py` CLI. Never edited in place.

## Rollback (G4)

`revert.py --audit-id <id>` undoes a mutation via its `rollback_ref`:
- astro-git / proxy-subdir (commit SHA + repo) → `git revert --no-edit <sha>`.
- wordpress-rest (post id) → delete/unpublish (manual step unless WP creds wired).
- others → manual guidance.
Each revert is itself logged.

## Observability (G5)

`status.py` synthesizes the audit log into a timeline, an approval queue (rows with
`approval_state=pending`), and counts — folding in Hermes' own cron status (`cron/jobs.json`).
Pair with Hermes' built-ins: `hermes logs --follow`, the dashboard (`/api/sessions`,
`/api/cron/jobs`), and per-session cost in `state.db`.
