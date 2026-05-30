import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, usePoll, type ProfileMeta } from "../lib/api";
import { timeAgo, usd } from "../lib/format";
import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";
import { Dot } from "./ui/Dot";

type SortKey = "name" | "sessions" | "last_active" | "cost" | "gateway";

/**
 * Sortable client list. Polls /api/admin/clients every 30 s.
 *
 * Per-client leads/response/reviews/content columns from the mockup are
 * placeholders until the aggregator exposes per-slug enrichments on this
 * endpoint (today they live behind /api/admin/clients/{slug}, which is N+1
 * for a list view).
 */
export function ClientTable() {
  const fetcher = useCallback(() => api.clients(), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "last_active",
    dir: "desc",
  });
  const navigate = useNavigate();

  const rows = useMemo(() => sortRows(data ?? [], sort), [data, sort]);

  const hint =
    error
      ? <span className="text-err">error · last good shown</span>
      : `${rows.length} client${rows.length === 1 ? "" : "s"}`;

  return (
    <Card>
      <Card.Header title="Clients" hint={hint} />
      <Card.Body className="!px-0">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <ColHead label="Client" sortKey="name" sort={sort} setSort={setSort} />
              <ColHead label="Sessions" sortKey="sessions" sort={sort} setSort={setSort} align="right" />
              <ColHead label="Last Active" sortKey="last_active" sort={sort} setSort={setSort} align="right" />
              <ColHead label="Cost" sortKey="cost" sort={sort} setSort={setSort} align="right" />
              <ColHead label="Gateway" sortKey="gateway" sort={sort} setSort={setSort} align="right" />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-mid/40">
                  no clients yet
                </td>
              </tr>
            ) : null}
            {rows.map((c) => (
              <tr
                key={c.slug}
                onClick={() => navigate(`/clients/${encodeURIComponent(c.slug)}`)}
                className="cursor-pointer border-b border-mid/4 hover:bg-mid/[0.02]"
              >
                <td className="px-3 py-2.5 text-[0.78rem]">
                  <div className="flex items-center gap-2 font-semibold">
                    <Dot tone={healthTone(c)} />
                    {c.display_name || c.slug}
                  </div>
                  <div className="ml-3.5 font-mono text-[0.6rem] opacity-40">
                    {c.slug} · {c.adapter}
                    {c.site_type !== "unknown" ? ` · ${c.site_type}` : ""}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-[0.7rem]">
                  {c.session_count}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-[0.7rem] opacity-70">
                  {timeAgo(c.last_active)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-[0.7rem] opacity-70">
                  {usd(c.total_cost_usd)}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <Badge tone={c.gateway_active ? "ok" : "err"}>
                    {c.gateway_active ? "LIVE" : "OFFLINE"}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card.Body>
    </Card>
  );
}

function ColHead({
  label,
  sortKey,
  sort,
  setSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  sort: { key: SortKey; dir: "asc" | "desc" };
  setSort: (s: { key: SortKey; dir: "asc" | "desc" }) => void;
  align?: "left" | "right";
}) {
  const active = sort.key === sortKey;
  return (
    <th
      onClick={() =>
        setSort({
          key: sortKey,
          dir: active && sort.dir === "desc" ? "asc" : "desc",
        })
      }
      className={
        "cursor-pointer border-b border-mid/8 px-3 py-2 font-mono text-[0.56rem] uppercase tracking-wider opacity-40 select-none hover:opacity-70 " +
        (align === "right" ? "text-right" : "text-left")
      }
    >
      {label}
      {active ? <span className="ml-1">{sort.dir === "desc" ? "↓" : "↑"}</span> : null}
    </th>
  );
}

function healthTone(c: ProfileMeta): "ok" | "warn" | "err" {
  if (!c.gateway_active) return "err";
  if (c.last_active == null) return "warn";
  return "ok";
}

function sortRows(
  rows: ProfileMeta[],
  s: { key: SortKey; dir: "asc" | "desc" },
): ProfileMeta[] {
  const mul = s.dir === "asc" ? 1 : -1;
  const out = [...rows];
  out.sort((a, b) => {
    let cmp = 0;
    switch (s.key) {
      case "name":
        cmp = (a.display_name || a.slug).localeCompare(b.display_name || b.slug);
        break;
      case "sessions":
        cmp = a.session_count - b.session_count;
        break;
      case "last_active":
        cmp = (a.last_active ?? -Infinity) - (b.last_active ?? -Infinity);
        break;
      case "cost":
        cmp = a.total_cost_usd - b.total_cost_usd;
        break;
      case "gateway":
        cmp = Number(a.gateway_active) - Number(b.gateway_active);
        break;
    }
    return cmp * mul;
  });
  return out;
}
