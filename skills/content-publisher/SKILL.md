---
name: content-publisher
description: Publish blog posts to Astro, WordPress, or a proxied blog.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [seo, content, publishing, wordpress, astro, marketing]
    category: marketing
---

# Content Publisher Skill

Publishes an SEO blog post to whatever surface a client has, via a **publishing adapter**. The
agent writes a truthful, locally-specific post; this skill handles slug, frontmatter/HTML,
placement, and idempotency. It does not write the post content or do keyword research (separate
concerns). One skill, four adapters — chosen per client from their profile:

- `astro-git` — write a frontmatter `.md` into a greenfield Astro repo's `blog` collection; git commit.
- `wordpress-rest` — POST to the client's existing WordPress REST API (markdown → HTML).
- `proxy-subdir` — publish to an Astro blog WE host; a Cloudflare Worker serves it at
  `client.com/blog` (augment a locked CMS without migrating). See `references/proxy_subdir_setup.md`.
- `manual` — render the post (md + HTML) to an outbox file for manual posting.

## When to Use

- The SEO/Content agent has a finished post body and needs it live on the client's site.
- Greenfield clients → `astro-git`; existing WordPress → `wordpress-rest`; locked/legacy CMS →
  `proxy-subdir`; no target wired yet → `manual`.

## Prerequisites

- Run via the `terminal` tool; read results with `read_file`.
- `astro-git` / `proxy-subdir`: a path to the Astro repo (`--repo`); `git` available for `--commit`.
- `proxy-subdir`: `--public-base` (client domain) + the Worker deployed (`references/proxy_subdir_setup.md`).
- `wordpress-rest`: `--wp-url`, `--wp-user`, and `WP_APP_PASSWORD` in `.env`
  (see `references/wordpress_setup.md`).

## How to Run

```
python <skill_dir>/scripts/publish.py --adapter <astro-git|wordpress-rest|proxy-subdir|manual> \
  --title "…" --category "…" --excerpt "…" [--keyword "…"] [--author "…"] [--date YYYY-MM-DD] \
  --body-file <post.md> [adapter-specific flags] [--draft] [--dry-run]
```

- astro-git: `--repo <site> [--commit]`
- proxy-subdir: `--repo <our-blog> --public-base https://client.com [--commit]`
- wordpress-rest: `--wp-url https://client.com --wp-user <user>` (+ `WP_APP_PASSWORD` env) `[--categories 3,7]`
- manual: `[--outbox-dir <dir>]`

Output is JSON with `slug`, `url`, and a `rollback_ref` (git SHA / WP post id) for governance.
Use `--dry-run` (wordpress-rest) to preview the exact POST payload without publishing.

## Quick Reference

| Adapter | Target | Key flags | rollback_ref |
|---------|--------|-----------|--------------|
| `astro-git` | greenfield Astro repo | `--repo --commit` | git commit SHA |
| `wordpress-rest` | existing WordPress | `--wp-url --wp-user` + `WP_APP_PASSWORD`; `--dry-run` | WP post id |
| `proxy-subdir` | our Astro blog @ client.com/blog | `--repo --public-base --commit` | git commit SHA |
| `manual` | outbox file (md + HTML) | `--outbox-dir` | — |

## Procedure

1. Pick the adapter for the client (recorded in their profile).
2. Write a real, E-E-A-T-respecting post (real local data/photos, named author) — no thin or
   fabricated content; that's what keeps it from being penalized.
3. Run `publish.py`; verify `success: true` and the returned `url`.
4. Record the `rollback_ref` so a bad post can be reverted (git revert / WP delete).

## Pitfalls

- **Real content only.** Templated/AI-thin posts and mass templated location pages get de-ranked
  — inject genuine local detail.
- **Slug collisions are guarded.** Re-publishing the same slug fails (astro/proxy) or skips
  (wordpress) unless `--overwrite` — prevents silent clobbering / duplicates.
- **WordPress needs Application Passwords**, not your login password; phone the body through
  `--dry-run` first to check the HTML conversion.
- **proxy-subdir reports the client's domain URL**, but serving requires the Worker deployed; the
  content itself lives in our hosted repo.
- **Profile isolation:** scripts read `HERMES_HOME` from the env — never hardcode `~/.hermes`.

## Verification

- Each adapter exits 0 with `success: true`; astro-git/proxy-subdir write the `.md`,
  wordpress-rest `--dry-run` prints the payload, manual writes md+html.
- `description` ≤ 60 chars; only the native `terminal`/`read_file` tools are referenced.
- A duplicate slug is rejected/skipped without `--overwrite`.
