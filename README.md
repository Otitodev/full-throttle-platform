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

All skills follow the same shape (a `PublishAdapter`-style provider layer with a `manual`
fallback, `_common.py`, JSON-to-stdout scripts, HERMES_HOME-aware state, no Hermes imports).

- **content-publisher** — publish a blog post via an adapter: `astro-git` (greenfield),
  `wordpress-rest`, `proxy-subdir` (Cloudflare Worker @ `client.com/blog`), or `manual`.
- **review-automation** — post-job review requests + AI-drafted review replies (GBP / manual adapters).
- **social-scheduler** — schedule real photos + recycled reviews to GBP/Facebook/Nextdoor (basics).
- **lead-response** — instant first-touch to inbound web-form leads + CRM sync (Jobber / manual).

Each lives under `skills/<name>/` with `SKILL.md` + `scripts/` + `references/`.

## Onboarding a client

`scripts/onboard_client.py` provisions a new client as an isolated Hermes profile (augment
mode): config, secrets → `.env`, the four skills, and seeded brand/memory context, plus a
`NEXT_STEPS.md` runbook. Driven by a non-secret `intake.json` + a gitignored `secrets.json`.

```
python scripts/onboard_client.py --intake intake.json --secrets secrets.json [--dry-run]
```

See `scripts/ONBOARDING.md` for the full runbook and `scripts/intake.example.json` /
`scripts/secrets.example.json` for templates.

## Installing a skill into a profile

Skills are sourced from this repo and installed into a Hermes profile's skills dir,
e.g. `~/.hermes/profiles/mrfence/skills/`. Keep this repo as the source of truth and
the per-profile copy as the runtime instance. (The onboarding script does this copy for you.)
