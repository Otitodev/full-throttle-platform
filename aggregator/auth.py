"""Auth helpers.

Client routes use a per-profile Bearer token (``FT_DASHBOARD_TOKEN`` in the
profile's ``.env``). Admin routes have no app-level check — they rely on Caddy
basicauth + the aggregator's 127.0.0.1-only bind. See plan §0.5.
"""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from fastapi import Header, HTTPException, status

from . import config

_ENV_TOKEN_KEY = "FT_DASHBOARD_TOKEN"


def _load_profile_token(slug: str, root: Optional[Path] = None) -> str:
    """Return the slug's ``FT_DASHBOARD_TOKEN``, or empty string if absent."""
    base = root if root is not None else config.PROFILES_ROOT
    env_path = base / slug / ".env"
    if not env_path.is_file():
        return ""
    values = dotenv_values(env_path)
    return (values.get(_ENV_TOKEN_KEY) or "").strip()


def _parse_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def require_client_token(slug: str, authorization: Optional[str]) -> None:
    """Raise 401 unless ``authorization`` carries the slug's expected Bearer.

    Constant-time comparison so token-length isn't a timing oracle. Cross-tenant
    use (slug A token presented for slug B) is rejected because the lookup is
    keyed on the URL slug, not the token.
    """
    presented = _parse_bearer(authorization)
    expected = _load_profile_token(slug)
    if not presented or not expected or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing dashboard token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# FastAPI dependency factory: bind a route to a slug parameter.
def client_token_dep(slug_param: str = "slug"):
    """Return a FastAPI dependency that enforces the per-slug Bearer.

    Usage:
        @router.get("/api/client/{slug}/stats",
                    dependencies=[Depends(client_token_dep())])
    """
    from fastapi import Request

    async def _dep(
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> None:
        slug = request.path_params.get(slug_param) or ""
        require_client_token(slug, authorization)

    return _dep
