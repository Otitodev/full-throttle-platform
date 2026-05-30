import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { utcClock } from "../lib/format";
import { Card } from "./ui/Card";

/**
 * Compact, mobile-friendly version of the admin AuditTrail — the owner's
 * "what has the agent done for me" stream.
 */
export function ActivityFeed() {
  const fetcher = useCallback(() => api.activity(50), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const rows = data ?? [];
  const hint =
    error ? <span className="text-err">error</span> : "live";

  return (
    <Card>
      <Card.Header title="Activity" hint={hint} />
      <Card.Body className="!py-0">
        {loading && rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">…</div>
        ) : rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">
            no activity yet
          </div>
        ) : (
          rows.map((row) => <ActivityRow key={row.id} row={row} />)
        )}
      </Card.Body>
    </Card>
  );
}

function ActivityRow({ row }: { row: AuditEntry }) {
  return (
    <div className="flex items-center gap-2.5 border-b border-mid/[0.03] py-2 text-[0.75rem] last:border-b-0">
      <span className="min-w-[3rem] font-mono text-[0.58rem] tracking-wider opacity-40">
        {utcClock(row.ts)}
      </span>
      <span className="min-w-0 flex-1 truncate">
        {row.action}
        {row.target ? <span className="opacity-50"> · {row.target}</span> : null}
      </span>
      <span className="whitespace-nowrap rounded-[calc(var(--radius-card)*0.4)] border border-mid/8 px-1.5 py-[0.08rem] font-mono text-[0.55rem] uppercase tracking-wider opacity-55">
        {tagFromSkill(row.skill)}
      </span>
    </div>
  );
}

function tagFromSkill(skill: string): string {
  // Tightened tags for mobile column.
  if (skill === "lead-response") return "LEAD";
  if (skill === "content-publisher") return "CONTENT";
  if (skill === "social-scheduler") return "SOCIAL";
  if (skill === "review-automation") return "REVIEWS";
  if (skill === "governance") return "GOV";
  return skill.toUpperCase();
}
