import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { telFromTarget, timeAgo } from "../lib/format";
import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";

/**
 * Recent leads (audit rows from lead-response · lead_first_touch).
 * On mobile, the target phone is rendered as a tap-to-call link.
 */
export function LeadList() {
  const fetcher = useCallback(() => api.leads(20), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const rows = data ?? [];
  const hint =
    error
      ? <span className="text-err">error</span>
      : `${rows.length} recent`;

  return (
    <Card>
      <Card.Header title="Inbound Leads" hint={hint} />
      <Card.Body className="!py-0">
        {loading && rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">…</div>
        ) : rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">
            no leads yet
          </div>
        ) : (
          rows.map((row) => <LeadRow key={row.id} row={row} />)
        )}
      </Card.Body>
    </Card>
  );
}

function LeadRow({ row }: { row: AuditEntry }) {
  const tel = telFromTarget(row.target);
  const tone = pickTone(row);
  const tag = pickTag(row);
  const display = displayTarget(row.target);

  return (
    <div className="flex items-center justify-between gap-3 border-b border-mid/4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="truncate text-[0.82rem] font-semibold">
          {tel ? (
            <a href={tel} className="underline decoration-mid/30 underline-offset-2">
              {display}
            </a>
          ) : (
            display
          )}
        </div>
        <div className="truncate text-[0.7rem] opacity-50">
          {row.skill}
          {row.action !== "lead_first_touch" ? ` · ${row.action}` : ""}
          {row.status && row.status !== "ok" ? ` · ${row.status}` : ""}
          {" · "}
          {timeAgo(row.ts)}
        </div>
      </div>
      <Badge tone={tone}>{tag}</Badge>
    </div>
  );
}

function displayTarget(target: string | null | undefined): string {
  if (!target) return "(unknown)";
  if (target.startsWith("sms:")) return target.slice(4);
  if (target.startsWith("email:")) return target.slice(6);
  return target;
}

function pickTone(row: AuditEntry): "filled-ok" | "filled-warn" | "filled-neutral" {
  if (row.status === "error") return "filled-warn";
  if (row.approval_state === "pending") return "filled-warn";
  if (row.action === "lead_first_touch") return "filled-ok";
  return "filled-neutral";
}

function pickTag(row: AuditEntry): string {
  if (row.action === "lead_first_touch") return "NEW";
  if (row.action === "crm_sync") return "SYNCED";
  if (row.approval_state === "pending") return "PENDING";
  return row.action.replace(/_/g, " ").toUpperCase();
}
