"""Unit tests for aggregator.audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aggregator import audit


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_audit(profile_dir: Path, rows: list[dict]) -> Path:
    gov = profile_dir / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    p = gov / "audit.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


def _row(
    *,
    id_: str,
    ts: str,
    skill: str = "lead-response",
    action: str = "intake",
    status: str = "ok",
    approval_state: str = "none",
) -> dict:
    return {
        "id": id_,
        "ts": ts,
        "skill": skill,
        "action": action,
        "target": f"target-{id_}",
        "status": status,
        "approval_state": approval_state,
    }


@pytest.fixture(autouse=True)
def _reset_cache():
    audit._clear_audit_cache()
    yield
    audit._clear_audit_cache()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_merge_across_profiles_sorted_desc(tmp_path):
    root = tmp_path / "profiles"
    _write_audit(
        root / "alpha",
        [
            _row(id_="a1", ts="2026-05-01T10:00:00+00:00"),
            _row(id_="a2", ts="2026-05-03T10:00:00+00:00"),
        ],
    )
    _write_audit(
        root / "beta",
        [
            _row(id_="b1", ts="2026-05-02T10:00:00+00:00"),
        ],
    )

    rows = audit.get_audit(root=root)
    assert [r.id for r in rows] == ["a2", "b1", "a1"]
    assert rows[0].slug == "alpha"
    assert rows[1].slug == "beta"


def test_filter_by_slug_skill_action(tmp_path):
    root = tmp_path / "profiles"
    _write_audit(
        root / "alpha",
        [
            _row(id_="a1", ts="2026-05-01T10:00:00+00:00", skill="lead-response"),
            _row(
                id_="a2",
                ts="2026-05-02T10:00:00+00:00",
                skill="content-publisher",
                action="publish",
            ),
        ],
    )
    _write_audit(
        root / "beta",
        [_row(id_="b1", ts="2026-05-03T10:00:00+00:00", skill="lead-response")],
    )

    only_alpha = audit.get_audit(slug="alpha", root=root)
    assert {r.id for r in only_alpha} == {"a1", "a2"}

    only_publish = audit.get_audit(skill="content-publisher", root=root)
    assert {r.id for r in only_publish} == {"a2"}

    intake = audit.get_audit(action="intake", root=root)
    assert {r.id for r in intake} == {"a1", "b1"}


def test_filter_by_time_range(tmp_path):
    root = tmp_path / "profiles"
    _write_audit(
        root / "alpha",
        [
            _row(id_="old", ts="2026-04-01T10:00:00+00:00"),
            _row(id_="mid", ts="2026-05-15T10:00:00+00:00"),
            _row(id_="new", ts="2026-06-01T10:00:00+00:00"),
        ],
    )

    # since 2026-05-01, until 2026-06-01 (exclusive)
    rows = audit.get_audit(
        root=root,
        since=audit._parse_ts("2026-05-01T00:00:00+00:00"),
        until=audit._parse_ts("2026-06-01T00:00:00+00:00"),
    )
    assert [r.id for r in rows] == ["mid"]


def test_pending_approvals_helper(tmp_path):
    root = tmp_path / "profiles"
    _write_audit(
        root / "alpha",
        [
            _row(id_="a1", ts="2026-05-01T10:00:00+00:00", approval_state="approved"),
            _row(id_="a2", ts="2026-05-02T10:00:00+00:00", approval_state="pending"),
        ],
    )
    _write_audit(
        root / "beta",
        [_row(id_="b1", ts="2026-05-03T10:00:00+00:00", approval_state="pending")],
    )

    rows = audit.get_pending_approvals(root=root)
    assert {r.id for r in rows} == {"a2", "b1"}
    assert all(r.approval_state == "pending" for r in rows)


def test_recent_by_skill_respects_limit(tmp_path):
    root = tmp_path / "profiles"
    _write_audit(
        root / "alpha",
        [
            _row(id_=f"l{i}", ts=f"2026-05-{i:02d}T10:00:00+00:00")
            for i in range(1, 6)
        ],
    )

    rows = audit.recent_by_skill("lead-response", limit=3, root=root)
    assert len(rows) == 3
    assert [r.id for r in rows] == ["l5", "l4", "l3"]


def test_cache_hit_avoids_reread(tmp_path, monkeypatch):
    root = tmp_path / "profiles"
    path = _write_audit(
        root / "alpha", [_row(id_="a1", ts="2026-05-01T10:00:00+00:00")]
    )

    # First call populates the cache.
    audit.get_audit(slug="alpha", root=root)

    reads = {"n": 0}
    original_read = Path.read_text

    def _counting_read(self, *args, **kwargs):
        if self == path:
            reads["n"] += 1
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read)

    # Second call with no mtime change: no re-read.
    audit.get_audit(slug="alpha", root=root)
    assert reads["n"] == 0


def test_malformed_lines_are_skipped(tmp_path):
    gov = tmp_path / "profiles" / "alpha" / "governance"
    gov.mkdir(parents=True)
    (gov / "audit.jsonl").write_text(
        "not-json\n"
        + json.dumps(_row(id_="ok", ts="2026-05-01T10:00:00+00:00"))
        + "\n"
        + "{partial\n",
        encoding="utf-8",
    )

    rows = audit.get_audit(root=tmp_path / "profiles")
    assert [r.id for r in rows] == ["ok"]
