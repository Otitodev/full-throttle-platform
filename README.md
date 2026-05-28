# Full Throttle Platform

Platform tooling for the Full Throttle Marketing autonomous agent system, built on
[Hermes Agent](https://github.com/NousResearch/hermes-agent). This repo holds the
**platform layer** — kept separate from both the Hermes framework and any client site.

## What lives here

- `skills/` — Hermes skills the agents use (SEO publishing, rank tracking, social, onboarding).

## What does NOT live here

- **The Hermes framework** — installed separately; this repo is tooling that runs *on* Hermes.
- **Client sites** — each client is its own Astro repo (e.g. `mrfence-site`), deployed to Vercel. Skills write into a client repo via a `--repo` path; they are never copied into it.
- **Runtime state** — API keys, sessions, active profiles live in `~/.hermes/profiles/<client>/`, not in version control.

## Three-layer architecture

| Layer | Repo / location | Deploys to |
|-------|-----------------|-----------|
| Platform tooling | this repo | your server (DigitalOcean) |
| Client site (per client) | `mrfence-site` and clones | Vercel |
| Runtime profile | `~/.hermes/profiles/<client>/` | local machine state |

## Skills

### seo-blog-publisher
Writes an SEO blog post as Markdown into a client's Astro `blog` collection and
optionally git-commits it (which triggers the client's Vercel rebuild). See
`skills/seo-blog-publisher/SKILL.md`.

## Installing a skill into a profile

Skills are sourced from this repo and installed into a Hermes profile's skills dir,
e.g. `~/.hermes/profiles/mrfence/skills/`. Keep this repo as the source of truth and
the per-profile copy as the runtime instance.
