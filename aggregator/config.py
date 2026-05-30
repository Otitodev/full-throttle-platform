"""Aggregator runtime configuration (env-driven)."""

from __future__ import annotations

import os
from pathlib import Path

# Where all Hermes profiles live. NOT HERMES_HOME — that's per-profile.
PROFILES_ROOT = Path(
    os.environ.get("FT_PROFILES_ROOT", "/home/hermes/.hermes/profiles")
)

# The aggregator must ONLY bind loopback. Caddy is the single frontdoor.
BIND_HOST = "127.0.0.1"
BIND_PORT = int(os.environ.get("FT_AGGREGATOR_PORT", "9201"))

# Platform-wide audit log (admin actions like unredact).
# Lives a level up from PROFILES_ROOT.
PLATFORM_AUDIT_PATH = PROFILES_ROOT.parent / "platform-audit.jsonl"

# Cache TTL (seconds) for systemd `is-active` checks. Plan §0.2.
GATEWAY_HEALTH_TTL_S = 5
