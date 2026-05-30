<!-- markdownlint-disable line-length -->
# Full Throttle Platform

[![CI](https://github.com/Otitodev/full-throttle-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Otitodev/full-throttle-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Hermes](https://img.shields.io/badge/runs%20on-Hermes%20Agent-6c5ce7.svg)](https://github.com/NousResearch/hermes-agent)

**AI-powered marketing operations for local service businesses.** Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). Augments existing websites and CRMs — lead response, reputation management, GBP optimization, and content publishing — without replacing what already works.

> Convert more inbound leads into booked jobs while increasing local trust signals.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [Onboarding a client](#onboarding-a-client)
  - [Running the gateway](#running-the-gateway)
  - [Cron jobs](#cron-jobs)
- [Project Structure](#project-structure)
- [Skills](#skills)
- [Publishing Adapters](#publishing-adapters)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **⚡ Instant lead response** — replies within seconds of web form submission, qualifies, and syncs to CRM. 391% conversion lift over delayed response.
- **⭐ Reputation automation** — post-job review requests, AI-drafted replies, negative-review escalation with approval gating.
- **🏢 GBP management** — Google Business Profile posts, Q&A, category audits, update reminders.
- **✍️ Content publishing** — localized blog posts published into existing CMS (WordPress, subdirectory proxy) via pluggable adapters. Augment-first — never migrates or rebuilds.
- **📋 Weekly reporting** — leads, reviews, rankings, and content stats compiled and delivered to the owner.
- **🛡️ Governance layer** — execution plans, tool-permission scopes, audit logging, rollback. Every mutation is logged, approved when risky, and revertible.
- **🏗️ Per-client isolation** — each client runs as a separate Hermes profile with its own credentials, memories, skills, and state.
- **⏰ Cron-driven cadence** — autonomous content, review, and social workflows on schedule.

---

## Architecture

```
┌─ SOURCE (git) ───────────────────────────────────┐
│  full-throttle-platform/    hermes-agent/         │
│  (skills, adapters,         (the engine, OSS)     │
│   scripts, cron specs)                            │
└──────────────────────┬───────────────────────────┘
                       │ onboard_client.py installs
                       ▼
┌─ RUNTIME (DigitalOcean) ───────────────────────────┐
│  Hermes Gateway (per client profile)               │
│  ~/.hermes/profiles/<client>/                      │
│    ├── .env          (API keys, chmod 600)         │
│    ├── config.yaml   (model, adapter, toolsets)    │
│    ├── skills/       (platform skills)             │
│    ├── memories/     (MEMORY.md, USER.md)          │
│    └── state.db      (sessions, FTS5 search)       │
│                                                    │
│  Supervisor → delegate_task() workers:             │
│    Lead-Response | Reputation | GBP | Content      │
└──────────────────────┬───────────────────────────┘
                       │ publishes into / syncs with
                       ▼
          Client's existing site + CRM + GBP
```

Three triggers wake the agent: an inbound lead, an owner SMS, or a cron tick.

📖 See the full diagrams: [ARCHITECTURE_DIAGRAMS.md](docs/ARCHITECTURE_DIAGRAMS.md) (Mermaid) and [ARCHITECTURE.md](ARCHITECTURE.md) (prose).

---

- **content-publisher** — publish a blog post via an adapter: `astro-git` (greenfield),
  `wordpress-rest`, `proxy-subdir` (Cloudflare Worker @ `client.com/blog`), or `manual`.
- **review-automation** — post-job review requests + AI-drafted review replies (GBP / manual adapters).
- **social-scheduler** — schedule real photos + recycled reviews to GBP/Facebook/Nextdoor (basics).
- **lead-response** — instant first-touch to inbound web-form leads + CRM sync (Jobber / manual).
- **governance** — the guardrail layer: per-client audit log of every mutation, execution
  plans + approval gating, rollback, a status/timeline view, and the tool-permission scope
  matrix. The four skills above auto-append to its audit log.

### Prerequisites

- **Hermes Agent** installed ([install guide](https://github.com/NousResearch/hermes-agent#quick-start))
- **Python 3.10+** with `pyyaml`
- API keys: Anthropic (or OpenRouter/OpenAI), Twilio, WordPress (if using), Jobber (if using)

### 1. Clone the platform

```bash
git clone https://github.com/Otitodev/full-throttle-platform.git
cd full-throttle-platform
```

### 2. Prepare your client data

Copy and fill in the example files:

```bash
cp scripts/intake.example.json intake.json
cp scripts/secrets.example.json secrets.json
# Edit both with real client data and API keys
```

### 3. Onboard the client

```bash
# Dry-run first — see what will be created
python scripts/onboard_client.py --intake intake.json --secrets secrets.json --dry-run

# Go live
python scripts/onboard_client.py --intake intake.json --secrets secrets.json
```

### 4. Start the gateway

```bash
hermes -p <client-slug> gateway
```

The agent sends a welcome SMS and is live.

---

## Usage

### Onboarding a client

```bash
python scripts/onboard_client.py \
  --intake intake.json \
  --secrets secrets.json \
  [--dry-run] \
  [--force] \
  [--profiles-root /custom/path]
```

**What it creates** (under `~/.hermes/profiles/<slug>/`):

| Step | Artifact | Purpose |
|------|----------|---------|
| 1 | Profile directory | Hermes `profile create <slug>` |
| 2 | `config.yaml` | Model, adapter, site_type, platforms |
| 3 | `.env` (chmod 600) | API keys: Anthropic, Twilio, WP, Jobber, webhook secret |
| 4 | `skills/` | content-publisher, review-automation, social-scheduler, lead-response |
| 5 | `memories/MEMORY.md` | Business facts (phone, domain, service area, keywords) |
| 6 | `memories/USER.md` | Owner contact and preferences |
| 7 | `AGENTS.md` | Brand voice, hard rules, guardrails |
| 8 | `NEXT_STEPS.md` | Manual runbook (Twilio provisioning, webhook wiring, etc.) |
| 9 | Cron jobs | Registered via `hermes -p <slug> cron add` |

Read the full runbook: [scripts/ONBOARDING.md](scripts/ONBOARDING.md)

### Running the gateway

```bash
hermes -p <client-slug> gateway        # foreground
hermes -p <client-slug> gateway run    # same
hermes -p <client-slug> gateway install  # install as systemd service
hermes -p <client-slug> gateway start    # start the service
```

### Cron jobs

Created automatically during onboarding. Manage manually:

```bash
hermes -p <client-slug> cron list                 # list all jobs
hermes -p <client-slug> cron run <job-id>         # trigger immediately
hermes -p <client-slug> cron pause <job-id>       # pause a job
hermes -p <client-slug> cron edit <job-id>        # edit schedule/prompt
```

Default cadence (customizable via `cadence` in intake):

| Job | Schedule | Skill |
|-----|----------|-------|
| Review automation | `0 9 * * *` (daily 9am) | review-automation |
| Social scheduling | `0 10 * * 1,3,5` (Mon/Wed/Fri) | social-scheduler |
| Content publishing | `0 9 * * 1` (Monday) | content-publisher |
| Weekly report | `0 8 * * 1` (Monday) | — |

### Deployment (production)

A turnkey single-droplet packaging is in [`infra/`](infra/README.md): Caddy auto-TLS, subdomain
per client (`<slug>.hooks.<domain>`), one systemd unit per gateway, and a deterministic per-client
webhook port allocated by `onboard_client.py` (registry at `~/.hermes/ports.json`).

```bash
# On a fresh Debian/Ubuntu droplet, as root:
sudo bash infra/install_server.sh        # one-time: Caddy + Hermes + Node + systemd unit
python3 scripts/onboard_client.py …      # per client (as before)
sudo bash infra/promote_client.sh <slug> --base-domain hooks.<your-domain>
# → live at https://<slug>.hooks.<your-domain>/webhooks/lead
```

Full runbook: [`infra/README.md`](infra/README.md).

---

## Project Structure

```
full-throttle-platform/
├── README.md                       ← you are here
├── LICENSE                         ← MIT
├── ARCHITECTURE.md                 ← full architecture doc
├── REVISION.md                     ← v2 proposal & decisions
├── MARKET_RESEARCH.md              ← research backing design choices
├── docs/
│   └── ARCHITECTURE_DIAGRAMS.md    ← Mermaid diagrams (e2e flows)
├── scripts/
│   ├── onboard_client.py           ← main onboarding pipeline
│   ├── ONBOARDING.md               ← operator runbook
│   ├── intake.example.json         ← template (non-secret)
│   └── secrets.example.json        ← template (secret keys)
├── infra/                          ← deployment packaging (production)
│   ├── README.md                   ← runbook: provision → install → onboard → promote
│   ├── install_server.sh           ← one-shot droplet bootstrap
│   ├── promote_client.sh           ← per-client: Caddy fragment + systemd enable
│   ├── caddy/
│   │   ├── Caddyfile               ← base config
│   │   └── example-client.caddy    ← per-client fragment template
│   └── systemd/
│       └── hermes-gateway@.service ← templated unit (one per slug)
├── skills/
│   ├── content-publisher/          ← blog publishing via adapters
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── publish.py
│   │   │   ├── _common.py
│   │   │   └── adapters/
│   │   │       ├── base.py         ← PublishAdapter interface
│   │   │       ├── wordpress_rest.py
│   │   │       ├── proxy_subdir.py
│   │   │       ├── astro_git.py
│   │   │       └── manual.py
│   │   └── references/
│   ├── review-automation/          ← review requests + replies
│   ├── social-scheduler/           ← photo + review scheduling
│   ├── lead-response/              ← instant lead first-touch
│   └── governance/                 ← execution plans, audit, rollback
└── .github/
    └── workflows/
        └── ci.yml                  ← lint (ruff) + dry-run test
```

---

## Skills

Every skill follows the same pattern: `SKILL.md` (metadata + instructions), `scripts/` (executable Python, JSON-to-stdout), `references/` (setup guides), and a provider-adapter layer with a `manual` fallback. No Hermes imports — scripts are plain Python usable by any Hermes agent.

| Skill | What it does | Adapters |
|-------|-------------|----------|
| **content-publisher** | Draft + publish blog posts to the client's CMS | wordpress-rest, proxy-subdir, astro-git, manual |
| **review-automation** | Send post-job review requests, draft AI replies | gbp, manual |
| **social-scheduler** | Schedule real photos + reviews to social platforms | gbp, manual |
| **lead-response** | Instant first-touch to inbound web leads, CRM sync | jobber, manual |

---

## Publishing Adapters

The `content-publisher` skill ships with pluggable adapters — chosen per client and recorded in their profile config.

| Adapter | Target | Use case |
|---------|--------|----------|
| `wordpress-rest` | WordPress REST API (Application Passwords) | Most common — existing WP sites |
| `proxy-subdir` | Astro blog served at `client.com/blog` via Cloudflare Worker | SEO equity retained; no migration |
| `astro-git` | Greenfield Astro repo (git commit + Vercel deploy) | Fallback — client with no site |
| `manual` | Outbox file (Markdown + HTML) | Fallback — no wired target |

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — full architecture, component map, data flows, governance
- [ARCHITECTURE_DIAGRAMS.md](docs/ARCHITECTURE_DIAGRAMS.md) — Mermaid diagrams (system, flows, state machines)
- [REVISION.md](REVISION.md) — v2 proposal, design decisions, deferred scope
- [MARKET_RESEARCH.md](MARKET_RESEARCH.md) — research citations backing design choices
- [scripts/ONBOARDING.md](scripts/ONBOARDING.md) — operator runbook for onboarding a client
- [infra/README.md](infra/README.md) — deployment runbook (server bootstrap, promote-to-live)

---

## Contributing

Contributions welcome. Please open an issue or submit a PR.

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push to the branch (`git push origin feat/my-feature`)
5. Open a pull request

**Conventions:**
- Python 3.10+, formatted with [ruff](https://github.com/astral-sh/ruff)
- CI runs on every push and PR (`ruff check --diff .` + dry-run onboarding)
- No secrets in version control — use `.env` files outside the repo
- Skills follow the `SKILL.md` + `scripts/` + `references/` layout

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgments

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) by [Nous Research](https://nousresearch.com/). The platform layer is independent of the Hermes framework and maintained separately.
