import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Card } from "./ui/Card";

/**
 * Pending approvals card.
 *
 * v1: READ-ONLY. Owners approve via SMS clarify (the agent texts them and
 * waits for "yes" / "no"). Building approve/deny buttons here would split
 * the source of truth and is deferred to a future task.
 */
export function ApprovalCards() {
  const fetcher = useCallback(() => api.approvals(), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const rows = data ?? [];
  const hint =
    error
      ? <span className="text-err">error</span>
      : `${rows.length} pending`;

  return (
    <Card>
      <Card.Header title="Needs Your Approval" hint={hint} />
      <Card.Body className="!py-0">
        {loading && rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">…</div>
        ) : rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">
            nothing waiting — you're clear
          </div>
        ) : (
          rows.map((row) => <ApprovalRow key={row.id} row={row} />)
        )}
        {rows.length > 0 ? (
          <div className="border-t border-mid/4 py-2 text-center font-mono text-[0.55rem] uppercase tracking-wider opacity-40">
            approve by replying to the SMS we sent you
          </div>
        ) : null}
      </Card.Body>
    </Card>
  );
}

function ApprovalRow({ row }: { row: AuditEntry }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-mid/4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="truncate text-[0.82rem] font-semibold">{row.action}</div>
        <div className="truncate text-[0.7rem] opacity-50">
          {row.skill}
          {row.target ? ` · ${row.target}` : ""}
          {" · "}
          {timeAgo(row.ts)}
        </div>
      </div>
      <span className="whitespace-nowrap rounded-[calc(var(--radius-card)*0.4)] border border-warn/30 px-2 py-1 font-mono text-[0.58rem] uppercase tracking-wider text-warn">
        PENDING
      </span>
    </div>
  );
}
