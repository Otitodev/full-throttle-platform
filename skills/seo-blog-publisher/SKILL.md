---
name: seo-blog-publisher
description: Write and publish an SEO blog post to a client Astro site.
version: 0.1.0
author: Otito Ogene
license: MIT
metadata:
  hermes:
    tags: [seo, content, astro, blog, marketing]
    category: marketing
---

# SEO Blog Publisher Skill

Drafts an SEO-optimized blog post and publishes it as a Markdown file into a client's Astro site, where a commit triggers an automatic rebuild and deploy. This skill owns the *publishing* mechanics — slug, frontmatter, file placement, and git commit. The *content* is written by the agent. It does not do keyword research or rank tracking (separate skills).

## When to Use

- A scheduled `cronjob` fires the daily/weekly content cadence (user story B1).
- The owner asks for a post on a specific topic over SMS/email.
- You need a new article live on the client site without touching component code.

## Prerequisites

- The target site is an **Astro repo with the `blog` content collection** wired (`src/content.config.ts` defines `blog`; posts live in `src/content/blog/*.md`; pages render at `/blog/<slug>`).
- `git` is available and the repo has a committable working tree.
- Use the `terminal` tool to run the script and the `read_file` tool to inspect results.

## How to Run

1. Write the article body as Markdown (no frontmatter — the script adds it). Use `##`/`###` headings, short paragraphs, and bullet lists. End with a call-to-action linking to the estimate tool.
2. Save the body to a temp file, then run the publisher via the `terminal` tool:

```
python <skill_dir>/scripts/publish_post.py \
  --repo <path-to-astro-repo> \
  --title "How Much Does a Vinyl Fence Cost in Panama City?" \
  --category "Cost Guide" \
  --excerpt "Real per-foot vinyl fence pricing for Bay County homeowners." \
  --keyword "vinyl fence cost panama city" \
  --body-file <tmp>/post.md \
  --commit
```

3. The script prints a JSON result with `slug`, `path`, `url`, and `committed`. The commit triggers the Vercel rebuild.

## Quick Reference

| Flag | Purpose |
|------|---------|
| `--repo` | Astro repo root (required) |
| `--title` / `--category` / `--excerpt` | Frontmatter + listing card (required) |
| `--keyword` | Primary target keyword (optional, stored in frontmatter) |
| `--body` / `--body-file` | Markdown body, inline or from a file (one required) |
| `--date` | `pubDate` override (defaults to today) |
| `--slug` | Override the auto-generated slug |
| `--draft` | Mark as draft — won't render or list |
| `--overwrite` | Replace an existing post of the same slug |
| `--commit` | `git add` + commit the new file |

## Procedure

1. Confirm the topic and primary keyword (from the brief or the rank-tracker skill).
2. Draft 400–800 words of genuinely useful, location-specific content. Match the site's voice: direct, local, no fluff.
3. Write a ≤160-char `excerpt` for SEO meta and the blog-card preview.
4. Run the script with `--commit`. Verify the JSON `success: true`.
5. Optionally run `npm run build` in the repo to confirm the post compiles before the deploy lands.

## Pitfalls

- **Don't hand-edit `blog.astro` or component files** — this skill only writes `src/content/blog/*.md`. Layout/design changes are a different task.
- **Slugs are derived from the title.** Re-publishing the same title without `--overwrite` fails by design (prevents silent clobbering).
- **`pubDate` must be `YYYY-MM-DD`.** The Astro schema coerces it to a date; malformed dates fail the build.
- **Draft posts are invisible** (`draft: true` is filtered in both the index and `getStaticPaths`). Remove the flag to go live.
- **Keep markdown to what the post page styles** (h2, h3, p, ul/ol, strong, links). Raw HTML/tables aren't styled.

## Verification

- Script exits `0` and prints `"success": true`.
- The file exists at `<repo>/src/content/blog/<slug>.md` with valid frontmatter.
- `npm run build` in the repo succeeds and emits `dist/blog/<slug>/index.html`.
- `git log -1` shows the publish commit.
