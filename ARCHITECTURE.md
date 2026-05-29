# Full Throttle Marketing — Architecture

How the platform works, what runs where, and how data flows. Built on
[Hermes Agent](https://github.com/NousResearch/hermes-agent). Every component maps to a real
Hermes mechanism (gateway, cron, delegation, profiles, skills, tools). The "why" behind these
decisions lives in `MARKET_RESEARCH.md` — key findings are cited inline as **[MR §n]**.

## 1. The core idea

Hermes is the **engine**. We don't build an orchestration graph — we run Hermes agent
processes. Each gets a working surface (a client's site, via whatever publishing path that
client supports), a set of skills, a schedule (cron), and a way to be reached (the gateway).
The agent uses **tools** (terminal/git, file edit, web, HTTP) and **delegation** to fan out
into specialist sub-agents.

The shift from the original LangGraph plan: there is **no separate orchestration service, no
n8n, no FastAPI glue**. The gateway is the front door, cron is the scheduler, delegation is the
multi-agent coordination, profiles/kanban are the multi-tenancy.

**The bigger strategic shift (from research):** the platform is **augment-first**, not
website-builder-first. Most fencing clients already have a site, and rebuilding risks 44–50%
organic traffic loss **[MR §11]**. And the biggest revenue levers — speed-to-lead, reviews/GBP
— aren't the website at all **[MR §1, §5]**. So we default to *improving what the client has*
and winning on lead response + reputation, with a fresh site only as a fallback.

**Positioning & operating principle (constraint-first).** We are NOT competing on "most
autonomous AI," "largest agent swarm," or generalized intelligence. We compete on **fastest
lead response, operational reliability, easiest onboarding, measurable ROI, and preservation
of existing business infrastructure.** Agents are therefore treated as **bounded workflow
executors**, not autonomous decision-makers: deterministic actions, structured outputs,
explicit approvals, and auditable execution over open-ended autonomy. The platform succeeds
when it reliably increases booked jobs, review volume, local trust, and owner responsiveness
with minimal workflow disruption. This stance drives the governance layer (§12) and the
narrowed agent topology (§6).

## 2. Two site modes

Onboarding captures a `site_type` and picks a mode. Most clients are **Augment**.

| Mode | When | What we do |
|------|------|-----------|
| **Augment** (default) | Client has a working site (WordPress/Wix/ColdFusion/custom) | Publish into it via a **publishing adapter** (below); manage GBP, reviews, ads, social externally; never migrate. Preserves SEO equity. **[MR §11]** |
| **Greenfield** (fallback) | Client has no site, or a broken/unsalvageable one | Clone + own an Astro site we commit to (the original flow). Lowest priority. |

## 3. Publishing-adapter abstraction

Replaces the old hardcoded "git commit to Astro" assumption. A skill writes content; an
**adapter** decides how it lands on the client's surface. All adapters live in the unified
**`content-publisher`** skill; the adapter is chosen per client and recorded in their profile.

| Adapter | Target | Priority / status |
|---------|--------|-------------------|
| `wordpress-rest` | WordPress REST API (Application Passwords) | **v2 primary** — most common contractor CMS. ✅ built |
| `proxy-subdir` | Astro blog we host, served at `client.com/blog` via **Cloudflare Workers reverse proxy** | **v2 primary** — SEO-equity wedge; subdirectory beats subdomain, no migration **[MR §11]**. ✅ built (Worker is one-time infra) |
| `astro-git` | Greenfield Astro repo | ✅ built — the *greenfield fallback*, for site-less/broken-site clients. |
| `manual` | Outbox file (md + HTML) | ✅ built — fallback when no target is wired. |
| `wix-data` | Wix Data / CMS API | Deferred until demand. |
| `webhook` | Any system accepting a webhook | Deferred until demand. |

**v2 priority (reconciled with REVISION.md):** the two adapters that serve the augment-first
default — `wordpress-rest` and `proxy-subdir` — are built (in `content-publisher`). `astro-git`
is the *greenfield fallback*; `wix-data` and `webhook` are deferred until a client needs them.

## 4. Static picture — three repos, one runtime

```
┌─ SOURCE OF TRUTH (git) ──────────────────────────────────────┐
│  hermes-agent/            full-throttle-platform/   <client>-site/ (greenfield only)
│  (the engine, OSS)        (skills, adapters,        (Astro site, when we own it)
│                            scripts, cron specs)      deploys → Vercel
└──────────────────────────────────────────────────────────────┘
              │ install                │ install skills           │ (greenfield) commit
              ▼                        ▼                          ▼
┌─ RUNTIME (DigitalOcean box) ──────────────────────────────────┐
│  Hermes installed once. One PROFILE per client:               │
│  ~/.hermes/profiles/<client>/                                 │
│     ├── .env        (client's keys — Claude, Twilio, CMS, …)  │
│     ├── config.yaml (model, toolsets, site_type, adapter)     │
│     ├── skills/     (copied from full-throttle-platform)      │
│     ├── memories/   (MEMORY.md, USER.md — agent-curated)      │
│     └── state.db    (sessions, FTS5 search)                   │
└──────────────────────────────────────────────────────────────┘
                          │ augment mode publishes via adapter into:
                          ▼
        Client's existing site (WordPress / Wix / proxy-subdir / …)
        + external surfaces: GBP, review platform, ad accounts, social
```

The platform repo is the **template/source**; a profile is a **running instance**.

## 5. Runtime topology

Per client profile, one **gateway process** is the always-on front door:

```
   Owner's phone        Inbound leads           Marketing APIs
   (SMS / email)      (form/call/LSA)      (GBP, SEMrush, CMS, Buffer…)
        │ ▲                │                        ▲ │
        ▼ │                ▼                        │ ▼
   ┌──────────────── Hermes Gateway (profile: <client>) ───────────────┐
   │  gateway/run.py — routes msgs + inbound leads, runs cron ticks,    │
   │  enforces the approval guard, delivers replies                     │
   │                              │                                     │
   │                              ▼                                     │
   │                  AIAgent (Supervisor)                              │
   │                  loads: skills + memory + AGENTS.md/CLAUDE.md      │
   └────────────────────────────────────────────────────────────────────┘
```

Three triggers wake the agent core: an **inbound message** (owner), an **inbound lead**
(speed-to-lead), or a **cron tick** (autonomous cadence).

## 6. Agent roster (leverage-ordered)

The Supervisor spawns specialists with `delegate_task`; they run concurrently in isolated
contexts. Roster is ordered by revenue leverage from the research, not by "website first."

- **Lead-Response agent** (top) — speed-to-lead. Watches inbound leads (form/call/LSA), replies
  in seconds, qualifies, books. The 60s lever: +391% conversion, first responder wins **[MR §1, §4]**.
  Hermes: gateway adapters + webhook + cron watcher.
- **Reviews/Reputation agent** (high) — post-job review-request automation (+80% response) +
  AI-drafted responses. Works for ALL clients regardless of site. Velocity is a ranking factor
  **[MR §5, §8]**. `[MCP/Skill]` GBP/Podium/Birdeye.
- **GBP agent** (high) — Business Profile optimization, posts, Q&A, categories — the #1 local
  lever **[MR §5]**. `[MCP/Skill]`.
- **Social Media agent** (basics — **built, parked**) — schedule **real** before/after photos +
  recycled reviews to GBP + Facebook + Nextdoor at 2–3×/week. Trust/proof support, **not** a
  lead driver. Guardrail: assist/schedule real job content, never fully auto-generate generic
  posts (authenticity penalty: trust 3.0 vs 4.5) **[MR §12]**. Shares source material with the
  Reviews/GBP agent. `[MCP/Skill]`. *v2 note: the `social-scheduler` skill exists; v2 defers
  multi-platform social automation, so it runs as "basics" only until retention is proven.*
- **SEO/Content agent** — publishes via the chosen **adapter**; E-E-A-T guardrails (inject real
  local data); 5–8 genuinely-unique markets, not templated mass pages (>80% doorway de-rank)
  **[MR §6, §7]**.
- **Ads agent** (med) — LSA + Google + Meta budget pacing + lead-quality feedback **[MR §9]**. `[MCP/Skill]`.
- **Website agent** — uptime + on-page edits via the platform-appropriate adapter.
- **Supervisor** — orchestration, weekly report, owner comms.

```
Supervisor (orchestrator role)
   └─ delegate_task(tasks=[ Lead-Response, Reviews/GBP, Social, SEO/Content, Ads, Website ])
   ◄── each returns a summary; Supervisor compiles the weekly report
```

A failed worker returns an error summary without killing siblings (error isolation).
Concurrency capped by `delegation.max_concurrent_children`.

**Narrowed production topology (v2).** The roster above is the full leverage map; the
*production* topology for v2 is narrowed to four workers + Supervisor, with the rest deferred:

| Agent | Scope in v2 | Allowed actions (tool-permission scope) |
|-------|-------------|------------------------------------------|
| **Supervisor** | route, enforce policy, manage approvals, compile reports — **never directly mutates external systems** | delegation, clarify, reporting |
| **Lead-Response** | inbound forms / missed-call text-back / LSA / qualification / booking | SMS+email, CRM create/update — **no website or CRM-schema edits** |
| **Reputation** | review requests + AI-assisted replies + negative-review escalation | review replies/requests — **negative replies require approval** |
| **GBP** | profile posts, Q&A, category/service audits | GBP posting only — **no autonomous business-detail edits** |
| **Content** | localized blog/news drafts via the adapter | CMS publish to blog/news + approved landing pages + metadata — **cannot redesign pages, alter nav, or overwrite the homepage** |

Deferred (until retention + operational stability are proven): autonomous **ad management**,
**multi-platform social automation**, advanced website **rebuilding**, fully autonomous
outbound, recursive agent swarms. **No worker gets unrestricted `terminal`/admin in
production** — see the tool-permission scopes in §12.

## 7. Data flows

### A) Inbound lead → instant response (the top lever)
```
Lead arrives (web form / missed call / LSA message)
  → webhook/adapter → gateway → Lead-Response agent (within seconds)
  → SMS/email reply, qualify, offer booking
  → sync lead into client's CRM/FSM (ServiceTitan/Jobber/HCP)
  → notify owner
```

### B) Owner texts a change (human override)
```
Owner SMS "update the homepage headline to X"
  → Twilio → gateway → Supervisor → SEO/Website agent
  → publishing adapter applies the change (WordPress API / Astro commit / proxy)
  ──► APPROVAL GUARD for risky/destructive actions: SMS "/approve | /deny"
  → reply "Done — live at <url>"
```

### C) Autonomous content + reviews + social (cron cadence)
```
cron tick → Supervisor fans out:
  • SEO/Content: draft post w/ real local data → adapter publishes → live
  • Reviews: send post-job review asks; draft responses to new reviews (→ approval)
  • Social: schedule real before/after photos + reviews → GBP + Facebook + Nextdoor
  (cron runs skip_memory=True, 3-min hard interrupt cap)
```

### D) Diagnostic Q&A
```
Owner SMS "why is our ranking dropping?"
  → Supervisor → rank-tracker skill pulls current rankings (SEMrush/DataForSEO)
  → compares against history in memory / state.db / Supabase
  → plain-English answer with real numbers
```

### E) Client onboarding (mode-aware, intake → live)
```
Intake form (business details, EXISTING SITE platform/URL, keywords, socials, contact)
        │
        ▼
Webhook → gateway api_server  (or operator runs the onboarding script)
        │
        ▼
┌─ onboarding script (full-throttle-platform) ─────────────────────────┐
│ 1. Determine site_type → choose MODE (augment | greenfield)          │
│    └ augment: pick publishing adapter (wordpress-rest / wix-data /    │
│      proxy-subdir / webhook)                                          │
│    └ greenfield: git clone Astro template → <client>-site, inject     │
│      business details                                                 │
│ 2. hermes profile create <client>  → ~/.hermes/profiles/<client>/    │
│ 3. write config.yaml  (model, terminal.cwd, site_type, adapter)      │
│ 4. write .env  (client keys: Claude, Twilio, CMS creds, SEMrush…)    │
│ 5. install platform skills → profile skills/                         │
│ 6. seed memories/ + profile AGENTS.md with business context          │
│ 7. connect lead sources, GBP, review platform, CRM/FSM               │
│ 8. provision Twilio number → route to this profile's gateway         │
│    (augment: configure adapter creds / stand up proxy)               │
│    (greenfield: deploy site → Vercel)                                │
└──────────────────────────────────────────────────────────────────────┘
        │
        ▼
Start gateway for profile → Supervisor sends welcome SMS → LIVE
```

Greenfield builds a generic template-derived site; client-specific data lands in the
**profile** (config/keys/memory), never by coupling a site to the platform.

## 8. CRM/FSM & tool coexistence

The platform **coexists, does not replace** the operational layer **[MR §13]**:

- **CRM/FSM** (ServiceTitan / Jobber / Housecall Pro) owns jobs + customer data. We sync leads
  *in* (from Lead-Response) and read job-completion events *out* (to fire review requests).
- **Reputation/messaging** (Podium / Birdeye) — integrate where present rather than duplicating.
- We **own** the marketing layer: content, SEO, GBP, ads, reviews orchestration, social.

## 9. Where data lives

| Data | Lives in | Why |
|------|----------|-----|
| Client site content | the client's own platform (WordPress/Wix/Astro/proxy) | augment-first; SEO equity stays on their domain |
| Conversation sessions | `state.db` (per profile, SQLite + FTS5) | cross-session recall, searchable |
| Agent's model of the client | `memories/` (MEMORY.md, USER.md) | persists "who the client is" |
| Secrets (API keys, CMS creds, tokens) | profile `.env` (gitignored) | client owns their keys; never in VCS |
| Rankings / leads / structured analytics | Supabase (optional) + the CRM/FSM | relational queries, reporting |

## 10. Scaling path (no rebuild)

```
Pilot → few clients:   one PROFILE (+ gateway) per client. Hard isolation.
                                  │ grows past ~20–30
                                  ▼
Many clients:          KANBAN dispatcher + worker fleet.
                       Board = hard boundary, Tenant = per-client namespace.
```

The "containerise workers + job queue beyond 50 clients" future scope — Hermes ships it, so
it's a config migration, not a re-architecture.

## 11. Component → Hermes mechanism map

| Plan component | Hermes mechanism |
|----------------|------------------|
| Supervisor + sub-agents | `delegate_task` (orchestrator + leaf roles) |
| Orchestration (was LangGraph) | the agent loop + delegation |
| Scheduler (was n8n) | built-in cron (`cron/scheduler.py`, `cronjob` tool) |
| Inbound leads / webhooks (was FastAPI) | gateway `api_server` / `webhook` adapter |
| Client comms | gateway SMS + email adapters |
| Content publishing | publishing adapters (astro-git / wordpress-rest / wix-data / proxy-subdir / webhook) |
| Per-client isolation | profiles (pilot) → kanban tenants (scale) |
| Client-owned API keys | per-profile `.env` |
| Live demo view | `hermes dashboard` + `hermes logs --follow` |
| Runaway protection | cron 3-min interrupt + `iteration_budget` |

## 12. Operational governance layer

A first-class concern in v2 — the mechanism that makes constraint-first real. Partly built
(dedup/idempotency already in our skills), partly net-new (execution plans, audit log,
rollback). Tracked as a backlog epic with honest effort tags.

- **Execution plans before mutations.** Before changing an external system, the agent emits a
  structured plan that is logged, validated, and optionally approved before execution:
  ```json
  {"intent":"update_blog_post","target":"/blog/summer-fence-maintenance",
   "actions":["update title","replace CTA","publish metadata"]}
  ```
- **Tool-permission scopes.** Each worker is restricted to the tools its job needs (see the §6
  table). **No worker receives unrestricted `terminal`/admin access in production.** In Hermes
  terms: per-profile/per-agent toolset enablement + delegation leaf roles.
- **Idempotency.** Every external action carries a unique execution id + dedup check + retry-safe
  semantics — prevents duplicate SMS, duplicate review requests, repeated CRM writes. *(Already
  practiced: `seen.json` / `posted.json` / `used.json` and slug-collision guards in the built
  skills.)*
- **Audit logging.** Every mutation records timestamp, agent, tool, input/output payloads,
  approval state, and a rollback reference. Append-only.
- **Rollback.** Snapshot prior state before a CMS mutation; retain a version; allow one-click
  revert — covers accidental overwrites, malformed content, hallucinated edits. *Adapter-specific:*
  for `astro-git`, git revert IS the rollback; for `wordpress-rest`, snapshot the post first.

This layer is what lets a constrained Content/Website agent safely touch a client's live site —
it backs the approval guard already shown in data flow §7-B.

## 13. Observability

Operational visibility is mandatory in v2 — agent systems without it become unmaintainable.
Required surfaces (built on `hermes dashboard` + `hermes logs` + the audit log above):

- execution timeline · approval queue · message replay
- lead tracking · error monitoring · tool-execution logs · cost tracking

## 14. Reconciliation note

This document is the canonical architecture. `REVISION.md` was the v2 proposal that has now
been folded in here (positioning §1, narrowed topology §6, governance §12, observability §13,
adapter priority §3). Where v2 and the prior roster differed, v2 wins on **sequencing**
(next builds = lead-response + `wordpress-rest`/`proxy-subdir` adapters + governance), while the
already-built skills are retained: `astro-git` as the greenfield fallback, `social-scheduler`
as parked "basics."
