# Full Throttle Marketing — Architecture

How the platform works, what runs where, and how data flows. Built on
[Hermes Agent](https://github.com/NousResearch/hermes-agent). Every component below
maps to a real Hermes mechanism (gateway, cron, delegation, profiles, skills, tools).

## 1. The core idea

Hermes is the **engine**. We don't build an orchestration graph — we run Hermes agent
processes. Each gets a working directory (a client's Astro repo), a set of skills, a
schedule (cron), and a way to be reached (the gateway). The agent uses **tools**
(terminal/git, file edit, web) to do the work and **delegation** to fan out into
specialist sub-agents. "The agent is the developer" because committing markdown to a
git repo *is* the deploy.

The shift from the original LangGraph plan: there is **no separate orchestration
service, no n8n, no FastAPI glue**. The gateway is the front door, cron is the
scheduler, delegation is the multi-agent coordination, and profiles/kanban are the
multi-tenancy.

## 2. Static picture — three repos, one runtime

```
┌─ SOURCE OF TRUTH (git) ──────────────────────────────────────┐
│                                                              │
│  hermes-agent/            full-throttle-platform/   mrfence-site/ (+ clones)
│  (the engine, OSS)        (skills, scripts,         (client site, per client)
│                            cron specs, onboarding)   deploys → Vercel
└──────────────────────────────────────────────────────────────┘
              │ install                │ install skills           │ agent commits into
              ▼                        ▼                          ▼
┌─ RUNTIME (DigitalOcean box) ──────────────────────────────────┐
│  Hermes installed once.                                       │
│  One PROFILE per client:  ~/.hermes/profiles/mrfence/         │
│     ├── .env        (client's own API keys — Claude, Twilio…) │
│     ├── config.yaml (model, toolsets, terminal.cwd → site)    │
│     ├── skills/     (copied from full-throttle-platform)      │
│     ├── memory/     (MEMORY.md, USER.md — agent-curated)      │
│     └── state.db    (sessions, FTS5 search)                   │
└──────────────────────────────────────────────────────────────┘
```

The platform repo is the **template/source**; a profile is a **running instance**.
Skills flow platform → profile (install), never into the client site.

## 3. Runtime topology — what processes are alive

Per client profile, one **gateway process** is the always-on front door:

```
        Owner's phone                     Internet APIs
       (SMS / email)                  (SEMrush, Buffer, GBP…)
            │  ▲                              ▲  │
            ▼  │                              │  ▼
   ┌────────────────────── Hermes Gateway (profile: mrfence) ──────────────┐
   │  gateway/run.py — routes inbound msgs, runs the cron scheduler tick,   │
   │  enforces the approval guard, delivers replies                         │
   │                              │                                         │
   │                              ▼                                         │
   │                  AIAgent (Supervisor)  ── working dir = mrfence-site/  │
   │                  loads: skills + memory + AGENTS.md/CLAUDE.md          │
   └───────────────────────────────────────────────────────────────────────┘
```

Two triggers wake the same agent core: an **inbound message** (owner) or a **cron
tick** (autonomous).

## 4. Agent hierarchy (delegation)

The Supervisor spawns specialists with `delegate_task`; they run concurrently in
isolated contexts:

```
Supervisor (orchestrator role)
   └─ delegate_task(tasks=[
        Website worker  (leaf) → terminal/file: uptime, on-page edits
        SEO worker      (leaf) → seo-blog-publisher skill, rank-tracker skill
        Social worker   (leaf) → social-scheduler skill (Buffer/Meta)
      ])
   ◄── each returns a summary; Supervisor compiles the weekly report
```

A failed worker returns an error summary without killing siblings (error isolation).
Concurrency is capped by `delegation.max_concurrent_children`.

## 5. Data flows

### A) Owner texts a change (human override)
```
Owner SMS "change homepage headline to X"
  → Twilio → gateway SMS adapter → Supervisor agent
  → reads/edits component via file/patch tool (obeys design-system rules)
  → terminal: git commit ──► APPROVAL GUARD: SMS "approve push? /approve /deny"
  → on /approve → git push → Vercel rebuild (~60s) → live
  → gateway replies "Done — live at <url>"
```

### B) Autonomous daily blog
```
cron tick ("every day 7am") fires the SEO job
  → loads seo-blog-publisher skill, working dir = mrfence-site/
  → agent writes article → publish_post.py writes src/content/blog/<slug>.md
  → git commit ──► Vercel rebuild → /blog/<slug> live
  → (cron runs with skip_memory=True, 3-min hard interrupt cap)
```

### C) "Why is our ranking dropping?" (diagnostic)
```
Owner SMS question → Supervisor
  → rank-tracker skill pulls today's rankings (SEMrush/DataForSEO)
  → compares against history in memory / state.db / Supabase
  → reasons over the delta, replies in plain English with real numbers
```

### D) Client onboarding (intake → live in <10 min)
```
Intake form submitted
(business name, location, services, keywords, social handles, contact info)
        │
        ▼
Webhook → gateway api_server  (or: operator runs the onboarding script)
        │
        ▼
┌─ onboarding script (full-throttle-platform) ─────────────────────────┐
│ 1. git clone site template  → <client>-site repo                     │
│    inject business details: name, phone, locations.json, content     │
│ 2. hermes profile create <client>  → ~/.hermes/profiles/<client>/    │
│ 3. write profile config.yaml  (terminal.cwd → client repo, model,    │
│    toolsets)                                                          │
│ 4. write profile .env  (client's API keys: Claude, Twilio, SEMrush)  │
│ 5. install platform skills  → profile skills/                        │
│ 6. seed memory/ + profile AGENTS.md with business context            │
│ 7. provision Twilio number  → route to this profile's gateway        │
│ 8. connect social accounts via OAuth                                  │
│ 9. pull SEO baseline (keywords, competitors, initial rankings)       │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
Deploy client site → Vercel   +   start gateway for profile
        │
        ▼
Supervisor sends welcome SMS  ──►  client is LIVE and autonomous
```

The new site repo is generic (template-derived); the client-specific data lands in the
**profile** (config, keys, memory) and in the site's content/data files — never by
coupling the site to the platform.

## 6. Where data lives (and why)

| Data | Lives in | Why |
|------|----------|-----|
| Site content & history | client git repo (`<client>-site`) | git *is* the CMS + audit log; commit = deploy |
| Conversation sessions | `state.db` (per profile, SQLite + FTS5) | cross-session recall, searchable |
| Agent's model of the client | `memory/` (MEMORY.md, USER.md) | persists "who the client is" across sessions |
| Secrets (API keys, tokens) | profile `.env` (gitignored) | client owns their keys; never in version control |
| Structured cross-client data | Supabase (optional) | rankings over time, dashboards — relational queries |

Deliberate split: **git holds content, Hermes holds conversation/memory, Supabase
(optional) holds structured analytics.** Git + Hermes memory cover the pilot; Supabase
is added when cross-client reporting is needed.

## 7. Scaling path (no rebuild)

```
Pilot → few clients:   one PROFILE (+ gateway) per client. Simple, hard isolation.
                                  │ grows past ~20–30
                                  ▼
Many clients:          KANBAN dispatcher + worker fleet.
                       Board = hard boundary, Tenant = per-client namespace.
                       One fleet serves all clients; dispatcher claims & spawns workers.
```

This is the "containerise workers + job queue beyond 50 clients" line from
`agents (2).md` — Hermes ships it, so it's a config migration, not a re-architecture.

## 8. Component → Hermes mechanism map

| Plan component | Hermes mechanism |
|----------------|------------------|
| Supervisor + sub-agents | `delegate_task` (orchestrator + leaf roles) |
| Orchestration (was LangGraph) | the agent loop + delegation |
| Scheduler (was n8n) | built-in cron (`cron/scheduler.py`, `cronjob` tool) |
| Webhooks (was FastAPI) | gateway `api_server` / `webhook` adapter |
| Client comms | gateway SMS + email adapters |
| Site deploy | `terminal` git + file tools → Vercel rebuild |
| Per-client isolation | profiles (pilot) → kanban tenants (scale) |
| Client-owned API keys | per-profile `.env` |
| Live demo view | `hermes dashboard` + `hermes logs --follow` |
| Runaway protection | cron 3-min interrupt + `iteration_budget` |
```
