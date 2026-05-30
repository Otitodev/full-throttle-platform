# Full Throttle Aggregator

Read-only FastAPI service that aggregates state across all Hermes profiles for
the dashboards (admin + per-client). See `docs/plans/2026-05-30-dashboards.md`
for the full design.

## Layout

```
aggregator/
  app.py            FastAPI entrypoint (binds 127.0.0.1:9201 only)
  config.py         Env-driven runtime config (FT_PROFILES_ROOT, BIND_*)
  profiles.py       Profile discovery + ProfileMeta (Task 0.2)
  audit.py          audit.jsonl reader w/ mtime cache (Task 0.3)
  stats.py          Stats engine wrapping governance/status.py (Task 0.4)
  auth.py           Bearer + Caddy-basicauth (Task 0.5)
  routes_admin.py   /api/admin/* (Task 0.5)
  routes_client.py  /api/client/{slug}/* (Task 0.5)
```

## Run locally

```bash
cd aggregator
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
FT_PROFILES_ROOT=~/.hermes/profiles python -m aggregator.app
```

## Why 127.0.0.1 only

Caddy is the single public frontdoor. The aggregator refuses to start if
`BIND_HOST` is anything other than `127.0.0.1` — a stray `0.0.0.0` here would
expose every client's audit log unauthenticated.
