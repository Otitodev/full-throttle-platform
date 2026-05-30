# Full Throttle Dashboards — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build two dashboard UIs — a per-client dashboard for fence company owners and an admin dashboard for the Full Throttle operator — using the Hermes broadcast-terminal design language, backed by the existing governance audit log and gateway infrastructure.

**Architecture:** A single lightweight FastAPI aggregator service reads `audit.jsonl` + gateway status across all profiles, exposing a REST API. Two standalone React/Vite SPAs (one per dashboard) consume that API. The aggregator runs as a systemd unit; the SPAs are static files served by Caddy behind basicauth (admin) or a per-client token (client), reusing the `caddy.d/` fragment pattern.

**Tech Stack:** Python 3.11 (FastAPI, PyYAML, aiosqlite), TypeScript (React 19, Vite, @nous-research/ui), Caddy (auto-HTTPS, basicauth), systemd.

**Design system:** Hermes broadcast-terminal aesthetic. See `dashboards/client-mockup.html` and `dashboards/admin-mockup.html` for the visual target.

---

## Phase 0: Data Layer — Aggregator Service

A single FastAPI process reads all profiles and serves dashboard data. Not per-profile — system-wide.

### Task 0.1: Scaffold aggregator project skeleton

**Files:**
- Create: `aggregator/pyproject.toml`, `aggregator/app.py`, `aggregator/__init__.py`, `aggregator/auth.py`, `aggregator/routes_admin.py`, `aggregator/routes_client.py`

```toml
# pyproject.toml
[project]
name = "fullthrottle-aggregator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115", "uvicorn[standard]>=0.34",
    "pyyaml>=6.0", "aiosqlite>=0.20", "pydantic>=2.0",
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
    uvicorn.run("app:app", host="127.0.0.1", port=9201)
```

**Verify:** `cd aggregator && python -c "from app import app; print(app.title)"` → `Full Throttle Aggregator`

---

### Task 0.2: Profile discovery — scan all Hermes profiles

**Files:** `aggregator/profiles.py`, `aggregator/test_profiles.py`

Reads `/home/hermes/.hermes/profiles/*/` → `config.yaml` (PyYAML) + `state.db` (aiosqlite for session counts) + `systemctl is-active` for gateway status.

Returns `list[ProfileMeta]` with: slug, display_name, site_type, adapter, domain, port, gateway_active, session_count, last_active.

---

### Task 0.3: Audit log aggregator — merge audit.jsonl across profiles

**Files:** `aggregator/audit.py`, `aggregator/test_audit.py`

Reads `<profile>/governance/audit.jsonl` from all profiles, parses JSONL, merges by timestamp descending. Supports filtering by slug, skill, time range, approval_state.

Key shortcuts: `get_pending_approvals()` returns all entries with `approval_state=pending` across all profiles.

---

### Task 0.4: Stats engine — compute cross-profile metrics

**Files:** `aggregator/stats.py`, `aggregator/test_stats.py`

`compute_platform_stats()` → active_clients, total_leads_7d/30d, avg_response_s, approvals_pending, mutations_24h.
`compute_client_stats(slug)` → per-client variant.

---

### Task 0.5: Wire aggregator API routes

**Files:** Modify `aggregator/app.py`, `aggregator/routes_admin.py`, `aggregator/routes_client.py`, `aggregator/auth.py`

**Admin API (basicauth via Caddy, no app-level auth):**
```
GET /api/admin/platform/stats      → PlatformStats
GET /api/admin/clients             → list[ClientSummary]
GET /api/admin/clients/{slug}      → ClientDetail
GET /api/admin/approvals           → list[AuditEntry] (pending)
GET /api/admin/audit?slug=&skill=&since=&limit= → list[AuditEntry]
```

**Client API (per-profile token from .env):**
```
GET /api/client/{slug}/stats       → ClientStats
GET /api/client/{slug}/leads       → list[LeadEntry]
GET /api/client/{slug}/content     → list[ContentEntry]
GET /api/client/{slug}/activity    → list[AuditEntry]
GET /api/client/{slug}/approvals   → list[AuditEntry] (pending)
```

**Auth:** Client routes validate `FT_DASHBOARD_TOKEN` from query param or Bearer header against the profile's `.env`.

---

### Task 0.6: Systemd unit + Caddy config for aggregator

**Files:** `infra/systemd/fullthrottle-aggregator.service`, `infra/caddy/aggregator-admin.caddy`

Systemd unit runs as `hermes` user on port 9201. Caddy fragment for the admin domain with basicauth, proxying to `:9201`.

---

## Phase 1: Admin Dashboard (Operator View)

### Task 1.1: Scaffold admin React app

**Files:** Create `dashboards/admin/` (Vite + React + TypeScript + `@nous-research/ui` + Tailwind)

### Task 1.2: Platform overview page

**Files:** `dashboards/admin/src/pages/Overview.tsx`, `dashboards/admin/src/components/StatsRow.tsx`, `dashboards/admin/src/components/ClientTable.tsx`, `dashboards/admin/src/components/ApprovalQueue.tsx`, `dashboards/admin/src/components/AuditTrail.tsx`

Matches the mockup: aggregate stats row, sortable client table with health dots, approval queue sidebar, audit trail feed.

### Task 1.3: Client drill-down page

**Files:** `dashboards/admin/src/pages/ClientDetail.tsx`

Click a client → full detail view reusing per-client components but with admin chrome.

### Task 1.4: Admin dashboard deployment

**Files:** `infra/caddy/admin-dashboard.caddy`, modify `infra/install_server.sh`

SPA built to static files, served by Caddy at `admin.ft.example.com` with basicauth. API calls at `/api/*` proxied to aggregator.

---

## Phase 2: Per-Client Dashboard (Owner View)

### Task 2.1: Scaffold client React app

**Files:** Create `dashboards/client/` (Vite + React + TypeScript, simpler than admin)

### Task 2.2: Client dashboard pages

**Files:** `dashboards/client/src/pages/Dashboard.tsx`, `dashboards/client/src/components/ClientStatsRow.tsx`, `dashboards/client/src/components/LeadList.tsx`, `dashboards/client/src/components/ContentList.tsx`, `dashboards/client/src/components/ActivityFeed.tsx`, `dashboards/client/src/components/ApprovalCards.tsx`

Matches the mockup: stats, inbound leads, pending approvals, recently published, activity feed.

### Task 2.3: Deploy via promote_client.sh

**Files:** Modify `infra/promote_client.sh`, `infra/caddy/example-client.caddy`

The client dashboard SPA is built once (one build, same files for all clients). The Caddy fragment serves it at `/<SCHEDULE>.hooks.example.com/dash` while `/api/client/*` routes go to the aggregator.

**Updated Caddy fragment pattern:**
```
<SLUG>.hooks.example.com {
    handle_path /dash/* {
        root * /srv/full-throttle-platform/dashboards/client/dist
        file_server
    }
    handle /api/client/* {
        reverse_proxy 127.0.0.1:9201
    }
    reverse_proxy 127.0.0.1:<PORT>
    respond /healthz "ok" 200
    request_body { max_size 1MB }
    log { ... }
}
```

### Task 2.4: Generate dashboard token during onboarding

**Files:** Modify `scripts/onboard_client.py`

Add `secrets.token_urlsafe(32)` → write `FT_DASHBOARD_TOKEN=<token>` to profile `.env`.

---

## Phase 3: Polish & Documentation

### Task 3.1: Add dashboards to ARCHITECTURE.md

**Files:** Modify `ARCHITECTURE.md` — add `## 16. Dashboards` section.

### Task 3.2: Update infra/README.md

**Files:** Modify `infra/README.md` — document deploy and access.

### Task 3.3: Add aggregator check to install_server.sh

**Files:** Modify `infra/install_server.sh` — `--check` verifies aggregator is running.

---

## Data Flow

```
                Aggregator (:9201)
  reads profiles/*/{config.yaml,state.db,governance/audit.jsonl}
                    │
     ┌──────────────┴──────────────┐
     ▼                              ▼
GET /api/admin/*              GET /api/client/{slug}/*
     │                              │
     ▼                              ▼
Admin Dashboard               Client Dashboard
(static SPA)                  (static SPA, one build)
admin.ft.example.com          {slug}.hooks.example.com/dash
Caddy: basicauth              Caddy: token param
/api/* → :9201                /api/* → :9201
```

## Build Order

```
Phase 0 (Aggregator)  ← must complete first
   Tasks 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6

Phase 1 (Admin)       ← depends on Phase 0
   Tasks 1.1 → 1.2 → 1.3 → 1.4

Phase 2 (Client)      ← depends on Phase 0
   Tasks 2.1 → 2.2 → 2.3 → 2.4

Phase 3 (Docs)        ← can be done anytime
```

## Files Summary

| File | Action | Phase |
|---|---|---|
| `aggregator/` (6 .py + tests) | Create | 0 |
| `infra/systemd/fullthrottle-aggregator.service` | Create | 0.6 |
| `infra/caddy/aggregator-admin.caddy` | Create | 0.6 |
| `dashboards/admin/` (Vite project) | Create | 1 |
| `dashboards/client/` (Vite project) | Create | 2 |
| `infra/caddy/admin-dashboard.caddy` | Create | 1.4 |
| `infra/promote_client.sh` | Modify | 2.3 |
| `infra/caddy/example-client.caddy` | Modify | 2.3 |
| `scripts/onboard_client.py` | Modify | 2.4 |
| `infra/install_server.sh` | Modify | 1.4, 3.3 |
| `ARCHITECTURE.md` | Modify | 3.1 |
| `infra/README.md` | Modify | 3.2 |
