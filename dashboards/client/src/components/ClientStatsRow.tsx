import { useCallback } from "react";

import { api, usePoll, type ClientStats } from "../lib/api";

/**
 * 4-tile owner stats row. Polls /api/client/{slug}/stats every 30 s.
 * Mobile: 2x2 grid below 480px, 4x1 above.
 */
export function ClientStatsRow() {
  const fetcher = useCallback(() => api.stats(), []);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const tiles = pickTiles(data);

  return (
    <div className="mb-6 overflow-hidden rounded-[var(--radius-card)] border border-mid/8 bg-mid/8">
      <div className="grid grid-cols-2 gap-px sm:grid-cols-4">
        {tiles.map(({ label, value }) => (
          <Tile
            key={label}
            label={label}
            value={value}
            loading={loading && data === null}
          />
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

function pickTiles(s: ClientStats | null) {
  return [
    { label: "Leads (7d)", value: s ? String(s.leads_7d) : "—" },
    { label: "Leads (30d)", value: s ? String(s.leads_30d) : "—" },
    { label: "Approvals", value: s ? String(s.approvals_pending) : "—" },
    {
      label: "Mutations (24h)",
      value: s ? String(s.mutations_24h) : "—",
    },
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
      <div className="mb-1 font-mono text-[0.58rem] uppercase tracking-wider opacity-45">
        {label}
      </div>
      <div className="text-2xl font-bold tracking-tight">
        {loading ? <span className="opacity-40">…</span> : value}
      </div>
    </div>
  );
}
