"""Stats engine — thin wrapper around the governance skill's ``status.py``.

We deliberately do NOT reimplement what
``skills/governance/scripts/status.py`` already computes (timeline, counts by
action/status, approval queue, cron jobs). Instead we shell out under each
profile's ``HERMES_HOME``, parse the JSON, and bolt on the dashboard-only
fields (recent leads, recent publishes, avg first-response, …).

Why shell out instead of importing: the skill is supposed to be Hermes-agnostic
and ships independently — pinning the audit semantics there means any future
schema or counting change flows through here automatically, with no parallel
code path to keep in sync.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import audit as audit_mod
from . import config
from . import profiles as profiles_mod

# Resolved at import time. The skill scripts live next to the platform repo at
# `<repo_root>/skills/governance/scripts/`. The aggregator package lives at
# `<repo_root>/aggregator/`, so the skill is one level up + over.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATUS_SCRIPT = _REPO_ROOT / "skills" / "governance" / "scripts" / "status.py"

_SECONDS_PER_DAY = 86_400


# ---------------------------------------------------------------------------
# governance/status.py shellout
# ---------------------------------------------------------------------------


def _run_status_for_profile(profile_dir: Path, n: int = 50) -> dict:
    """Call ``status.py --json --state-dir <profile>/governance/`` under that
    profile's ``HERMES_HOME`` and return the parsed JSON.

    Failures (script missing, non-zero exit, malformed JSON) return an empty
    dict so the dashboard degrades gracefully instead of 500-ing.
    """
    if not _STATUS_SCRIPT.is_file():
        return {}
    gov = profile_dir / "governance"
    env = os.environ.copy()
    env["HERMES_HOME"] = str(profile_dir)
    try:
        out = subprocess.run(
            [
                sys.executable,
                str(_STATUS_SCRIPT),
                "--json",
                "--state-dir",
                str(gov),
                "--n",
                str(n),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Dashboard-only enrichments (computed from audit log)
# ---------------------------------------------------------------------------


def _leads_in_window(slug: str, root: Path, days: int) -> int:
    """Count distinct leads handled in the last ``days`` days.

    The lead-response skill emits ``action=lead_first_touch`` once per new lead
    (deduped — duplicate retries don't append). That's the cleanest "new lead"
    signal in the audit log; ``crm_sync`` rows would double-count.
    """
    since = audit_mod.now_epoch() - days * _SECONDS_PER_DAY
    rows = audit_mod.get_audit(
        slug=slug,
        skill="lead-response",
        action="lead_first_touch",
        since=since,
        root=root,
    )
    return len(rows)


def _recent_publishes(slug: str, root: Path, days: int = 30) -> int:
    since = audit_mod.now_epoch() - days * _SECONDS_PER_DAY
    rows = audit_mod.get_audit(
        slug=slug,
        skill="content-publisher",
        action="publish",
        since=since,
        root=root,
    )
    return sum(1 for r in rows if (r.status or "ok") == "ok")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_client_stats(slug: str, root: Optional[Path] = None) -> dict:
    """Per-client stats payload for ``/api/admin/clients/{slug}`` and
    ``/api/client/{slug}/stats``.

    Shape: whatever ``status.py --json`` returned + these dashboard-only keys:
    ``slug``, ``leads_7d``, ``leads_30d``, ``recent_publishes_30d``,
    ``mutations_24h``, ``approvals_pending``.
    """
    base = root if root is not None else config.PROFILES_ROOT
    profile_dir = base / slug
    if not profile_dir.is_dir():
        return {"slug": slug, "ok": False, "error": "profile not found"}

    payload = _run_status_for_profile(profile_dir)
    payload["slug"] = slug
    payload["leads_7d"] = _leads_in_window(slug, base, 7)
    payload["leads_30d"] = _leads_in_window(slug, base, 30)
    payload["recent_publishes_30d"] = _recent_publishes(slug, base)
    payload["mutations_24h"] = len(
        audit_mod.get_audit(
            slug=slug,
            since=audit_mod.now_epoch() - _SECONDS_PER_DAY,
            root=base,
        )
    )
    payload["approvals_pending"] = len(
        audit_mod.get_pending_approvals(slug=slug, root=base)
    )
    return payload


def compute_platform_stats(root: Optional[Path] = None) -> dict:
    """Aggregate across every profile under ``root``.

    Powers the operator-dashboard headline tiles. ``active_clients`` counts
    profiles whose ``hermes-gateway@<slug>.service`` is currently active.
    """
    base = root if root is not None else config.PROFILES_ROOT
    metas = profiles_mod.discover_profiles(base)

    active_clients = sum(1 for m in metas if m.gateway_active)
    total_clients = len(metas)

    total_leads_7d = 0
    total_leads_30d = 0
    approvals_pending = 0
    mutations_24h = 0
    for m in metas:
        total_leads_7d += _leads_in_window(m.slug, base, 7)
        total_leads_30d += _leads_in_window(m.slug, base, 30)
        approvals_pending += len(
            audit_mod.get_pending_approvals(slug=m.slug, root=base)
        )
        mutations_24h += len(
            audit_mod.get_audit(
                slug=m.slug,
                since=audit_mod.now_epoch() - _SECONDS_PER_DAY,
                root=base,
            )
        )

    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "total_leads_7d": total_leads_7d,
        "total_leads_30d": total_leads_30d,
        "approvals_pending": approvals_pending,
        "mutations_24h": mutations_24h,
    }
