---
name: review-automation
description: Send review requests and draft replies to customer reviews.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [reviews, reputation, gbp, local-seo, marketing]
    category: marketing
---

# Review Automation Skill

Automates the highest-leverage local-SEO play: asking happy customers for reviews and
responding to the ones that land. It owns the *mechanics* — fetching reviews, building the
request message, posting an approved reply — through a provider adapter. The agent owns
*judgment*: drafting replies, getting owner approval, and delivering messages. It does not
do SEO content or rank tracking (separate skills).

Reviews come through an **adapter** so the source is swappable:
- `manual` (default) — reviews from a CSV/JSON file; approved replies written to a file for
  the operator to paste into Google. Use this until Google Business Profile API access lands.
- `gbp` — live Google Business Profile reads + reply posting (needs OAuth + API access; see
  `references/gbp_setup.md`). Flipping adapters is a flag change, no code change.

## When to Use

- **R1 — review request:** the owner texts "job done for <name> <phone>" (or supplies a list
  of completed jobs). Send each customer a review request.
- **R2 — review responses:** a scheduled `cronjob` checks for new reviews; draft a reply to
  each, get owner approval, post it.

## Prerequisites

- Delivery uses the `send_message` tool (SMS via Twilio / email via SMTP). Requires the
  client profile's `.env`: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
  (and/or `EMAIL_*` for email).
- Approval uses the `clarify` tool.
- Run the scripts with the `terminal` tool; read results with `read_file`.
- `manual` adapter: a reviews CSV/JSON the operator exports. `gbp` adapter: `GBP_LOCATION`
  (`accounts/{a}/locations/{l}`) + OAuth token (see `references/gbp_setup.md`).

## How to Run

**R1 — send a review request:**
1. Build the message: `python <skill_dir>/scripts/request.py --name "Jane D." --business "<Client>" --review-link "<google review url>" --customer "sms:+1850…"`
2. Take the `message` from the JSON output and deliver it with the `send_message` tool:
   `send_message(target="sms:+1850…", message="<message>")`.

**R2 — respond to new reviews (the agent's loop):**
1. `python <skill_dir>/scripts/fetch_reviews.py --adapter manual --reviews-file <path>` →
   JSON of NEW reviews (auto-deduped via `seen.json`).
2. For each review, draft a short, specific reply (thank by name, address specifics, stay warm).
3. Ask the owner with `clarify(question="Post this reply to <author>'s review?", choices=["Post", "Edit", "Skip"])`.
4. On **Post**: `python <skill_dir>/scripts/post_response.py --adapter manual --reviews-file <path> --review-id <id> --text "<reply>"`.
5. Confirm to the owner with `send_message`.

## Quick Reference

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `request.py` | Build a review-request message (R1) | `--name --business --review-link`/`--place-id --customer` |
| `fetch_reviews.py` | List new reviews since last run (R2) | `--adapter --reviews-file` / `--location`; `--peek --all --reset` |
| `post_response.py` | Post an approved reply (R2) | `--adapter --review-id --text`/`--text-file` |

Common adapter flags: `--adapter {manual,gbp}`, `--reviews-file`/`--responses-dir` (manual),
`--location`/`--token-path` (gbp), `--state-dir` (override profile state).

## Cron spec (R2 monitor)

```
cronjob(action="create",
        schedule="0 9 * * *",
        skills=["review-automation"],
        script="fetch_reviews.py --adapter manual --reviews-file <path>",
        prompt="For each new review in the context: draft a short specific reply, use clarify to get owner approval, on approval run post_response.py, then confirm via send_message.",
        deliver="origin")
```

`fetch_reviews.py` stdout is injected into the prompt; the agent drafts, gates on `clarify`,
and posts. Cron sessions run with a 3-minute hard interrupt.

## Procedure

1. Pick the adapter for the client (manual until GBP access; then gbp).
2. R1: build + deliver requests for completed jobs; the script logs each to `requests.jsonl`.
3. R2: fetch new reviews → draft → `clarify` approval → post → confirm.
4. Keep replies real and specific (E-E-A-T): name the customer, reference their job, no
   boilerplate. Negative reviews → de-escalate, apologize, move offline — always via approval.

## Pitfalls

- **The scripts never send or auto-post without approval.** Delivery is the agent's
  `send_message` call; posting a reply is gated by `clarify`. Don't bypass either.
- **`fetch_reviews.py` marks reviews seen on fetch** (so the cadence doesn't re-surface them).
  Use `--peek` to inspect without persisting, `--reset` to clear state.
- **Manual replies aren't live** — they're appended to `review_responses.jsonl` for the
  operator to paste into Google. Only the `gbp` adapter posts to Google directly.
- **Don't fabricate review content.** Only act on reviews the adapter returns.
- **Profile isolation:** state lives under `<HERMES_HOME>/review-automation/`; never hardcode
  `~/.hermes` — the scripts read `HERMES_HOME` from the env.

## Verification

- `fetch_reviews.py` exits 0, prints `success: true`; a second run reports `new_count: 0` (dedup).
- `post_response.py` (manual) appends to `review_responses.jsonl`; (gbp) returns `posted: true`.
- `request.py` prints a message containing the review link and logs to `requests.jsonl`.
- `description` ≤ 60 chars; the skill references only native tools (`send_message`, `clarify`,
  `terminal`, `read_file`) for delivery/approval.
