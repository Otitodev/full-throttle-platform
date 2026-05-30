"""Unit + integration tests for aggregator.stats."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from aggregator import audit as audit_mod
from aggregator import profiles as profiles_mod
from aggregator import stats


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_audit_rows(profile_dir: Path, rows: list[dict]) -> Path:
    gov = profile_dir / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    p = gov / "audit.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


def _write_minimal_config(profile_dir: Path, *, slug: str, port: int = 8888) -> None:
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


def _row(
    *,
    id_: str,
    skill: str,
    action: str,
    ts_epoch: float,
    status: str = "ok",
    approval_state: str = "none",
) -> dict:
    return {
        "id": id_,
        "ts": _iso_from_epoch(ts_epoch),
        "skill": skill,
        "action": action,
        "target": f"target-{id_}",
        "status": status,
        "approval_state": approval_state,
    }


def _iso_from_epoch(ts: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def _isolate_caches(monkeypatch):
    audit_mod._clear_audit_cache()
    profiles_mod._clear_health_cache()
    # No systemctl in CI — pretend gateways aren't active.
    monkeypatch.setattr(profiles_mod.shutil, "which", lambda _name: None)
    yield
    audit_mod._clear_audit_cache()
    profiles_mod._clear_health_cache()


# ---------------------------------------------------------------------------
# compute_client_stats
# ---------------------------------------------------------------------------


def test_client_stats_returns_dashboard_keys(tmp_path):
    root = tmp_path / "profiles"
    _write_minimal_config(root / "alpha", slug="alpha")
    now = time.time()
    _write_audit_rows(
        root / "alpha",
        [
            _row(id_="l1", skill="lead-response", action="lead_first_touch", ts_epoch=now - 60),
            _row(
                id_="l2",
                skill="lead-response",
                action="lead_first_touch",
                ts_epoch=now - 6 * stats._SECONDS_PER_DAY,
            ),
            _row(
                id_="l3",
                skill="lead-response",
                action="lead_first_touch",
                ts_epoch=now - 20 * stats._SECONDS_PER_DAY,
            ),
            # Outside both windows
            _row(
                id_="l4",
                skill="lead-response",
                action="lead_first_touch",
                ts_epoch=now - 40 * stats._SECONDS_PER_DAY,
            ),
            # Publish
            _row(
                id_="p1",
                skill="content-publisher",
                action="publish",
                ts_epoch=now - 60,
            ),
            # Pending approval
            _row(
                id_="g1",
                skill="governance",
                action="plan:publish",
                ts_epoch=now - 60,
                approval_state="pending",
            ),
        ],
    )

    payload = stats.compute_client_stats("alpha", root=root)
    assert payload["slug"] == "alpha"
    assert payload["leads_7d"] == 2  # l1 + l2
    assert payload["leads_30d"] == 3  # l1 + l2 + l3
    assert payload["recent_publishes_30d"] == 1
    assert payload["mutations_24h"] >= 3  # l1, p1, g1 within 24h
    assert payload["approvals_pending"] == 1


def test_client_stats_unknown_slug(tmp_path):
    root = tmp_path / "profiles"
    payload = stats.compute_client_stats("ghost", root=root)
    assert payload["ok"] is False
    assert "not found" in payload["error"]


# ---------------------------------------------------------------------------
# compute_platform_stats
# ---------------------------------------------------------------------------


def test_platform_stats_aggregates_across_profiles(tmp_path):
    root = tmp_path / "profiles"
    _write_minimal_config(root / "alpha", slug="alpha")
    _write_minimal_config(root / "beta", slug="beta", port=8889)
    now = time.time()
    _write_audit_rows(
        root / "alpha",
        [
            _row(id_="a1", skill="lead-response", action="lead_first_touch", ts_epoch=now - 100),
            _row(
                id_="a2",
                skill="governance",
                action="plan:publish",
                ts_epoch=now - 200,
                approval_state="pending",
            ),
        ],
    )
    _write_audit_rows(
        root / "beta",
        [
            _row(id_="b1", skill="lead-response", action="lead_first_touch", ts_epoch=now - 300),
            _row(id_="b2", skill="lead-response", action="lead_first_touch", ts_epoch=now - 400),
        ],
    )

    payload = stats.compute_platform_stats(root=root)
    assert payload["total_clients"] == 2
    assert payload["active_clients"] == 0  # no systemctl
    assert payload["total_leads_7d"] == 3
    assert payload["total_leads_30d"] == 3
    assert payload["approvals_pending"] == 1
    assert payload["mutations_24h"] == 4


# ---------------------------------------------------------------------------
# Integration: shellout to status.py (skipped if script missing or python
# subprocess unavailable — typical in restricted CI).
# ---------------------------------------------------------------------------


def test_status_shellout_smoke(tmp_path):
    if not stats._STATUS_SCRIPT.is_file():
        pytest.skip("status.py not present in this checkout")
    root = tmp_path / "profiles"
    _write_minimal_config(root / "alpha", slug="alpha")
    _write_audit_rows(
        root / "alpha",
        [
            _row(
                id_="z1",
                skill="content-publisher",
                action="publish",
                ts_epoch=time.time() - 60,
            ),
        ],
    )

    payload = stats.compute_client_stats("alpha", root=root)
    # Whatever status.py emits, our additions must be present.
    assert payload["slug"] == "alpha"
    assert "leads_7d" in payload
    assert "recent_publishes_30d" in payload
