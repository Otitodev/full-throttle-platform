import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { utcClock } from "../lib/format";
import { Card } from "./ui/Card";

/**
 * Cross-profile audit timeline. Polls /api/admin/audit?limit=50 every 30 s.
 */
export function AuditTrail() {
  const fetcher = useCallback(() => api.audit({ limit: 50 }), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);
  const rows = data ?? [];

  const hint =
    error
      ? <span className="text-err">error</span>
      : `last ${rows.length}`;

  return (
    <Card>
      <Card.Header title="Audit Trail" hint={hint} />
      <Card.Body className="!py-0">
        {rows.length === 0 && !loading ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">
            no mutations yet
          </div>
        ) : null}
        {rows.map((row) => (
          <AuditRow key={row.id} row={row} />
        ))}
      </Card.Body>
    </Card>
  );
}

function AuditRow({ row }: { row: AuditEntry }) {
  return (
    <div className="flex items-center gap-2.5 border-b border-mid/[0.03] py-1.5 text-[0.73rem] last:border-b-0">
      <span className="min-w-[3rem] font-mono text-[0.56rem] tracking-wider opacity-40">
        {utcClock(row.ts)}
      </span>
      <span className="min-w-[4rem] font-mono text-[0.55rem] tracking-wider opacity-40">
        {row.slug}
      </span>
      <span className="whitespace-nowrap rounded-[calc(var(--radius-card)*0.35)] border border-mid/7 px-1.5 py-[0.08rem] font-mono text-[0.53rem] uppercase tracking-wider opacity-55">
        {row.skill}
      </span>
      <span className="flex-1 truncate">
        {row.action}
        {row.target ? <span className="opacity-50"> · {row.target}</span> : null}
      </span>
      {row.status && row.status !== "ok" ? (
        <span
          className={
            "font-mono text-[0.55rem] uppercase tracking-wider " +
            (row.status === "error" ? "text-err" : "text-warn")
          }
        >
          {row.status}
        </span>
      ) : null}
    </div>
  );
}
