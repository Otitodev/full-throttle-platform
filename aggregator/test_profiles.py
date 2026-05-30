"""Unit tests for aggregator.profiles.

Builds tmp-dir fixtures with two fake profiles, asserts discovery returns both
``ProfileMeta``s with the right slugs + extracted fields, and patches
``shutil.which`` so the ``systemctl is-active`` call is short-circuited (we don't
need systemd in the test).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aggregator import profiles


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_config(profile: Path, *, slug: str, port: int) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "config.yaml").write_text(
        f"""site_type: augment
publishing:
  adapter: manual
client:
  business_name: Test {slug}
  brand_voice: friendly
  services:
    - install
    - repair
platforms:
  webhook:
    enabled: true
    extra:
      port: {port}
      routes:
        lead:
          secret: testsecret
          skills:
            - lead-response
""",
        encoding="utf-8",
    )


def _write_state(profile: Path, *, sessions: int, last_started: float) -> None:
    """Create a state.db with N sessions, the most recent at ``last_started``."""
    db = profile / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                started_at REAL NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                actual_cost_usd REAL DEFAULT 0.0
            )
            """
        )
        for i in range(sessions):
            conn.execute(
                "INSERT INTO sessions(id, source, started_at, input_tokens, "
                "output_tokens, actual_cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
                (f"sess-{i}", "cli", last_started - i, 100, 50, 0.001),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _disable_systemctl(monkeypatch):
    """Force ``_systemctl_is_active`` to return False without shelling out."""
    monkeypatch.setattr(profiles.shutil, "which", lambda _name: None)
    profiles._clear_health_cache()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_discover_returns_one_per_profile(tmp_path):
    root = tmp_path / "profiles"
    _write_config(root / "alpha", slug="alpha", port=8800)
    _write_state(root / "alpha", sessions=3, last_started=1_700_000_000.0)
    _write_config(root / "beta", slug="beta", port=8801)
    # beta has no state.db

    metas = profiles.discover_profiles(root)

    assert [m.slug for m in metas] == ["alpha", "beta"]
    alpha, beta = metas
    assert alpha.display_name == "Test alpha"
    assert alpha.adapter == "manual"
    assert alpha.port == 8800
    assert alpha.brand_voice == "friendly"
    assert alpha.services == ["install", "repair"]
    assert alpha.session_count == 3
    assert alpha.last_active == pytest.approx(1_700_000_000.0)
    assert alpha.total_input_tokens == 300
    assert alpha.total_output_tokens == 150
    assert alpha.total_cost_usd == pytest.approx(0.003)
    assert alpha.gateway_active is False  # systemctl absent in test

    assert beta.session_count == 0
    assert beta.last_active is None
    assert beta.total_cost_usd == 0.0


def test_discover_skips_dotfiles_and_files(tmp_path):
    root = tmp_path / "profiles"
    _write_config(root / "real", slug="real", port=9000)
    (root / ".cache").mkdir()
    (root / "loose-file.txt").write_text("noise", encoding="utf-8")

    metas = profiles.discover_profiles(root)

    assert [m.slug for m in metas] == ["real"]


def test_get_profile_returns_single_or_none(tmp_path):
    root = tmp_path / "profiles"
    _write_config(root / "solo", slug="solo", port=9100)

    found = profiles.get_profile("solo", root)
    assert found is not None
    assert found.slug == "solo"

    missing = profiles.get_profile("ghost", root)
    assert missing is None


def test_missing_root_returns_empty(tmp_path):
    assert profiles.discover_profiles(tmp_path / "does-not-exist") == []


def test_health_cache_avoids_duplicate_systemctl_calls(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(profiles.shutil, "which", lambda _name: "/usr/bin/systemctl")

    class _FakeProc:
        stdout = "active\n"

    def fake_run(cmd, **_kwargs):
        calls.append(cmd[-1])
        return _FakeProc()

    monkeypatch.setattr(profiles.subprocess, "run", fake_run)
    profiles._clear_health_cache()

    # First call: shells out.
    assert profiles._systemctl_is_active("hermes-gateway@x.service") is True
    # Second call within TTL: cached.
    assert profiles._systemctl_is_active("hermes-gateway@x.service") is True
    assert len(calls) == 1
