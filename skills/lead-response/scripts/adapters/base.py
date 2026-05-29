"""CRM adapters — common interface.

A CRMAdapter abstracts *where a lead is recorded* so the skill doesn't care
whether leads go to a manual file the operator imports, Jobber, ServiceTitan, or
Housecall Pro. Mirrors the review/social adapter pattern.

Each adapter implements:
- sync_lead(lead) -> dict   (create/record one lead; idempotent on lead.id)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict


@dataclass
class Lead:
    id: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    message: str = ""
    source: str = ""          # web-form | lsa | referral | …
    created: str = ""         # ISO timestamp
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Lead":
        known = {"id", "name", "phone", "email", "message", "source", "created"}
        return Lead(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")).strip(),
            phone=normalize_phone(d.get("phone", "")),
            email=str(d.get("email", "")).strip().lower(),
            message=str(d.get("message") or d.get("comment") or "").strip(),
            source=str(d.get("source", "")).strip(),
            created=str(d.get("created", "")),
            extra={k: v for k, v in d.items() if k not in known},
        )


class CRMAdapter:
    name = "base"

    def sync_lead(self, lead: Lead) -> dict:
        raise NotImplementedError


def normalize_phone(value) -> str:
    """Strip to digits, keep a leading + if present. Best-effort E.164-ish."""
    s = str(value or "").strip()
    if not s:
        return ""
    plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    return ("+" if plus else "") + digits


def lead_fingerprint(lead: Lead) -> str:
    """Stable id for dedup when the source didn't supply one: phone|email."""
    basis = (lead.phone or "") + "|" + (lead.email or "")
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12] if basis != "|" else ""
