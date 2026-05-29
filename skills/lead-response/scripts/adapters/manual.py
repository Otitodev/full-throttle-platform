"""Manual CRM adapter — records leads to a file the operator imports.

The demo-ready default before a real CRM (Jobber/ServiceTitan/HCP) is wired.
Appends each lead to leads_crm.jsonl; dedups on lead id so replays don't create
duplicate rows. Same interface as the jobber adapter, so flipping later is a
config change, not code.
"""

from __future__ import annotations

import json
from pathlib import Path

from adapters.base import CRMAdapter, Lead


class ManualAdapter(CRMAdapter):
    name = "manual"

    def __init__(self, crm_dir: str | None = None):
        if not crm_dir:
            raise ValueError("manual adapter requires a crm dir (set by --crm-dir or state dir)")
        self.crm_dir = Path(crm_dir).expanduser()

    def sync_lead(self, lead: Lead) -> dict:
        self.crm_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.crm_dir / "leads_crm.jsonl"

        # Dedup on lead id (idempotent).
        if out_path.is_file():
            for line in out_path.read_text(encoding="utf-8").splitlines():
                try:
                    if json.loads(line).get("id") == lead.id and lead.id:
                        return {"adapter": self.name, "lead_id": lead.id, "duplicate": True, "written_to": str(out_path)}
                except json.JSONDecodeError:
                    continue

        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(lead.to_dict()) + "\n")
        return {"adapter": self.name, "lead_id": lead.id, "duplicate": False, "written_to": str(out_path)}
