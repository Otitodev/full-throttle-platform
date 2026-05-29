---
name: social-scheduler
description: Schedule real job photos and reviews to social channels.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [social, gbp, content, marketing, reputation]
    category: marketing
---

# Social Scheduler Skill

Schedules **real** job content — before/after photos and recycled customer reviews — to social
channels at a steady cadence (~2-3×/week), with the owner approving each batch. Social is a
**trust/proof surface, not a lead engine** for local home services, so this skill is deliberately
"basics done consistently." It owns the *mechanics* (pick real content, queue, publish on
schedule); the agent writes truthful captions and the owner approves.

**Hard guardrail: never fabricate.** Every post is built from a real asset or a real review.
Do not auto-generate generic/AI filler posts or invent projects, locations, or claims — that
both misleads and carries a measured engagement/authenticity penalty.

Posts go out through an **adapter**:
- `manual` (default) — writes scheduled posts to `outbox.jsonl`, a content calendar the operator
  (or a Buffer import) publishes. Use until platform API access lands.
- `gbp` — Google Business Profile posts (`localPosts`); reuses the **review skill's** Google
  `business.manage` token (see `../review-automation/references/gbp_setup.md`). No second OAuth.
- Facebook/Meta and Nextdoor are documented as later adapters (`references/social_setup.md`).

## When to Use

- A weekly `cronjob` builds the next batch of posts from real content for owner approval.
- A daily `cronjob` publishes approved posts that are now due.
- The owner asks to post a specific recent job photo or shout out a review.

## Prerequisites

- A per-client **assets manifest** (`assets.json`) of real job photos:
  `[{ "id", "image_path", "job_desc", "location" }]`. Owner-supplied (a photo texted in can be
  saved here).
- A **reviews source** — reuse the `review-automation` skill's reviews CSV/JSON (don't duplicate).
- Approval uses the `clarify` tool; owner notifications use `send_message`.
- `gbp` adapter: `GBP_LOCATION` + the Google token from the review skill's setup.
- Run scripts with the `terminal` tool; read results with `read_file`.

## How to Run

**Weekly batch-build (agent):**
1. `python <skill_dir>/scripts/pick_content.py --assets-file <assets.json> --reviews-file <reviews> --count 3`
   → real, unused candidates (photos + 4-5★ reviews).
2. For each, write a short, local, truthful caption (name the job/location; recycle the review's
   real words). No invented claims.
3. `clarify(question="Approve these 3 posts?", choices=["Approve","Edit","Skip"])`.
4. On **Approve**, enqueue each spread across the week:
   `python <skill_dir>/scripts/enqueue_post.py --kind photo --source-ref asset:a1 --image <path> --caption "…" --targets gbp,facebook --scheduled-at <ISO> --status approved`

**Daily publish (cron):**
- `python <skill_dir>/scripts/publish_due.py --adapter manual` → publishes approved posts whose
  `scheduled_at` has passed, marks them `posted` (dedup), and reports a summary.

## Quick Reference

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `pick_content.py` | Select real, unused photos/reviews | `--assets-file --reviews-file --count --min-rating` |
| `enqueue_post.py` | Queue an approved, captioned post | `--kind --caption --image --source-ref --targets --scheduled-at --status` |
| `publish_due.py` | Publish due approved posts (cron) | `--adapter {manual,gbp} --now --dry-run` |

Adapter flags: `--adapter`, `--outbox-dir` (manual), `--location`/`--token-path` (gbp), `--state-dir`.

## Cron specs

```
# Weekly batch-build (agent + approval)
cronjob(action="create", schedule="0 9 * * 1", skills=["social-scheduler"],
        script="pick_content.py --assets-file <a> --reviews-file <r> --count 3",
        prompt="Caption each real candidate truthfully; clarify() to approve the batch; on approval enqueue_post.py each spread across the week with status=approved.",
        deliver="origin")

# Daily publish
cronjob(action="create", schedule="0 14 * * *", skills=["social-scheduler"],
        script="publish_due.py --adapter manual", no_agent=True, deliver="origin")
```

## Procedure

1. Keep `assets.json` fed with real before/after photos from completed jobs.
2. Weekly: pick → caption (truthful) → owner approves batch → enqueue across the week (2-3×).
3. Daily: publish due posts; manual adapter fills the outbox for the operator/Buffer.
4. Flip to `--adapter gbp` once GBP access is set up (same token as reviews).

## Pitfalls

- **Never fabricate content.** `pick_content.py` only surfaces real, unused assets/reviews — build
  posts from those. Do not invent projects or use generic AI filler.
- **Nothing publishes without approval.** Posts enter the queue as `approved` only after the owner
  okays the batch via `clarify`. `publish_due.py` ignores non-approved/non-due posts.
- **`publish_due.py` dedups** by setting `status=posted`; a second run won't repost. Per-post
  failures are isolated and left for retry (status stays `approved`).
- **GBP photo posts need a public image URL** — a local file posts as text-only on `gbp`; host the
  image first, or rely on the manual outbox to attach it.
- **Profile isolation:** state lives under `<HERMES_HOME>/social-scheduler/`; scripts read
  `HERMES_HOME` from the env — never hardcode `~/.hermes`.

## Verification

- `pick_content.py` returns only real, unused items (≥`--min-rating` reviews); used items don't recur.
- `enqueue_post.py` appends to `queue.json` and records the source in `used.json`.
- `publish_due.py --adapter manual` writes due+approved posts to `outbox.jsonl`, marks `posted`;
  a second run publishes 0.
- `description` ≤ 60 chars; only native tools (`clarify`, `send_message`, `terminal`, `read_file`)
  named for approval/delivery.
