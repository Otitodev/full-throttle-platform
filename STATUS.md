# Full Throttle Platform — State of Play

*Read-on-commute brief. Last updated: 2026-06-01.*

A grounded account of what's actually live, the architecture as built (not as
sketched), the tradeoffs we made along the way, the integrations in play, and
what to do next. Companion to `ARCHITECTURE.md` (the static architecture) and
`REVISION.md` (the v2 design rationale). Where those describe the system in the
abstract, this one tells you exactly which parts are running, which are still
on paper, and what's broken or flaky.

---

## 1. Snapshot

We have an end-to-end working pilot for **Mr. Fence of Florida** plus a working
**personal Telegram agent** for the operator. On the droplet at
`138.197.7.87`, three gateways run in parallel: `mrfence` (client pilot),
`otito_socials` (personal), `smoke` (deployment validation). All three run on
the same shared Hermes install, isolated via per-profile config and dedicated
systemd instances. A lead can now travel from a customer typing on
mrfenceflorida.com → through Vercel → through Caddy → through the agent →
into Twilio → onto a phone. The same agent receives the customer's SMS reply
and continues the conversation.

What we proved today:

- Anthropic `claude-sonnet-4-6` as the primary model with OpenAI `o4-mini`
  fallback works at the gateway level under real load.
- The `lead-response` skill runs intake, first-touch SMS, CRM sync, and
  owner notification in ~30s, ~10 LLM calls, ~$0.02 per lead.
- Customer SMS replies route back into the same agent session via Hermes'
  `sms` platform (inbound Twilio webhook → signature validation → conversation
  resume).
- The website's lead form (Vercel Edge function → HMAC-signed POST → agent)
  works without leaking the secret to the browser.
- A second profile (`otito_socials`) sharing the same Hermes binary serves a
  Telegram bot for the operator — confirming the multi-tenant pattern.

What we have *not* proven, but is built:

- Multi-client scale (only one paying-shape client active).
- The dashboards (admin + per-client) — code exists, full pipeline not pressure
  tested with real traffic yet.
- Long-horizon agent behaviours (multi-turn customer qualification past the
  first reply, booking, escalation).
- Anything social/content (`content-publisher`, `review-automation`,
  `social-scheduler` skills exist but no live publishing happens for Mr. Fence
  yet).

---

## 2. What's live right now

| Component | State | Notes |
|---|---|---|
| Droplet `138.197.7.87` (DO) | live | Debian, hardened systemd, Caddy auto-TLS |
| Caddy reverse proxy | live | wildcard `*.hooks.138.197.7.87.nip.io`; per-client fragments under `/etc/full-throttle/caddy.d/` |
| Hermes install at `~hermes/.hermes/hermes-agent/` | live | commit `827ce602d` |
| `hermes-gateway@mrfence.service` | live | webhook + sms platforms |
| `hermes-gateway@otito_socials.service` | live | telegram platform, `hermes-cli` toolset |
| `hermes-gateway@smoke.service` | live | leftover from infra validation; harmless |
| Anthropic API integration | live | key in each profile's `.env`, account validated |
| OpenAI fallback (custom provider) | live | for `o4-mini` if Anthropic 5xxs |
| Twilio (Full account `AC786e7…`) | live | FROM `+12183074659`, US-issued |
| `lead-response` skill v2 | live | tightened SMS template (≤160 char GSM-7), em-dash normalisation, 20-char `about` slice |
| `intake.py` / `sync_lead.py` | live | JSON-to-stdout pattern, governance audit appended on every mutation |
| SMS inbound reply path | live | Caddy `/webhooks/twilio*` → 127.0.0.1:8080; signature validated; `GATEWAY_ALLOW_ALL_USERS=true` (signature is the gate) |
| Mr Fence website Astro build | live | 60 pages built clean, deployed on Vercel |
| Site `<QuoteForm>` + `/api/lead` Edge fn | deployed | HMAC-signs lead payload; waiting on `WEBHOOK_LEAD_SECRET` to be set in Vercel env to function |
| Owner dashboard (admin) | code complete | aggregator + SPA on droplet at `admin.<domain>`; not pressure tested |
| Per-client dashboard | code complete | embedded at `<slug>.hooks.<domain>/dash/`, token-gated |
| Personal Telegram agent | live | DM-reachable from operator's phone |

| Component | Not live yet |
|---|---|
| GBP integration (`gbp-agent` skill) | scaffolded, not connected to a Google Business Profile |
| `review-automation` skill | scaffolded, no live review feed yet |
| `social-scheduler` skill | scaffolded, no live social account connected |
| `content-publisher` skill | scaffolded, no WordPress/CMS adapter actively publishing |
| Mr Fence greenfield Astro deployed alongside old site | code exists in `mrfence-site-ai`; Vercel is rebuilding right now post-env-var |
| Telegram for client agents | infra ready; no client has activated their own bot yet |

---

## 3. The architecture in one page

```
                   PUBLIC                              DROPLET (single VM)
                                                      ─────────────────────
                                                      │  Caddy (:443)
   browser ── HTTPS ────▶ mrfenceflorida.com          │   ├─ <slug>.hooks.<domain>
                                 │                    │   │    ├─ /webhooks/lead    → :<webhook port>
                                 ▼                    │   │    ├─ /webhooks/twilio  → 8080
                          Vercel Edge                 │   │    ├─ /api/client/*     → 9201 (aggregator)
                          /api/lead                   │   │    └─ /dash/*           → static SPA
                          ─ HMAC sign ─               │   ├─ admin.<domain>         → 9201 (aggregator)
                                 │                    │   │
                       ──── HTTPS POST ──────────────▶│   ▼ (per profile)
                                                      │  hermes-gateway@<slug>  (systemd)
   Twilio ──── POST /webhooks/twilio ────────────────▶│   ├─ webhook platform   :<port>
                                                      │   ├─ sms platform       :8080
                                                      │   ├─ telegram platform  (long-poll out)
                                                      │   └─ agent core
                                                      │       ├─ Anthropic Sonnet (primary)
                                                      │       └─ OpenAI o4-mini (fallback)
                                                      │           │
                                                      │           ▼
                                                      │       skills/<name>/scripts/*.py
                                                      │           │
                                                      │           ▼
   customer phone ◀──── SMS  ── Twilio (outbound) ────│       audit.jsonl + sessions.json
                                                      │           │
                                                      │           ▼
                                                      │       FastAPI aggregator (:9201)
                                                      │           ▲
                                                      │           │
   operator browser ◀──── HTTPS ──── dashboards ──────│           │
                                                      │           │
                                                      │       basic-auth (admin) or
                                                      │       per-client bearer token
                                                      └────────────────────────────
```

Three properties to internalize:

1. **One Hermes process per profile.** Profiles are total isolation
   boundaries: separate `.env`, sessions, audit log, skill copies, dashboard
   token. Adding a client is `onboard_client.py` + `promote_client.sh`.
2. **Profile-local skills.** When `onboard_client.py` runs, it *copies* the
   platform repo's skills into each profile. Edits to the repo's `skills/`
   don't reach a live profile until `sync_skill_to_profile.sh <slug>
   <skill>` is run. Decouples client behaviour from platform commits but
   adds a manual sync step.
3. **One reverse-proxy fragment per client.** Caddy auto-issues per-subdomain
   certs from the wildcard DNS; the per-client fragment is the only
   client-specific Caddy config. SMS reply, lead webhook, dashboard, and
   client API live under the same subdomain via `handle` blocks.

---

## 4. Integrations

External systems the platform talks to:

| Integration | Purpose | Where credentials live | Notes |
|---|---|---|---|
| **Anthropic** (Sonnet 4.6 + Haiku 4.5) | Primary LLM. Tool calling, reasoning. | `ANTHROPIC_API_KEY` in each profile's `.env` | Hermes' `anthropic` provider plugin. Passes model strings through verbatim — `claude-sonnet-4-6` is a real alias the API accepts. |
| **OpenAI** (o4-mini) | Fallback LLM when Anthropic is rate-limited or 5xxing. | `OPENAI_API_KEY` in `.env` | Wired as Hermes `provider: custom, base_url: https://api.openai.com/v1`. Reasoning models require OpenAI org verification (~15 min after switch). |
| **Twilio** (Full account, US LongCode `+12183074659`) | Outbound first-touch SMS + inbound reply routing. | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` in `.env` | Was a Trial account, swapped to Full to remove the 40-char prefix + multi-segment cap + verified-Caller-ID restriction (Trial errors 30044/21608). |
| **Telegram (Bot API)** | Operator's personal agent UI. | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` in `.env` | Long-poll outbound — no inbound webhook URL, no Caddy fragment needed. Cross-profile bot lock at `~/.local/state/hermes/`. |
| **Vercel (Edge runtime)** | Hosts the Mr Fence site + serverless function for the lead form. | `WEBHOOK_LEAD_SECRET` and (optional) `LEAD_WEBHOOK_URL` as Vercel project env vars. | Form posts to `/api/lead` (Edge fn). HMAC happens on Vercel, not in the browser. |
| **Let's Encrypt** (via Caddy) | TLS for every `<slug>.hooks.<domain>` subdomain. | n/a — Caddy auto-issues via HTTP-01. | One wildcard DNS A record covers all clients. |
| **GitHub** (`Otitodev/full-throttle-platform`, `Otitodev/mrfence-site-ai`, `NousResearch/hermes-agent`) | Source of truth + auto-deploy trigger for Vercel. | HTTPS PATs for the platform repo, HTTPS for the site. | Pulled on droplet during deploys. |

External systems on the roadmap but not connected:

- **Google Business Profile (GBP)** for the `gbp-agent` skill.
- **Jobber / Housecall Pro / ServiceTitan** for `sync_lead.py` real CRM
  adapter (currently uses `manual` adapter — leads land in
  `profiles/<slug>/leads.jsonl` only).
- **Google review feed / Yelp / Trustpilot** for `review-automation`.
- **WordPress REST or `proxy-subdir`** for `content-publisher`.

---

## 5. Tradeoffs we explicitly made

These are the load-bearing decisions worth re-reading before changing.

### 5.1 Augment, don't replace

Hermes-driven agents wire into a client's *existing* website and *existing*
CRM via adapters. We never own the customer's homepage. Conversion lift is the
deliverable, not a re-platform. Tradeoff: every new CRM / CMS we onboard
needs an adapter (`skills/<name>/scripts/adapters/<provider>.py`); the
`manual` fallback lets us ship before the adapter exists.

### 5.2 Profile-as-tenant

One Hermes profile = one client. Total isolation of sessions, secrets,
audit logs, dashboard tokens. Tradeoff: each new profile spins up another
Python process (currently ~150 MB RSS); we run out of RAM long before we run
out of CPU. Mitigation: kanban dispatcher fleet (§10 in ARCHITECTURE.md) when
we cross ~30 clients.

### 5.3 Single droplet, vertical scale first

We deliberately did *not* shard across multiple machines, multiple Hermes
binaries, or containerize per profile. One droplet, one Hermes, N profiles.
Tradeoff: a Hermes upgrade is a global event for all clients. Mitigation:
keep `~/.hermes/hermes-agent/` under git and use `git checkout <tag>` for
rollbacks.

### 5.4 Profile-local skill copies

Skills get *copied* into the profile during onboarding rather than
symlinked or imported from the platform repo at runtime. Tradeoff: behavior
drift between repo `skills/` and live `profiles/<slug>/skills/` until you
run `sync_skill_to_profile.sh`. Upside: a client's behaviour is frozen and
auditable on disk; an upstream platform commit can't change a live agent
without an explicit sync action.

### 5.5 Anthropic primary, OpenAI fallback

Anthropic's tool-calling quality on Sonnet 4.6 is materially better than
OpenAI mid-tier for the lead-response use case. We pay slightly more per
token and accept Anthropic's lower context window. Fallback to `o4-mini`
covers Anthropic 5xx / rate-limit windows. Tradeoff: two API keys to
maintain per profile.

### 5.6 Twilio LongCode (not Toll-Free, not Short Code)

US LongCode `+12183074659` is the simplest path to send SMS without A2P 10DLC
campaign registration. Tradeoff: in some countries (Nigeria observed) the
LongCode is rewritten to the alphanumeric Sender ID `hcloud` and delivery
is flakier. Real US-Mr-Fence-customer traffic won't hit this. For brand-
preserved Nigeria delivery, a Twilio Messaging Service + registered
Alphanumeric Sender ID would be needed (~$0.005/msg).

### 5.7 Webhook signature as auth, not allowlist

`mrfence`'s webhook route accepts HMAC-signed leads from anywhere — we don't
allowlist the Vercel egress IPs. Tradeoff: simpler ops, the secret is the
gate. Same approach for the Twilio inbound: signature verification, no IP
allowlist, `GATEWAY_ALLOW_ALL_USERS=true`. Compromised secret = compromised
inbound; mitigate by rotating via `nano` on the droplet.

### 5.8 Static-first Astro with one serverless escape hatch

The Mr Fence site is `output: 'static'` Astro — every marketing page is
pre-rendered HTML, no SSR cost on Vercel. The *only* dynamic piece is
`/api/lead` as a Vercel-native Edge function in `api/lead.ts`. We did NOT
adopt `@astrojs/vercel` adapter / `output: 'server'`/`'hybrid'` (which would
have required adding `export const prerender = true` to ~15 pages). Tradeoff:
the API endpoint is invisible to Astro (no shared types, no `import.meta.env`
in the form context); upside is build stays fast and pages stay cacheable.

### 5.9 Vercel Edge runtime (not Node)

`/api/lead` uses `export const config = { runtime: 'edge' }`. Tradeoff:
small standard library (Web Crypto only — no `node:crypto`); upside is faster
cold starts and lower cost. We use `crypto.subtle.importKey` + `sign` for
HMAC-SHA256 — works in both Edge and Node, so swap is trivial if we need
Node APIs later.

### 5.10 First-touch SMS as a *template*, not free LLM text

`intake.py`'s `FIRST_TOUCH` is a hand-tuned ≤160-char GSM-7 string with
`{name} {business} {about}` substitutions and a 20-char slice of the
customer's project description. We do NOT have the LLM compose the first
SMS. Tradeoff: less personalization; upside is deterministic deliverability
(no surprise emoji forcing UCS-2) and predictable carrier-pass behaviour.
Owner-notification SMS *is* LLM-composed and has hit Twilio's segment caps;
worth tightening with a similar template if it bites again.

---

## 6. Open seams (gaps and known issues)

These aren't bugs we'll forget; they're conscious deferrals.

1. **`send_message` reports success on Twilio "queued", not delivered.** A
   delivered audit entry can hide a silent carrier drop. Fix: wire Twilio
   status callback to a Hermes webhook and reconcile delivery into the audit
   log. Open in
   `feedback_twilio_send_message_queued_not_delivered` memory.
2. **No home channel set for SMS** — Hermes' "📬 No home channel" cosmetic
   shows up as a stray owner SMS. Set per-profile default `chat_id` to silence.
3. **Workspace cwd fallback warning.** The agent's terminal tool falls back
   from `workspace/` to `/tmp/` on every cold session. Pre-create the
   workspace dir during onboarding.
4. **No Twilio Alphanumeric Sender ID registered.** Outbound SMS to certain
   non-US destinations (Nigeria observed) shows the carrier-rewritten "hcloud"
   sender. Acceptable for pilot; register an alphanumeric sender for Nigeria
   before going wide to non-US owners.
5. **`mrfence-site-ai` Vercel env var.** `WEBHOOK_LEAD_SECRET` was being set as
   the brief was written; until the redeploy finishes, `/api/lead` returns
   500. (Loud failure by design — leads won't silently disappear.)
6. **`leftover smoke profile`** is still active on the droplet (port 9295). It
   was the deployment validator and serves no purpose now. Disable via
   `systemctl disable --now hermes-gateway@smoke; rm /etc/full-throttle/caddy.d/smoke.caddy; systemctl reload caddy`.
7. **No automated tests for the skills.** `ruff check --diff .` is the entire
   CI gate per `AGENTS.md` § CI. Skills get human-tested via real lead flows;
   a recipe-style pytest suite for `intake.py`'s fingerprint + template
   rendering would catch regressions like the em-dash 30044 incident.
8. **No formal `mrfence-site` ↔ `mrfence` agent linkage in docs.** The lead
   form's `LEAD_WEBHOOK_URL` is hardcoded in the Edge function as a default
   and overridable via Vercel env. If we ever migrate the droplet, both env
   vars on both sides change. Worth documenting in `infra/README.md`'s
   migration playbook.
9. **PowerShell → ssh → bash quote stripping.** Three distinct sessions today
   wasted time on it. The mitigation (always write a script file, commit,
   pull on droplet, run) is documented in `CLAUDE.md` but worth promoting to
   a leading "Gotchas" section in `infra/README.md`.

---

## 7. Suggested next moves

Ranked by leverage, with risk noted. Most are 30–90 minutes of work.

**Tier 1 — close the visible loop**

1. **Twilio status callback → audit reconciliation.** Adds a `delivery_status`
   field to `audit.jsonl` entries for each `send_message`. Removes the
   single biggest unknown ("did the customer actually get it?") and gives
   the dashboards a real "SMS delivered: yes/no" column. ~2h.
2. **Owner SMS template hardening.** Apply the same GSM-7 + 160-char + emoji
   stripping logic to the agent's *owner-notification* SMS path (currently
   LLM-composed). Bring everything Twilio sends under a single normalize
   helper in `skills/lead-response/scripts/_common.py`. ~1h.
3. **Pre-create `workspace/` during onboarding.** Add to `onboard_client.py`
   so the agent's terminal tool doesn't print the "fallback to /tmp" warning
   on every first call of the day. ~15 min.

**Tier 2 — make the platform sellable**

4. **Wire the real CRM adapter for Mr Fence.** Mr Fence uses [whichever
   FSM/CRM they actually use — confirm]. Drop in
   `skills/lead-response/scripts/adapters/<provider>.py`, smoke-test with one
   real lead, flip the profile config from `adapter: manual` to the new one.
5. **Activate `review-automation`.** Connect a Google Business Profile or
   Yelp feed → first business-side reputation lift. The skill scaffold is
   ready; mostly an OAuth + dashboard config job.
6. **Dashboards pressure test.** Run a real day of leads through the
   `mrfence` profile and verify the per-client dashboard renders correct
   stats, audit, and approval queue. Catch any aggregator bugs while there
   are still few enough audit lines to read by hand.

**Tier 3 — multi-client posture**

7. **Onboard client #2.** The infra is built for N. Two clients is where
   actual multi-tenant edge cases surface. Pick a contractor with a
   similar profile to Mr Fence so the same skills + adapters apply.
8. **Telegram for client agents.** Each client can have their own bot
   (owner + select staff in `TELEGRAM_ALLOWED_USERS`) so they can chat with
   their agent directly, not just see SMS. Cheap to enable; nice
   stickiness.
9. **Migration playbook.** Write a one-page runbook in `infra/README.md` for
   "we need to move the droplet". Cover: snapshot, rsync `~hermes/`, update
   DNS, repoint Vercel env, repoint Twilio `sms_url`. Catch all the
   external-pointer breakage in one place.

**Tier 4 — protect the future**

10. **Tighten CI.** Add `pytest` skeleton with: (a) `intake.py`
    fingerprint determinism, (b) first-touch template renders under 160
    chars + GSM-7, (c) HMAC sig round-trip with `/api/lead`. Three tests
    cover 80% of the regressions today's session would have caught earlier.
11. **Tear down `smoke` profile.** It served its purpose. Document the
    teardown in `infra/README.md` as the canonical way to deprovision a
    client.
12. **Documentation drift.** `ARCHITECTURE.md` §15 (Dashboards) and
    §14 (Deployment) were last touched today; `REVISION.md` is older. Audit
    `REVISION.md` for staleness next session.

---

## 8. Pointers to deeper docs

- `ARCHITECTURE.md` — full topology, agent roster, data flows, deployment
  packaging. Updated 2026-06-01.
- `REVISION.md` — v2 design decisions and why we narrowed scope.
- `CLAUDE.md` — fast index of operational gotchas (PS quoting, Twilio Trial
  traps, profile-local logs, webhook toolset widening).
- `AGENTS.md` — Python dev guide (lint, structure, audit conventions, skill
  authoring).
- `infra/README.md` — droplet runbook (install, onboard, promote, gotchas).
- `MARKET_RESEARCH.md` — the market case for the platform.

---

## 9. Appendix — today's session log

The work that put the platform in its current state, dated 2026-06-01:

- Anthropic provider + OpenAI fallback config validated on `mrfence`.
- `intake.py` SMS template tightened to ≤160 GSM-7; em-dash, smart quotes,
  ellipsis normalised after substitution; 160-char truncation guard;
  `about` slice dropped 60→20 chars.
- `platform_toolsets.webhook` widened to `[hermes-webhook, terminal,
  messaging]` so `lead-response` can run python + send SMS.
- Twilio Trial replaced with Full account (errors 30044 / 21608 / "Sent from
  your Twilio trial account - " prefix all gone).
- SMS reply path wired: Caddy `handle /webhooks/twilio*` → 127.0.0.1:8080,
  Twilio `sms_url` repointed, signature validation proven via
  `simulate_inbound_sms.sh` synthetic POST.
- `sync_skill_to_profile.sh` written — closes the platform-repo-vs-profile
  drift hole.
- Mr Fence Astro site got `<QuoteForm>` + Vercel Edge `/api/lead` with HMAC
  signing.
- `otito_socials` personal Hermes profile modernised and brought up under
  systemd with the Telegram platform.
- Two infra bugs fixed: systemd `ProtectHome=read-only` + missing
  `~/.local/state` in `ReadWritePaths` (Telegram lock failed with EROFS);
  ghost gateway from a deleted `/opt/hermes-agent` install still holding
  the bot token (evicted).
- 10+ new helper scripts under `scripts/`: `sync_skill_to_profile`,
  `wire_sms_reply_path`, `simulate_inbound_sms`, `twilio_recent`,
  `twilio_failure_detail`, `twilio_msg_body`, `setup_personal_telegram_agent`,
  `fix_systemd_state_writable`, `evict_ghost_gateway`, `inspect_mrfence_full`,
  `diag_hermes_installs`, `diag_telegram_locks`,
  `patch_mrfence_webhook_toolsets`.
