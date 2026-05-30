"""Audit log aggregator.

Reads ``<profile>/governance/audit.jsonl`` from every profile under
``FT_PROFILES_ROOT``, caches each file's parsed rows by ``(path, mtime_ns)`` so
unchanged logs are not re-parsed, and exposes a small filter API for the routes.

Schema (per ``skills/governance/scripts/audit.py``):

    {
        "id":              "<12-hex>",
        "ts":              "<ISO-8601 UTC>",
        "skill":           "<lead-response|content-publisher|...|governance>",
        "action":          "<intake|publish|revert|plan:<intent>|...>",
        "target":          "<string>",
        "status":          "<ok|error|pending|...>",
        "rollback_ref":    "<opt>",
        "approval_state":  "<pending|approved|none|...>",
        "repo":            "<opt>"
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from . import config


class AuditEntry(BaseModel):
    """One row from a profile's audit.jsonl plus a ``slug`` provenance field."""

    model_config = ConfigDict(extra="allow")

    id: str
    ts: str  # ISO 8601 UTC
    skill: str
    action: str
    target: Optional[str] = None
    status: Optional[str] = None
    rollback_ref: Optional[str] = None
    approval_state: Optional[str] = None
    repo: Optional[str] = None
    # Injected by the aggregator so callers know which client the row came from.
    slug: str = ""


# ---------------------------------------------------------------------------
# Per-file mtime cache
# ---------------------------------------------------------------------------

# key: absolute Path  →  (mtime_ns, parsed_rows)
_AUDIT_CACHE: dict[Path, tuple[int, list[AuditEntry]]] = {}


def _read_one(path: Path, slug: str) -> list[AuditEntry]:
    """Return parsed rows for one audit.jsonl, using the mtime cache."""
    if not path.is_file():
        return []
    mtime_ns = path.stat().st_mtime_ns
    cached = _AUDIT_CACHE.get(path)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    rows: list[AuditEntry] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Malformed line — skip but keep going (status.py does the same).
            continue
        obj.setdefault("slug", slug)
        try:
            rows.append(AuditEntry.model_validate(obj))
        except Exception:
            # Schema drift — skip rather than crash the whole dashboard.
            continue

    _AUDIT_CACHE[path] = (mtime_ns, rows)
    return rows


def _clear_audit_cache() -> None:
    """Test hook — drop the per-file mtime cache."""
    _AUDIT_CACHE.clear()


def _audit_path(profiles_root: Path, slug: str) -> Path:
    return profiles_root / slug / "governance" / "audit.jsonl"


def _list_slugs(profiles_root: Path) -> list[str]:
    if not profiles_root.is_dir():
        return []
    return sorted(
        p.name
        for p in profiles_root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def _parse_ts(ts: str) -> float:
    """Best-effort ISO-8601 → epoch seconds, with safe fallback for sort stability."""
    try:
        # `fromisoformat` handles e.g. "2026-05-30T11:19:23.123456+00:00".
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Public query API
# ---------------------------------------------------------------------------


def get_audit(
    *,
    slug: Optional[str] = None,
    skill: Optional[str] = None,
    action: Optional[str] = None,
    approval_state: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: Optional[int] = None,
    root: Optional[Path] = None,
) -> list[AuditEntry]:
    """Cross-profile audit query, newest first.

    ``since`` / ``until`` are epoch seconds (inclusive lower bound, exclusive upper
    bound). ``limit`` clips after sorting + filtering. All filters compose.
    """
    base = root if root is not None else config.PROFILES_ROOT
    slugs = [slug] if slug else _list_slugs(base)

    merged: list[AuditEntry] = []
    for s in slugs:
        merged.extend(_read_one(_audit_path(base, s), s))

    if skill is not None:
        merged = [r for r in merged if r.skill == skill]
    if action is not None:
        merged = [r for r in merged if r.action == action]
    if approval_state is not None:
        merged = [r for r in merged if (r.approval_state or "") == approval_state]
    if since is not None or until is not None:
        lo = since if since is not None else float("-inf")
        hi = until if until is not None else float("inf")
        merged = [r for r in merged if lo <= _parse_ts(r.ts) < hi]

    merged.sort(key=lambda r: _parse_ts(r.ts), reverse=True)
    if limit is not None and limit >= 0:
        merged = merged[:limit]
    return merged


def get_pending_approvals(
    slug: Optional[str] = None,
    root: Optional[Path] = None,
) -> list[AuditEntry]:
    """All rows where ``approval_state == "pending"``, newest first."""
    return get_audit(slug=slug, approval_state="pending", root=root)


def recent_by_skill(
    skill: str,
    slug: Optional[str] = None,
    limit: int = 20,
    root: Optional[Path] = None,
) -> list[AuditEntry]:
    """N most-recent rows for one skill, optionally pinned to a single slug."""
    return get_audit(skill=skill, slug=slug, limit=limit, root=root)


def now_epoch() -> float:
    """Helper for tests + routes — UTC now as epoch seconds."""
    return datetime.now(timezone.utc).timestamp()
