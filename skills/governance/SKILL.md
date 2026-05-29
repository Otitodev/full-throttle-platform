---
name: governance
description: Audit, plan, roll back, and scope agent mutations.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [governance, audit, rollback, observability, safety]
    category: marketing
---

# Governance Skill

The constraint-first guardrail layer that lets agents safely touch a client's live business.
It does NOT do marketing work — it records, gates, reverts, and reports on what the other skills
do. Every client-facing mutation (publish, review reply, social post, lead first-touch, CRM sync)
is appended to a per-client audit log; risky actions are planned + owner-approved; bad actions can
be rolled back; and the operator gets a timeline + approval queue.

Reuses Hermes for what it already enforces — per-worker tool scoping
(`delegate_task(toolsets=[...], role="leaf")`), per-session cost (`state.db`), cron status, and
logs — and only adds the business-level gaps.

## When to Use

- Always-on: the 4 capability skills auto-append to the audit log (no action needed).
- Before a risky mutation: emit an execution plan and gate it with `clarify`.
- After a bad mutation: roll it back by audit id.
- Anytime: show the operator a status/timeline + approval queue.

## Prerequisites

- Run via the `terminal` tool. Owner approval uses the `clarify` tool.
- Audit log lives at `<HERMES_HOME>/governance/audit.jsonl` (per profile).

## How to Run

```
# Log a mutation (the capability skills do this automatically)
python <skill>/scripts/audit.py log --skill content-publisher --action publish \
  --target /blog/x --status ok --rollback-ref <sha> --repo <repo>

# Plan + classify a mutation before doing it (risky → gate with clarify)
python <skill>/scripts/plan.py --intent publish_post --target /blog/y --actions "publish"

# Status / timeline / approval queue
python <skill>/scripts/status.py           # human;  --json for machine

# Roll back a logged mutation
python <skill>/scripts/revert.py --audit-id <id>

# Lint a profile's tool-permission caps (G1)
python <skill>/scripts/scopes.py check --config <profile>/config.yaml
```

## Quick Reference

| Script | Purpose | Notes |
|--------|---------|-------|
| `audit.py` | `log` / `tail` / `query` the mutation log | canonical writer/reader |
| `plan.py` | emit + classify an execution plan | risky → `requires_approval` (gate w/ clarify) |
| `revert.py` | undo a mutation by audit id | git revert (astro/proxy) or manual (WordPress) |
| `status.py` | timeline + approval queue + counts | folds in cron status; `--json` |
| `scopes.py` | lint profile tool caps vs the matrix | see `references/scope_matrix.md` |

## Audit record

One JSON object per line in `audit.jsonl`:
`{id, ts, skill, action, target, status, rollback_ref, approval_state, repo}`.
The capability skills append a row at each mutation point via a tiny `audit()` helper in their
own `_common.py` — there are no cross-skill imports; the shared contract is just this file format.

## Procedure

1. For a risky change: `plan.py` → if `requires_approval`, `clarify(...)` the owner → on approval, do it.
2. The capability skill performs the mutation and auto-logs it (with a `rollback_ref`).
3. `status.py` surfaces the timeline + anything pending.
4. If something's wrong: `revert.py --audit-id <id>`.

## Pitfalls

- **Don't bypass plans/approval for risky intents** (publish/delete/push/charge) — `plan.py` flags
  them; gate with `clarify`.
- **Rollback is adapter-specific**: git-backed publishes auto-revert; WordPress/API actions print
  a manual step unless creds are wired.
- **Idempotency is policy**: the capability skills dedup their own actions (seen/posted/used state,
  slug guards) — don't add retry loops that defeat it.
- **Profile isolation**: state under `<HERMES_HOME>/governance/`; never hardcode `~/.hermes`.

## Verification

- `audit.py log` then `tail`/`query` round-trips a record.
- `plan.py` flags a risky intent `requires_approval: true`.
- `revert.py` git-reverts a git-backed publish; prints manual steps for a WordPress row.
- `status.py --json` is valid and lists the approval queue.
- `scopes.py check` fails an uncapped profile and passes a capped one.
- `description` ≤ 60 chars; references only native tools (`terminal`, `clarify`).
