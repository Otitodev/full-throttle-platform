"""Per-client (owner) API routes — Bearer-authenticated against the slug's
``FT_DASHBOARD_TOKEN``. See ``auth.py``.

Auth is enforced inline at each handler (calling
``auth.require_client_token``) rather than via an APIRouter-level dependency —
route-level deps don't see the URL slug until after path parsing, which led to
spurious 422s. Inline is clearer and harder to forget.

Cross-tenant tokens are rejected automatically because the expected token is
read from the URL slug's ``.env``, not the request.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, status

from . import audit as audit_mod
from . import auth as auth_mod
from . import profiles as profiles_mod
from . import stats

router = APIRouter(prefix="/api/client/{slug}", tags=["client"])


def _check(slug: str, authorization: Optional[str]) -> None:
    auth_mod.require_client_token(slug, authorization)


@router.get("/stats")
def client_stats(
    slug: str, authorization: Optional[str] = Header(default=None)
) -> dict:
    _check(slug, authorization)
    meta = profiles_mod.get_profile(slug)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown slug")
    payload = stats.compute_client_stats(slug)
    payload["meta"] = meta.model_dump()
    return payload


@router.get("/leads")
def client_leads(
    slug: str,
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    _check(slug, authorization)
    rows = audit_mod.get_audit(
        slug=slug,
        skill="lead-response",
        action="lead_first_touch",
        limit=limit,
    )
    return [r.model_dump() for r in rows]


@router.get("/content")
def client_content(
    slug: str,
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    _check(slug, authorization)
    rows = audit_mod.get_audit(
        slug=slug,
        skill="content-publisher",
        action="publish",
        limit=limit,
    )
    return [r.model_dump() for r in rows]


@router.get("/activity")
def client_activity(
    slug: str,
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    since: Optional[float] = None,
) -> list[dict]:
    _check(slug, authorization)
    rows = audit_mod.get_audit(slug=slug, since=since, limit=limit)
    return [r.model_dump() for r in rows]


@router.get("/approvals")
def client_approvals(
    slug: str, authorization: Optional[str] = Header(default=None)
) -> list[dict]:
    _check(slug, authorization)
    return [r.model_dump() for r in audit_mod.get_pending_approvals(slug=slug)]
