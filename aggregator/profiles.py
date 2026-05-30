"""Profile discovery — scan ``FT_PROFILES_ROOT`` and expose per-client metadata.

Plan §0.2. One read of ``config.yaml`` + a short read-only burst against
``state.db`` per profile per refresh, plus a 5-second-cached ``systemctl is-active``
check. We intentionally use synchronous ``sqlite3`` (not aiosqlite) — the per-call
work is a single ``COUNT(*)`` + ``MAX(started_at)`` + token sum, and threadpool
dispatch from FastAPI is enough; async would add machinery without measurable
benefit at this load.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict

from . import config

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ProfileMeta(BaseModel):
    """One per Hermes profile under ``FT_PROFILES_ROOT``."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    display_name: str
    site_type: str  # "augment" | "greenfield" | "unknown"
    adapter: str  # "manual" | "wordpress-rest" | "astro-git" | "proxy-subdir" | …
    port: Optional[int]  # webhook port from platforms.webhook.extra.port
    brand_voice: Optional[str] = None
    services: list[str] = []
    gateway_active: bool = False
    session_count: int = 0
    last_active: Optional[float] = None  # epoch seconds; None if no sessions
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Gateway health cache (5 s TTL, plan §0.2)
# ---------------------------------------------------------------------------

_HEALTH_CACHE: dict[str, tuple[float, bool]] = {}


def _systemctl_is_active(unit: str) -> bool:
    """Return True iff systemd reports the unit as ``active``.

    Cached for ``config.GATEWAY_HEALTH_TTL_S`` seconds per unit. Failures
    (systemctl missing, non-zero exit) are treated as inactive — this runs
    in dev environments too where systemd isn't installed.
    """
    now = time.monotonic()
    cached = _HEALTH_CACHE.get(unit)
    if cached and now - cached[0] < config.GATEWAY_HEALTH_TTL_S:
        return cached[1]

    if shutil.which("systemctl") is None:
        active = False
    else:
        try:
            out = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=2,
            )
            active = out.stdout.strip() == "active"
        except (subprocess.TimeoutExpired, OSError):
            active = False

    _HEALTH_CACHE[unit] = (now, active)
    return active


def _clear_health_cache() -> None:
    """Test hook — wipe the systemctl cache between cases."""
    _HEALTH_CACHE.clear()


# ---------------------------------------------------------------------------
# Per-profile reads
# ---------------------------------------------------------------------------


def _read_config_yaml(profile_dir: Path) -> dict:
    f = profile_dir / "config.yaml"
    if not f.is_file():
        return {}
    try:
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return {}


def _read_state_db(profile_dir: Path) -> dict:
    """Return ``{session_count, last_active, input/output_tokens, cost_usd}``.

    Opens the SQLite file with a read-only URI (``mode=ro``) and pins
    ``PRAGMA query_only=1`` to enforce no writes even if our SQL has a typo.
    Returns zeros if the DB is missing or unreadable — new profiles have no
    state.db until the agent runs once.
    """
    db = profile_dir / "state.db"
    empty = {
        "session_count": 0,
        "last_active": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0.0,
    }
    if not db.is_file():
        return empty

    # WAL means the writer keeps writing; the reader sees a consistent snapshot.
    uri = f"file:{db}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
    except sqlite3.Error:
        return empty
    try:
        conn.execute("PRAGMA query_only=1")
        cur = conn.execute(
            "SELECT COUNT(*), MAX(started_at), "
            "COALESCE(SUM(input_tokens), 0), "
            "COALESCE(SUM(output_tokens), 0), "
            "COALESCE(SUM(actual_cost_usd), 0.0) "
            "FROM sessions"
        )
        row = cur.fetchone() or (0, None, 0, 0, 0.0)
        return {
            "session_count": int(row[0] or 0),
            "last_active": float(row[1]) if row[1] is not None else None,
            "total_input_tokens": int(row[2] or 0),
            "total_output_tokens": int(row[3] or 0),
            "total_cost_usd": float(row[4] or 0.0),
        }
    except sqlite3.Error:
        return empty
    finally:
        conn.close()


def _extract_port(cfg: dict) -> Optional[int]:
    try:
        port = cfg["platforms"]["webhook"]["extra"]["port"]
    except (KeyError, TypeError):
        return None
    try:
        return int(port)
    except (TypeError, ValueError):
        return None


def _extract_adapter(cfg: dict) -> str:
    pub = cfg.get("publishing") or {}
    return str(pub.get("adapter") or "unknown")


def _build_meta(profile_dir: Path) -> ProfileMeta:
    slug = profile_dir.name
    cfg = _read_config_yaml(profile_dir)
    client = cfg.get("client") or {}
    display_name = (
        client.get("display_name")
        or client.get("business_name")
        or slug
    )
    services = client.get("services") or []
    if not isinstance(services, list):
        services = []
    state = _read_state_db(profile_dir)
    return ProfileMeta(
        slug=slug,
        display_name=str(display_name),
        site_type=str(cfg.get("site_type") or "unknown"),
        adapter=_extract_adapter(cfg),
        port=_extract_port(cfg),
        brand_voice=client.get("brand_voice"),
        services=[str(s) for s in services],
        gateway_active=_systemctl_is_active(f"hermes-gateway@{slug}.service"),
        session_count=state["session_count"],
        last_active=state["last_active"],
        total_input_tokens=state["total_input_tokens"],
        total_output_tokens=state["total_output_tokens"],
        total_cost_usd=state["total_cost_usd"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_profiles(root: Optional[Path] = None) -> list[ProfileMeta]:
    """Scan ``root`` (default ``config.PROFILES_ROOT``) and return one
    ``ProfileMeta`` per profile directory.

    Skips dotfiles and non-directories. Order is slug-ascending so the UI gets a
    stable list.
    """
    base = root if root is not None else config.PROFILES_ROOT
    if not base.is_dir():
        return []
    metas: list[ProfileMeta] = []
    for child in sorted(base.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        metas.append(_build_meta(child))
    return metas


def get_profile(slug: str, root: Optional[Path] = None) -> Optional[ProfileMeta]:
    """Return one profile's metadata, or None if the slug isn't a profile dir."""
    base = root if root is not None else config.PROFILES_ROOT
    target = base / slug
    if not target.is_dir() or target.name.startswith("."):
        return None
    return _build_meta(target)
