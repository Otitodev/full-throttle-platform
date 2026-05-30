"""Admin (operator) API routes.

These are NOT app-level authenticated — Caddy applies basicauth at the edge,
and the aggregator only binds 127.0.0.1 so they're unreachable any other way.
``app.py``'s startup refuses to launch on a non-loopback host as a safety rail.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from . import audit as audit_mod
from . import config
from . import profiles as profiles_mod
from . import stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Headline tiles + client list
# ---------------------------------------------------------------------------


@router.get("/platform/stats")
def platform_stats() -> dict:
    return stats.compute_platform_stats()


@router.get("/clients")
def list_clients() -> list[dict]:
    return [m.model_dump() for m in profiles_mod.discover_profiles()]


@router.get("/clients/{slug}")
def client_detail(slug: str) -> dict:
    meta = profiles_mod.get_profile(slug)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown slug")
    payload = stats.compute_client_stats(slug)
    payload["meta"] = meta.model_dump()
    return payload


# ---------------------------------------------------------------------------
# Audit / approvals
# ---------------------------------------------------------------------------


@router.get("/approvals")
def list_pending_approvals(slug: Optional[str] = None) -> list[dict]:
    return [r.model_dump() for r in audit_mod.get_pending_approvals(slug=slug)]


@router.get("/audit")
def list_audit(
    slug: Optional[str] = None,
    skill: Optional[str] = None,
    action: Optional[str] = None,
    since: Optional[float] = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    rows = audit_mod.get_audit(
        slug=slug, skill=skill, action=action, since=since, limit=limit
    )
    return [r.model_dump() for r in rows]


# ---------------------------------------------------------------------------
# Leads — PII redaction (default-on, audited unredact)
# ---------------------------------------------------------------------------

_PHONE_RX = re.compile(r"(\+?\d[\d\-\s().]{4,})")


def _redact_phone(s: str) -> str:
    """Return ``"***-***-1234"`` keeping only the last 4 digits."""
    digits = re.sub(r"\D", "", s)
    if len(digits) <= 4:
        return "***"
    return f"***-***-{digits[-4:]}"


def _redact_email(s: str) -> str:
    """Return ``"***@<domain>"`` keeping the domain only."""
    if "@" not in s:
        return "***"
    _, _, dom = s.partition("@")
    return f"***@{dom}" if dom else "***"


def _redact_target(target: str) -> str:
    """Audit ``target`` values look like ``sms:+1...`` or ``email:foo@x`` or
    sometimes a bare phone/email; redact whichever shape we got.
    """
    if not target:
        return ""
    if target.startswith("sms:"):
        return "sms:" + _redact_phone(target[4:])
    if target.startswith("email:"):
        return "email:" + _redact_email(target[6:])
    if "@" in target:
        return _redact_email(target)
    if _PHONE_RX.fullmatch(target):
        return _redact_phone(target)
    return target


def _append_platform_audit(action: str, target: str, status_: str = "ok") -> None:
    """Write one row to the platform-wide audit log (separate from per-client)."""
    config.PLATFORM_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": "dashboard",
        "action": action,
        "target": target,
        "status": status_,
    }
    with config.PLATFORM_AUDIT_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


@router.get("/leads")
def list_leads(
    slug: Optional[str] = None,
    unredact: int = Query(default=0, ge=0, le=1),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    rows = audit_mod.get_audit(
        slug=slug,
        skill="lead-response",
        action="lead_first_touch",
        limit=limit,
    )
    out: list[dict] = []
    for r in rows:
        d = r.model_dump()
        if not unredact:
            d["target"] = _redact_target(d.get("target") or "")
        out.append(d)

    if unredact:
        _append_platform_audit(
            action="unredact_leads", target=f"slug={slug or '*'}", status_="ok"
        )
    return out
