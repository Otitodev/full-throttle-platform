# Social channel setup

The skill runs on the `manual` adapter by default (no setup beyond an assets manifest). These
notes cover the real publishing adapters.

## Outbox format (manual adapter)

`publish_due.py --adapter manual` appends one JSON object per line to
`<HERMES_HOME>/social-scheduler/outbox.jsonl`:

```json
{"published_at":"…","targets":["gbp","facebook"],"kind":"photo","caption":"…","image_path":"…","source_ref":"asset:a1","post_id":"…"}
```

The operator (or a Buffer import job) reads this calendar and posts to each channel. This is the
demo path and the fallback whenever a platform API isn't wired.

## Google Business Profile posts (`gbp` adapter)

GBP posts use the same Google OAuth + `business.manage` scope as the review-automation skill — set
it up once (see `../../review-automation/references/gbp_setup.md`) and reuse
`<HERMES_HOME>/google_token.json`. Then publish with:

```
python scripts/publish_due.py --adapter gbp --location accounts/<a>/locations/<l>
```

Note: GBP `localPosts` media requires a **public image URL** (`sourceUrl`). A local-file photo is
posted as text-only; host the image (or keep it in the manual outbox where the operator attaches
it) to include the photo.

## Facebook / Meta (later adapter)

A `meta` adapter would post to a Facebook Page via the Graph API. Requires a Facebook Page, a Page
access token, and Meta app review for content-publishing permissions. Gated — not built for the
MVP; the manual outbox covers Facebook in the meantime.

## Nextdoor (manual only)

Nextdoor has no open automated-posting API (partner-gated). Treat Nextdoor as a manual-outbox
target — the operator posts these by hand from the content calendar.

## Buffer (optional fan-out)

Instead of per-platform adapters, the manual outbox can feed Buffer, which fans out to Facebook,
Instagram, etc. from one integration. Adds a paid Buffer dependency; useful once volume grows.
