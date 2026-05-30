"""Routes integration tests — uses FastAPI's TestClient and tmp-dir profiles.

Covers the must-have Phase 0 §0.5 cases:

1. ``/api/client/<slug>/stats`` without Bearer → 401.
2. With wrong Bearer → 401.
3. With correct Bearer → 200.
4. ``/api/admin/leads?slug=...`` redacts phone/email by default;
   ``?unredact=1`` returns full + appends to platform-audit.jsonl.
5. ``/api/client/foo/stats`` with token belonging to slug ``bar`` → 401
   (cross-tenant rejected).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aggregator import audit as audit_mod
from aggregator import config
from aggregator import profiles as profiles_mod


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_config_yaml(profile_dir: Path, *, slug: str, port: int = 8888) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "config.yaml").write_text(
        f"""site_type: augment
publishing:
  adapter: manual
client:
  business_name: Test {slug}
platforms:
  webhook:
    enabled: true
    extra:
      port: {port}
""",
        encoding="utf-8",
    )


def _write_state_db(profile_dir: Path) -> None:
    db = profile_dir / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL, "
            "started_at REAL NOT NULL, input_tokens INTEGER DEFAULT 0, "
            "output_tokens INTEGER DEFAULT 0, actual_cost_usd REAL DEFAULT 0.0)"
        )
        conn.commit()
    finally:
        conn.close()


def _write_env(profile_dir: Path, token: str) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / ".env").write_text(
        f'FT_DASHBOARD_TOKEN={token}\n', encoding="utf-8"
    )


def _write_audit(profile_dir: Path, rows: list[dict]) -> None:
    gov = profile_dir / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    with (gov / "audit.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _lead_row(
    id_: str, *, target: str, ts_epoch: float
) -> dict:
    from datetime import datetime, timezone

    return {
        "id": id_,
        "ts": datetime.fromtimestamp(ts_epoch, tz=timezone.utc).isoformat(),
        "skill": "lead-response",
        "action": "lead_first_touch",
        "target": target,
        "status": "ok",
        "approval_state": "none",
    }


# ---------------------------------------------------------------------------
# Fixtures — point the aggregator at a fresh tmp PROFILES_ROOT for every test.
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    profiles_root = tmp_path / "profiles"
    profiles_root.mkdir()
    monkeypatch.setattr(config, "PROFILES_ROOT", profiles_root)
    monkeypatch.setattr(
        config, "PLATFORM_AUDIT_PATH", tmp_path / "platform-audit.jsonl"
    )
    monkeypatch.setattr(profiles_mod.shutil, "which", lambda _name: None)
    audit_mod._clear_audit_cache()
    profiles_mod._clear_health_cache()

    # Import the app late so routers see the patched config.
    from aggregator.app import app

    with TestClient(app) as c:
        yield c, profiles_root, tmp_path

    audit_mod._clear_audit_cache()
    profiles_mod._clear_health_cache()


# ---------------------------------------------------------------------------
# 1–3, 5: Bearer auth on client routes
# ---------------------------------------------------------------------------


def test_client_stats_without_bearer_returns_401(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    _write_env(root / "alpha", token="secret-token-alpha")

    resp = c.get("/api/client/alpha/stats")
    assert resp.status_code == 401


def test_client_stats_with_wrong_bearer_returns_401(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    _write_env(root / "alpha", token="secret-token-alpha")

    resp = c.get(
        "/api/client/alpha/stats", headers={"Authorization": "Bearer not-it"}
    )
    assert resp.status_code == 401


def test_client_stats_with_correct_bearer_returns_200(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    _write_env(root / "alpha", token="secret-token-alpha")
    _write_audit(root / "alpha", [])

    resp = c.get(
        "/api/client/alpha/stats",
        headers={"Authorization": "Bearer secret-token-alpha"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "alpha"
    assert "leads_7d" in body
    assert body["meta"]["slug"] == "alpha"


def test_cross_tenant_token_rejected(client):
    c, root, _ = client
    _write_config_yaml(root / "foo", slug="foo")
    _write_state_db(root / "foo")
    _write_env(root / "foo", token="foo-token")
    _write_config_yaml(root / "bar", slug="bar")
    _write_state_db(root / "bar")
    _write_env(root / "bar", token="bar-token")

    # Present bar's token for foo's URL → must be 401.
    resp = c.get(
        "/api/client/foo/stats", headers={"Authorization": "Bearer bar-token"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4: Admin leads redaction
# ---------------------------------------------------------------------------


def test_admin_leads_default_redacted(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    now = time.time()
    _write_audit(
        root / "alpha",
        [
            _lead_row("l1", target="sms:+18505551234", ts_epoch=now - 60),
            _lead_row("l2", target="email:jane@mrfence.example", ts_epoch=now - 120),
        ],
    )

    resp = c.get("/api/admin/leads?slug=alpha")
    assert resp.status_code == 200
    leads = resp.json()
    assert any(L["id"] == "l1" and L["target"] == "sms:***-***-1234" for L in leads)
    assert any(
        L["id"] == "l2" and L["target"] == "email:***@mrfence.example" for L in leads
    )


def test_admin_leads_unredact_writes_platform_audit(client):
    c, root, tmp_path = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    now = time.time()
    _write_audit(
        root / "alpha",
        [_lead_row("l1", target="sms:+18505551234", ts_epoch=now - 60)],
    )

    resp = c.get("/api/admin/leads?slug=alpha&unredact=1")
    assert resp.status_code == 200
    leads = resp.json()
    assert leads[0]["target"] == "sms:+18505551234"  # full value

    audit_path = config.PLATFORM_AUDIT_PATH
    assert audit_path.is_file()
    rows = [
        json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()
    ]
    assert any(
        r["skill"] == "dashboard"
        and r["action"] == "unredact_leads"
        and r["target"] == "slug=alpha"
        for r in rows
    )


# ---------------------------------------------------------------------------
# Misc: admin endpoints sanity
# ---------------------------------------------------------------------------


def test_admin_platform_stats_works_without_auth(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")
    _write_config_yaml(root / "beta", slug="beta")
    _write_state_db(root / "beta")

    resp = c.get("/api/admin/platform/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_clients"] == 2


def test_admin_clients_list(client):
    c, root, _ = client
    _write_config_yaml(root / "alpha", slug="alpha")
    _write_state_db(root / "alpha")

    resp = c.get("/api/admin/clients")
    assert resp.status_code == 200
    body = resp.json()
    assert [m["slug"] for m in body] == ["alpha"]


def test_healthz_open(client):
    c, _root, _ = client
    resp = c.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
