"""Jobber CRM adapter — creates a client/request in Jobber for a lead.

Jobber exposes a GraphQL API (OAuth2). This adapter creates a client record (and
optionally a request) so an inbound lead lands in the contractor's pipeline. Only
works once Jobber OAuth is set up (see ../references/crm_setup.md); until then the
skill runs on the `manual` adapter. The HTTP client is imported lazily so the
manual path needs no extra deps.
"""

from __future__ import annotations

import os
from pathlib import Path

from adapters.base import CRMAdapter, Lead

_API_URL = "https://api.getjobber.com/api/graphql"
_API_VERSION = "2023-11-15"

_CREATE_CLIENT = """
mutation CreateClient($input: ClientCreateInput!) {
  clientCreate(input: $input) {
    client { id }
    userErrors { message }
  }
}
""".strip()


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


class JobberAdapter(CRMAdapter):
    name = "jobber"

    def __init__(self, token_path: str | None = None, access_token: str | None = None):
        self.access_token = access_token or os.environ.get("JOBBER_ACCESS_TOKEN", "")
        self.token_path = Path(token_path).expanduser() if token_path else (
            _hermes_home() / "jobber_token.json"
        )

    def _token(self) -> str:
        if self.access_token:
            return self.access_token
        if self.token_path.is_file():
            import json
            return str(json.loads(self.token_path.read_text(encoding="utf-8")).get("access_token", ""))
        raise FileNotFoundError(
            f"no Jobber token (set JOBBER_ACCESS_TOKEN or {self.token_path}) — see references/crm_setup.md"
        )

    def sync_lead(self, lead: Lead) -> dict:
        import requests  # lazy

        first, _, last = lead.name.partition(" ")
        variables = {
            "input": {
                "firstName": first or lead.name or "Lead",
                "lastName": last,
                "emails": [{"address": lead.email}] if lead.email else [],
                "phones": [{"number": lead.phone}] if lead.phone else [],
                "note": f"[{lead.source}] {lead.message}".strip(),
            }
        }
        resp = requests.post(
            _API_URL,
            json={"query": _CREATE_CLIENT, "variables": variables},
            headers={
                "Authorization": f"Bearer {self._token()}",
                "X-JOBBER-GRAPHQL-VERSION": _API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        result = (data.get("data") or {}).get("clientCreate") or {}
        errors = result.get("userErrors") or []
        if errors:
            return {"adapter": self.name, "lead_id": lead.id, "posted": False, "errors": errors}
        return {"adapter": self.name, "lead_id": lead.id, "posted": True,
                "client_id": (result.get("client") or {}).get("id", "")}
