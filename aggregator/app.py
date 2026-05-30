"""Full Throttle aggregator — FastAPI entrypoint.

Binds 127.0.0.1 only (Caddy is the public frontdoor). Refusing to bind anywhere
else is a deployment-grade safety rail: a stray `0.0.0.0` here would expose every
client's audit log unauthenticated. See plan Phase 0 §0.1.
"""

from __future__ import annotations

import sys

from fastapi import FastAPI

from . import config
from .routes_admin import router as admin_router
from .routes_client import router as client_router

app = FastAPI(title="Full Throttle Aggregator", version="0.1.0")
app.include_router(admin_router)
app.include_router(client_router)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "fullthrottle-aggregator"}


def main() -> None:
    import uvicorn

    if config.BIND_HOST != "127.0.0.1":
        print(
            f"refusing to start: BIND_HOST must be 127.0.0.1, got {config.BIND_HOST!r}",
            file=sys.stderr,
        )
        sys.exit(2)
    uvicorn.run(
        "aggregator.app:app",
        host=config.BIND_HOST,
        port=config.BIND_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
