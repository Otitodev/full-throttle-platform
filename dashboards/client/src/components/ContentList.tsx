import { useCallback } from "react";

import { api, usePoll, type AuditEntry } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Card } from "./ui/Card";

/**
 * Recently published items (audit rows from content-publisher · publish).
 * Clicking a row opens the published URL (target field, when it looks like one).
 */
export function ContentList() {
  const fetcher = useCallback(() => api.content(20), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const rows = data ?? [];
  const hint =
    error
      ? <span className="text-err">error</span>
      : `last ${rows.length}`;

  return (
    <Card>
      <Card.Header title="Recently Published" hint={hint} />
      <Card.Body className="!py-0">
        {loading && rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">…</div>
        ) : rows.length === 0 ? (
          <div className="py-4 text-center text-[0.72rem] text-mid/40">
            nothing published yet
          </div>
        ) : (
          rows.map((row) => <ContentRow key={row.id} row={row} />)
        )}
      </Card.Body>
    </Card>
  );
}

function ContentRow({ row }: { row: AuditEntry }) {
  const url = looksLikeUrl(row.target) ? row.target : null;
  const repo = row.repo;
  const tag = pickTag(row);

  const body = (
    <>
      <div className="min-w-[2.2rem] pt-0.5 font-mono text-[0.58rem] uppercase tracking-wider opacity-40">
        {tag}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[0.78rem] font-semibold">
          {row.action}
          {repo ? <span className="opacity-50"> · {repo}</span> : null}
        </div>
        <div className="truncate font-mono text-[0.65rem] opacity-40">
          {row.target ?? "—"} · {timeAgo(row.ts)}
        </div>
      </div>
    </>
  );

  return url ? (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="flex items-start gap-3 border-b border-mid/4 py-3 hover:bg-mid/[0.02] last:border-b-0"
    >
      {body}
    </a>
  ) : (
    <div className="flex items-start gap-3 border-b border-mid/4 py-3 last:border-b-0">
      {body}
    </div>
  );
}

function looksLikeUrl(s: string | null | undefined): boolean {
  if (!s) return false;
  return /^https?:\/\//i.test(s);
}

function pickTag(row: AuditEntry): string {
  // Cheap heuristics over target / repo until publishers tag rows explicitly.
  const t = (row.target ?? "").toLowerCase();
  const r = (row.repo ?? "").toLowerCase();
  if (t.includes("/blog/") || r.includes("blog")) return "BLOG";
  if (t.includes("business.google") || t.includes("gbp")) return "GBP";
  if (t.includes("instagram") || t.includes("facebook") || t.includes("social"))
    return "SOCIAL";
  if (row.action.includes("review")) return "REPLY";
  return "PUB";
}
