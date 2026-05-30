import { useCallback } from "react";
import { api, usePoll, type PlatformStats } from "../lib/api";

/**
 * Five-tile platform-wide stats row, polling /api/admin/platform/stats
 * every 30 s. Mirrors the mockup's `.agg-row` section.
 */
export function StatsRow() {
  // Stable reference so usePoll's deps don't churn every render.
  const fetcher = useCallback(() => api.platformStats(), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const tiles = renderTiles(data);

  return (
    <div className="mb-6 overflow-hidden rounded-[var(--radius-card)] border border-mid/8 bg-mid/8">
      <div className="grid grid-cols-2 gap-px md:grid-cols-5">
        {tiles.map(({ label, value }) => (
          <Tile key={label} label={label} value={value} loading={loading && data === null} />
        ))}
      </div>
      {error ? (
        <div className="border-t border-err/20 bg-err/5 px-4 py-1.5 font-mono text-[0.55rem] uppercase tracking-wider text-err/80">
          stats refresh failed — {error.message}
        </div>
      ) : null}
    </div>
  );
}

function renderTiles(s: PlatformStats | null) {
  return [
    { label: "Active Clients", value: s ? `${s.active_clients}/${s.total_clients}` : "—" },
    { label: "Leads (7d)", value: s ? String(s.total_leads_7d) : "—" },
    { label: "Leads (30d)", value: s ? String(s.total_leads_30d) : "—" },
    { label: "Approvals Pending", value: s ? String(s.approvals_pending) : "—" },
    { label: "Mutations (24h)", value: s ? String(s.mutations_24h) : "—" },
  ];
}

function Tile({
  label,
  value,
  loading,
}: {
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <div
      className="p-4"
      style={{
        background: "color-mix(in srgb, var(--color-mid) 2%, var(--color-bg))",
      }}
    >
      <div className="mb-1 font-mono text-[0.56rem] uppercase tracking-wider opacity-45">
        {label}
      </div>
      <div className="text-2xl font-bold tracking-tight">
        {loading ? <span className="opacity-40">…</span> : value}
      </div>
    </div>
  );
}
