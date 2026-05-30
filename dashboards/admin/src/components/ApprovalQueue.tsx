import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Card } from "./ui/Card";

/**
 * Pending-approvals sidebar. Polls /api/admin/approvals every 30 s. Read-only
 * in v1 — owners approve via SMS clarify; the dashboard just shows the queue.
 */
export function ApprovalQueue() {
  const fetcher = useCallback(() => api.approvals(), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);
  const items = data ?? [];

  const hint =
    error
      ? <span className="text-err">error</span>
      : `${items.length} pending`;

  return (
    <Card>
      <Card.Header title="Approval Queue" hint={hint} />
      <Card.Body className="!py-0">
        {items.length === 0 && !loading ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">
            queue empty
          </div>
        ) : null}
        {items.map((row) => (
          <QueueRow key={row.id} row={row} />
        ))}
      </Card.Body>
    </Card>
  );
}

function QueueRow({ row }: { row: AuditEntry }) {
  return (
    <div className="flex items-start gap-2.5 border-b border-mid/4 py-2 text-[0.78rem] last:border-b-0">
      <div className="min-w-[4.5rem] pt-0.5 font-mono text-[0.55rem] uppercase tracking-wider opacity-40">
        {row.slug}
      </div>
      <div className="flex-1">
        <strong className="block">{row.action}</strong>
        <span className="text-[0.68rem] opacity-50">
          {row.skill}
          {row.target ? ` · ${row.target}` : ""}
        </span>
      </div>
      <div className="whitespace-nowrap font-mono text-[0.55rem] uppercase tracking-wider opacity-45">
        {timeAgo(row.ts)}
      </div>
    </div>
  );
}
