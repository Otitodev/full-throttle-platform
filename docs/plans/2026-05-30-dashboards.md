# Full Throttle Dashboards — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Read **Phase -1 (data source contracts)** before anything else — every downstream task cites it.

**Goal:** Build two dashboard UIs — a per-client dashboard for fence company owners and an admin dashboard for the Full Throttle operator — using the Hermes broadcast-terminal design language, backed by the existing governance audit log and gateway infrastructure.

**Architecture:** A single lightweight FastAPI aggregator service reads `audit.jsonl` + skill state across all profiles, exposing a REST API on `127.0.0.1:9201`. Two standalone React/Vite SPAs (one per dashboard) consume that API. The aggregator runs as a systemd unit; the SPAs are static files served by Caddy behind basicauth (admin) or a per-client Bearer token (client), reusing the `caddy.d/` fragment pattern.

**Tech Stack:** Python 3.11 (FastAPI, PyYAML, aiosqlite), TypeScript (React 19, Vite, **Tailwind + shadcn/ui** — Radix-based, no fictional libs), Caddy (auto-HTTPS, basicauth), systemd.

**Design system:** Hermes broadcast-terminal aesthetic. See `dashboards/client-mockup.html` and `dashboards/admin-mockup.html` for the visual target.

**Responsive scope (v1):** Owner dashboard MUST be mobile-friendly (owners check from the truck). Admin dashboard is desktop-first. Both use a single responsive Tailwind layout — no separate mobile build.

---

## Phase -1: Data source contracts (read first)

Every metric and list rendered by either dashboard comes from one of these sources. This pins the
mapping so no task downstream can guess.

| Metric / list | Source of truth | Path / table | Notes |
|---|---|---|---|
| Active gateway / health | `systemctl is-active hermes-gateway@<slug>` | (host) | Cache 5s; one shell call per profile per refresh |
| Session count, last_active, token spend | `state.db` | `sessions` table | **Read-only:** `file:.../state.db?mode=ro&immutable=0`, `PRAGMA query_only=1`. WAL means writer keeps writing — reader sees a consistent snapshot. |
| Mutations / activity timeline | `audit.jsonl` | `<HERMES_HOME>/governance/audit.jsonl` | Per-profile; merge across profiles for admin views |
| Pending approvals | `audit.jsonl` | rows where `approval_state == "pending"` | Same file |
| **Leads list / counts** | `audit.jsonl` (primary) + `<HERMES_HOME>/lead-response/leads_crm.jsonl` (manual adapter only, optional enrichment) | — | The audit log row (`skill=lead-response, action=intake`) is the only universal source — jobber/CRM-adapter clients have no local JSONL. Display from audit; enrich with `leads_crm.jsonl` when present. |
| **Published content list** | `audit.jsonl` | rows where `skill=content-publisher, action=publish, status=ok` | The publish state under `<HERMES_HOME>/content-publisher/` is for *dedup* — not the public list. |
| Social posts | `audit.jsonl` | `skill=social-scheduler` | Same pattern |
| Review responses | `audit.jsonl` | `skill=review-automation` | Same pattern |
| Cron job state | `<HERMES_HOME>/cron/jobs.json` | — | Already aggregated by `governance/status.py` |
| Client config (display_name, services, brand_voice, port, adapter) | `<HERMES_HOME>/config.yaml` | — | PyYAML; deep-merge defaults if needed |
| Per-client dashboard token | `<HERMES_HOME>/.env` | `FT_DASHBOARD_TOKEN=...` | Written at onboarding (Task 2.4) |

**Profile root:** `FT_PROFILES_ROOT` env var (default `/home/hermes/.hermes/profiles`). NOT
`HERMES_HOME` — that's per-profile.

**Caching:** the audit log re-read scales linearly with mutations × profiles. The aggregator
caches each `audit.jsonl` parse keyed by `(path, mtime)`. Cache invalidates when mtime changes.

**PII / retention (v1):**
- Lead rows contain phone/email — owners see their own, admin sees redacted by default (last 4 of phone, domain of email). Full unredacted view is gated by an `?unredact=1` query that the aggregator audits.
- `audit.jsonl` retention is "forever" until log rotation is added (tracked as a future task, NOT in this plan).
- No DSAR / deletion API in v1; documented as a known gap.

---

## Phase 0: Data Layer — Aggregator Service

A single FastAPI process reads all profiles and serves dashboard data. **Binds 127.0.0.1:9201**
(never 0.0.0.0 — Caddy fronts it).

### Task 0.1: Scaffold aggregator project skeleton

**Files:**
- Create: `aggregator/pyproject.toml`, `aggregator/app.py`, `aggregator/__init__.py`, `aggregator/auth.py`, `aggregator/routes_admin.py`, `aggregator/routes_client.py`, `aggregator/config.py`

```toml
# pyproject.toml
[project]
name = "fullthrottle-aggregator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115", "uvicorn[standard]>=0.34",
    "pyyaml>=6.0", "aiosqlite>=0.20", "pydantic>=2.0",
    "python-dotenv>=1.0",
]
```

```python
# app.py — minimal
from fastapi import FastAPI
app = FastAPI(title="Full Throttle Aggregator")

@app.get("/healthz")
def healthz(): return {"ok": True}

def main():
    import uvicorn
    # NEVER bind to 0.0.0.0; Caddy is the only frontdoor.
    uvicorn.run("app:app", host="127.0.0.1", port=9201)
```

```python
# config.py
import os
from pathlib import Path
PROFILES_ROOT = Path(os.environ.get("FT_PROFILES_ROOT", "/home/hermes/.hermes/profiles"))
```

**Verify:** `cd aggregator && python -c "from app import app; print(app.title)"` → `Full Throttle Aggregator`. Then `python -m aggregator.app &` and `curl -fsS http://127.0.0.1:9201/healthz` → `{"ok":true}`; `curl -fsS http://<droplet-ip>:9201/healthz` → connection refused (proves 127.0.0.1-only bind).

---

### Task 0.2: Profile discovery — scan all Hermes profiles

**Files:** `aggregator/profiles.py`, `aggregator/test_profiles.py`

Iterates `FT_PROFILES_ROOT/*/` (skip dotfiles + non-dirs). For each profile reads:
- `config.yaml` (PyYAML) → display_name, site_type, adapter, port, brand_voice, services.
- `state.db` (aiosqlite, **read-only URI** `file:...?mode=ro` + `PRAGMA query_only=1`) → session_count (rows in `sessions`), last_active (max `started_at`), token spend.
- `systemctl is-active hermes-gateway@<slug>` → `gateway_active` boolean. Cache 5s.

Returns `list[ProfileMeta]` (Pydantic): slug, display_name, site_type, adapter, port, gateway_active, session_count, last_active.

**Verify:** Unit test with a tmp-dir fixture containing two fake profiles (`config.yaml` + empty `state.db`); assert discovery returns two `ProfileMeta` objects with correct slugs. Mock `systemctl` via subprocess shim.

---

### Task 0.3: Audit log aggregator — merge audit.jsonl across profiles

**Files:** `aggregator/audit.py`, `aggregator/test_audit.py`

Reads `<profile>/governance/audit.jsonl` from each profile. **Caching:** `lru_cache`-style dict keyed by `(path, mtime_ns)`; on hit return parsed rows, on miss reparse. Cache eviction by mtime change only — no TTL needed.

Merges by timestamp descending. Filtering: by slug, skill, action, time range, approval_state.

Key shortcuts:
- `get_pending_approvals(slug=None) -> list[AuditEntry]` — all rows where `approval_state="pending"`.
- `recent_by_skill(skill, slug=None, limit=N)` — used for leads/content/social/reviews lists.

**Verify:** Unit test with fixture audit.jsonls across two profiles; assert merge order is timestamp-desc, filter works, cache hit (second call doesn't re-read the file — patch `Path.read_text` and assert call count).

---

### Task 0.4: Stats engine — thin wrapper around `governance/status.py`

**Files:** `aggregator/stats.py`, `aggregator/test_stats.py`

Do NOT reimplement what `skills/governance/scripts/status.py` already does (timeline, counts by action/status, approval queue, cron jobs). Instead:

- `compute_client_stats(slug)` shells out to `python <skill>/governance/scripts/status.py --json --state-dir <profile>/governance/` under that profile's HERMES_HOME, parses the JSON, and adds dashboard-only fields (leads_7d/30d from audit filtered by skill+action, recent_publishes count, avg_response_s if computable, etc.).
- `compute_platform_stats()` aggregates client stats: active_clients (gateway_active sum), total_leads_7d/30d (sum), approvals_pending (sum), mutations_24h (sum).

**Why shell out:** keeps the audit semantics single-sourced in the skill, so any future change to status.py automatically flows through.

**Verify:** Unit test asserts `compute_client_stats("test")` returns a dict containing keys produced by status.py plus the dashboard-only additions. Integration test: with a populated fixture profile, `total_leads_7d` equals the count of `skill=lead-response, action=intake` rows in the last 7 days.

---

### Task 0.5: Wire aggregator API routes

**Files:** Modify `aggregator/app.py`; create `aggregator/routes_admin.py`, `aggregator/routes_client.py`, `aggregator/auth.py`, `aggregator/test_routes.py`

**Admin API (basicauth handled by Caddy, no app-level auth — relies on 127.0.0.1 bind):**
```
GET /api/admin/platform/stats        → PlatformStats
GET /api/admin/clients               → list[ClientSummary]
GET /api/admin/clients/{slug}        → ClientDetail
GET /api/admin/approvals             → list[AuditEntry] (pending, all profiles)
GET /api/admin/audit?slug=&skill=&since=&limit= → list[AuditEntry]
GET /api/admin/leads?slug=&unredact=0|1 → list[LeadEntry] (default redacted)
```

**Client API (per-profile token, Bearer header ONLY):**
```
GET /api/client/{slug}/stats         → ClientStats
GET /api/client/{slug}/leads         → list[LeadEntry]
GET /api/client/{slug}/content       → list[ContentEntry]
GET /api/client/{slug}/activity      → list[AuditEntry]
GET /api/client/{slug}/approvals     → list[AuditEntry] (pending)
```

**Auth (`auth.py`):**
- Client routes: extract `Authorization: Bearer <token>` header (NOT query param — leaks to logs). Validate against the `FT_DASHBOARD_TOKEN` value in `<profile>/.env` (parsed via python-dotenv). Constant-time comparison (`hmac.compare_digest`). 401 on mismatch.
- Admin routes: no app-level check; rely on Caddy basicauth + 127.0.0.1 bind. The aggregator MUST refuse to start if it can't bind 127.0.0.1 specifically.

**PII redaction (`routes_admin.py`):** lead endpoints redact phone (`***-***-1234`) and email (`***@example.com`) by default. `?unredact=1` returns full values AND writes an audit entry `skill=dashboard, action=unredact, target=<slug>, status=ok` to the platform audit log (a new file at `FT_PROFILES_ROOT/../platform-audit.jsonl`).

**Verify:** Unit tests with FastAPI's `TestClient`:
1. `/api/client/test/stats` without Bearer → 401.
2. With wrong Bearer → 401.
3. With correct Bearer → 200 + expected shape.
4. `/api/admin/leads?slug=test` returns redacted phones; `?unredact=1` returns full + appends to platform-audit.jsonl.
5. `/api/client/foo/stats` with token belonging to slug `bar` → 401 (cross-tenant).

---

### Task 0.6: Systemd unit + Caddy config for aggregator

**Files:** `infra/systemd/fullthrottle-aggregator.service`, `infra/caddy/aggregator-admin.caddy.example`

Systemd unit:
```ini
[Unit]
Description=Full Throttle Aggregator (dashboard API)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=hermes
Group=hermes
Environment=FT_PROFILES_ROOT=/home/hermes/.hermes/profiles
ExecStart=/srv/full-throttle-platform/aggregator/.venv/bin/python -m aggregator.app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Caddy fragment (`aggregator-admin.caddy.example` — copied + edited at install time to inject domain + basicauth hash):
```
admin.ft.example.com {
    basicauth /api/admin/* {
        admin {$FT_ADMIN_PASSWORD_HASH}
    }
    handle /api/admin/* {
        reverse_proxy 127.0.0.1:9201
    }
    handle /healthz { respond "ok" 200 }
    # SPA served from /srv/.../dashboards/admin/dist (added in Task 1.4)
    log { output file /var/log/full-throttle/admin-access.log }
}
```

**Verify:**
1. `systemd-analyze verify infra/systemd/fullthrottle-aggregator.service` clean.
2. `caddy validate --adapter caddyfile --config infra/caddy/aggregator-admin.caddy.example` clean (with env vars stubbed).
3. After install (post Task 1.4): `systemctl status fullthrottle-aggregator` active; `curl -fsS https://admin.ft.example.com/healthz` 200; `curl -fsSi https://admin.ft.example.com/api/admin/clients` → 401 (no basicauth); with `-u admin:<password>` → 200.

---

## Phase 1: Admin Dashboard (Operator View)

### Task 1.1: Scaffold admin React app

**Files:** Create `dashboards/admin/` (Vite + React 19 + TypeScript + Tailwind + shadcn/ui).

Init: `npm create vite@latest admin -- --template react-ts`; install `tailwindcss postcss autoprefixer @radix-ui/* class-variance-authority`. NO `@nous-research/ui` — it doesn't exist.

Reuse the broadcast-terminal CSS variables from the HTML mockups (CSS custom properties `--bg`, `--mid`, `--font-mono` etc.) — copy into `src/index.css`.

**Verify:** `npm run build` succeeds; `npm run dev` shows a "Full Throttle Admin" placeholder page.

---

### Task 1.2: Aggregate stats row (top of overview)

**Files:** `dashboards/admin/src/components/StatsRow.tsx`, `dashboards/admin/src/api.ts`

Fetches `/api/admin/platform/stats` (polling every 30s with `setInterval` — REST polling, no WebSockets in v1, so dashboards lag by up to 30s).

**Verify:** With aggregator running and a fixture profile populated, the component renders the 5 stat tiles from the mockup.

---

### Task 1.3: Client table

**Files:** `dashboards/admin/src/components/ClientTable.tsx`

Sortable table with health dot (gateway_active), columns from `ClientSummary`. Row click → navigate to `/clients/:slug`.

**Verify:** With ≥2 fixture clients, table renders both; click navigates.

---

### Task 1.4: Approval queue sidebar

**Files:** `dashboards/admin/src/components/ApprovalQueue.tsx`

Fetches `/api/admin/approvals`. Shows pending items grouped by client.

**Verify:** Fixture audit.jsonl with one `approval_state=pending` row renders one card.

---

### Task 1.5: Audit trail feed

**Files:** `dashboards/admin/src/components/AuditTrail.tsx`

Fetches `/api/admin/audit?limit=50`. Renders the timeline from the mockup with skill/action/target/status/timestamp.

**Verify:** Renders the last 50 audit rows in timestamp-desc order.

---

### Task 1.6: Compose Overview page

**Files:** `dashboards/admin/src/pages/Overview.tsx`, router setup

Combines 1.2 / 1.3 / 1.4 / 1.5 per the admin mockup layout.

**Verify:** Page matches `dashboards/admin-mockup.html` visually (manual check); no console errors.

---

### Task 1.7: Client drill-down page

**Files:** `dashboards/admin/src/pages/ClientDetail.tsx`

Reuses the client-dashboard components (Phase 2) wrapped in admin chrome. Fetches `/api/admin/clients/{slug}`.

**Verify:** Clicking a client row in 1.3 loads the detail page; data matches the per-client mockup.

---

### Task 1.8: Admin basicauth password setup

**Files:** Modify `infra/install_server.sh`

Add a step (idempotent — skip if hash file exists):
```bash
step_admin_password() {
  local hash_file=/etc/full-throttle/.admin-password.hash
  if [ -f "$hash_file" ]; then ok "admin password already set"; return; fi
  log "generating admin dashboard password"
  local pw; pw=$(openssl rand -base64 24)
  caddy hash-password --plaintext "$pw" > "$hash_file"
  chmod 600 "$hash_file"
  echo "ADMIN PASSWORD (save now, not shown again): $pw"
}
```

The Caddy fragment references the hash via `{$FT_ADMIN_PASSWORD_HASH}` env imported by systemd from the file.

**Verify:** Running `install_server.sh` on a clean box prints the password once; re-running prints `[ok] admin password already set` and does not overwrite.

---

### Task 1.9: Admin dashboard deployment

**Files:** `infra/caddy/admin-dashboard.caddy.example`, modify `infra/install_server.sh`

SPA built (`cd dashboards/admin && npm run build`) to `dashboards/admin/dist`. Caddy serves it at `admin.ft.example.com` (with SPA fallback for client-side routing) plus the basicauth-gated `/api/admin/*` from Task 0.6.

```
admin.ft.example.com {
    basicauth /api/admin/* {
        admin {$FT_ADMIN_PASSWORD_HASH}
    }
    handle /api/admin/* {
        reverse_proxy 127.0.0.1:9201
    }
    handle /healthz { respond "ok" 200 }
    root * /srv/full-throttle-platform/dashboards/admin/dist
    try_files {path} /index.html
    file_server
    log { output file /var/log/full-throttle/admin-access.log }
}
```

`install_server.sh` adds a `--admin-domain <host>` flag that, when passed, materializes the fragment from the `.example` with the domain substituted.

**Verify:** `curl -fsS https://admin.ft.example.com/` returns the SPA HTML; deep link `/clients/foo` also returns the SPA HTML (try_files fallback works); `/api/admin/clients` without auth → 401; with auth → 200.

---

## Phase 2: Per-Client Dashboard (Owner View)

### Task 2.1: Scaffold client React app

**Files:** Create `dashboards/client/` (Vite + React + TypeScript + Tailwind + shadcn/ui, **mobile-first responsive**).

**Verify:** `npm run build` succeeds; viewport at 375px shows a usable mobile layout.

---

### Task 2.2: Client stats row

**Files:** `dashboards/client/src/components/ClientStatsRow.tsx`, `dashboards/client/src/api.ts`

Fetches `/api/client/{slug}/stats` with Bearer header from a runtime-injected `<meta name="ft-token">` (the Caddy fragment will inject this at HTML-serve time, see Task 2.4).

**Verify:** Renders 4 stat tiles per the client mockup; fails gracefully with a "not authenticated" view if the token is missing.

---

### Task 2.3: Inbound leads list

**Files:** `dashboards/client/src/components/LeadList.tsx`

**Verify:** Renders the last 20 lead intake rows; tap-to-call (`tel:` link) works on mobile.

---

### Task 2.4: Approval cards

**Files:** `dashboards/client/src/components/ApprovalCards.tsx`

Pending items the owner needs to approve. v1: read-only display (no approve/deny UI — that's a future task, owners approve via SMS/clarify). Documented in the component.

**Verify:** Renders pending cards from `/api/client/{slug}/approvals`.

---

### Task 2.5: Recently published content list

**Files:** `dashboards/client/src/components/ContentList.tsx`

**Verify:** Renders publish-action audit rows; clicking a row opens the published URL (from `target` field).

---

### Task 2.6: Activity feed

**Files:** `dashboards/client/src/components/ActivityFeed.tsx`

Compact mobile-friendly version of the admin AuditTrail.

**Verify:** Renders activity feed; vertical-scroll works on mobile.

---

### Task 2.7: Compose Dashboard page

**Files:** `dashboards/client/src/pages/Dashboard.tsx`, router setup

Combines 2.2–2.6 per the client mockup. Mobile-first: stack vertically below 768px, two-column above.

**Verify:** Matches `dashboards/client-mockup.html` at desktop; usable at 375px width.

---

### Task 2.8: Update `promote_client.sh` + Caddy fragment for `/dash`

**Files:** Modify `infra/promote_client.sh`, `infra/caddy/example-client.caddy`

Updated Caddy fragment pattern. Key: `try_files` fallback for SPA routing, and `/api/client/*` proxied to aggregator. `respond /healthz` MUST come before fallthroughs so the gateway-down case still returns 200:

```caddy
<SLUG>.hooks.<base-domain> {
    respond /healthz "ok" 200

    handle /api/client/* {
        reverse_proxy 127.0.0.1:9201
    }

    handle_path /dash/* {
        root * /srv/full-throttle-platform/dashboards/client/dist
        try_files {path} /index.html
        file_server
    }

    # Webhooks (default) → the per-client Hermes gateway
    reverse_proxy 127.0.0.1:<PORT>

    request_body { max_size 1MB }
    log { output file /var/log/full-throttle/<SLUG>-access.log }
}
```

`promote_client.sh` reads the slug's token from `<profile>/.env` (`FT_DASHBOARD_TOKEN`) and prints
the dashboard URL (`https://<slug>.hooks.<base>/dash#token=<token>` — fragment, NOT query — so
the token never hits the access log) at the end of promotion. The SPA reads `location.hash` to
extract it and stores it in `sessionStorage`, then strips it from the URL.

**Verify:**
1. `caddy validate` clean on the updated fragment.
2. After re-promoting a test client: `curl -fsS https://test.hooks.<ip>.nip.io/dash` returns SPA HTML; `/dash/leads` (deep link) also returns SPA HTML (try_files fallback); `/api/client/test/stats` without Bearer → 401; with Bearer → 200; `/webhooks/lead` POST still reaches the per-client gateway.

---

### Task 2.9: Re-promote already-onboarded clients

**Files:** `infra/repromote_all.sh` (new)

Existing clients promoted before this plan landed have the old Caddy fragment (no `/dash`, no `/api/client/*`). Add a small script:

```bash
#!/usr/bin/env bash
# Re-runs promote_client.sh for every client with an active gateway unit,
# refreshing their Caddy fragment to the latest template.
set -euo pipefail
BASE_DOMAIN="${1:?usage: $0 <base-domain>}"
for unit in $(systemctl list-units --type=service --state=active --no-legend 'hermes-gateway@*' | awk '{print $1}'); do
    slug=$(echo "$unit" | sed 's/hermes-gateway@\(.*\)\.service/\1/')
    echo "==> re-promoting $slug"
    bash /srv/full-throttle-platform/infra/promote_client.sh "$slug" --base-domain "$BASE_DOMAIN"
done
```

**Verify:** With two fake gateway units (or one real test client), running `repromote_all.sh hooks.X.nip.io` re-runs promote for each, and the Caddy fragments now include `/dash` + `/api/client/*`.

---

### Task 2.10: Generate dashboard token during onboarding

**Files:** Modify `scripts/onboard_client.py`

Add at top: `import secrets`. When writing the `.env`, include:
```python
env_lines.append(f"FT_DASHBOARD_TOKEN={secrets.token_urlsafe(32)}")
```
(Skip if `FT_DASHBOARD_TOKEN` already present — don't rotate on re-onboard.)

Include the token + dashboard URL in the summary JSON and `NEXT_STEPS.md`.

**Verify:** `python scripts/onboard_client.py --intake test.intake.json --secrets test.secrets.json` produces a `.env` with a `FT_DASHBOARD_TOKEN=...` line; re-running with `--force` preserves the existing token.

---

## Phase 3: Polish & Documentation

### Task 3.1: Add dashboards to ARCHITECTURE.md

**Files:** Modify `ARCHITECTURE.md` — add `## 16. Dashboards` section: data sources, auth model, aggregator topology, scaling notes.

### Task 3.2: Update infra/README.md

**Files:** Modify `infra/README.md` — document admin password setup, dashboard token retrieval, `repromote_all.sh`.

### Task 3.3: Add aggregator + admin checks to install_server.sh

**Files:** Modify `infra/install_server.sh` — `--check` verifies aggregator unit is active and `/healthz` responds.

---

## Data Flow

```
                Aggregator (127.0.0.1:9201)
  reads profiles/*/{config.yaml,state.db?mode=ro,governance/audit.jsonl}
                    │
     ┌──────────────┴──────────────┐
     ▼                              ▼
GET /api/admin/*              GET /api/client/{slug}/*
(basicauth via Caddy)         (Bearer token from <profile>/.env)
     │                              │
     ▼                              ▼
Admin Dashboard               Client Dashboard
(static SPA, desktop)         (static SPA, mobile-first, one build)
admin.ft.example.com          {slug}.hooks.example.com/dash
                              token via #fragment → sessionStorage
```

## Build Order

```
Phase -1 (Data contracts)  ← read first, no code
Phase 0 (Aggregator)       ← must complete first
   Tasks 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6

Phase 1 (Admin)            ← depends on Phase 0
   Tasks 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9

Phase 2 (Client)           ← depends on Phase 0; can parallel Phase 1
   Tasks 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8 → 2.9 → 2.10

Phase 3 (Docs)             ← can be done anytime after the others
```

## Files Summary

| File | Action | Phase |
|---|---|---|
| `aggregator/` (7 .py + tests) | Create | 0 |
| `infra/systemd/fullthrottle-aggregator.service` | Create | 0.6 |
| `infra/caddy/aggregator-admin.caddy.example` | Create | 0.6 |
| `dashboards/admin/` (Vite project) | Create | 1.1 |
| `dashboards/admin/src/components/*` (5 components) | Create | 1.2–1.5 |
| `dashboards/admin/src/pages/{Overview,ClientDetail}.tsx` | Create | 1.6, 1.7 |
| `dashboards/client/` (Vite project) | Create | 2.1 |
| `dashboards/client/src/components/*` (5 components) | Create | 2.2–2.6 |
| `dashboards/client/src/pages/Dashboard.tsx` | Create | 2.7 |
| `infra/caddy/admin-dashboard.caddy.example` | Create | 1.9 |
| `infra/repromote_all.sh` | Create | 2.9 |
| `infra/promote_client.sh` | Modify | 2.8 |
| `infra/caddy/example-client.caddy` | Modify | 2.8 |
| `scripts/onboard_client.py` | Modify | 2.10 |
| `infra/install_server.sh` | Modify | 1.8, 1.9, 3.3 |
| `ARCHITECTURE.md` | Modify | 3.1 |
| `infra/README.md` | Modify | 3.2 |

## Known gaps (NOT in this plan)

- **Approval action UI** (approve/deny buttons on owner dashboard) — v1 owners approve via SMS/clarify; dashboard is read-only for approvals.
- **WebSocket live updates** — REST polling only; dashboards lag by ≤30s.
- **Audit log rotation** — `audit.jsonl` grows forever. Document as future work.
- **DSAR / lead deletion API** — no PII deletion path.
- **Multi-droplet HA** — single-droplet only, same as the rest of the platform.
