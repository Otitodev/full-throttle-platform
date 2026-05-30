import { useCallback, useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import { api, usePoll, type AuditEntry, type ClientDetail as ClientDetailT } from "../lib/api";
import { timeAgo, usd, utcClock } from "../lib/format";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Dot } from "../components/ui/Dot";
import { SecLabel } from "../components/ui/SecLabel";

/**
 * Drill-down view for one client. Opened by clicking a row in the admin
 * ClientTable. Fetches /api/admin/clients/{slug} which returns the full
 * compute_client_stats payload + ProfileMeta in a single call.
 */
export function ClientDetail() {
  const { slug = "" } = useParams<{ slug: string }>();
  const fetcher = useCallback(() => api.client(slug), [slug]);
  const { data, error, loading } = usePoll(fetcher, 30_000);

  const timeline = data?.timeline ?? [];
  const approvals = data?.approval_queue ?? [];

  return (
    <>
      <div className="mb-3 flex items-center gap-3 font-mono text-[0.6rem] uppercase tracking-wider">
        <Link to="/" className="opacity-50 hover:opacity-100">
          ← Overview
        </Link>
        <span className="opacity-30">/</span>
        <span className="opacity-90">{slug}</span>
      </div>

      <SecLabel>Client</SecLabel>
      <MetaPanel
        slug={slug}
        data={data}
        loading={loading && data === null}
        error={error}
      />

      <SecLabel>This Client</SecLabel>
      <StatsRowScoped data={data} loading={loading && data === null} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <ScopedAudit slug={slug} timeline={timeline} loading={loading && data === null} />
        <ScopedApprovals approvals={approvals} loading={loading && data === null} />
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Meta panel
// ---------------------------------------------------------------------------

function MetaPanel({
  slug,
  data,
  loading,
  error,
}: {
  slug: string;
  data: ClientDetailT | null;
  loading: boolean;
  error: Error | null;
}) {
  const meta = data?.meta;

  if (error && !data) {
    return (
      <Card className="mb-6">
        <Card.Body className="text-err text-[0.8rem]">
          could not load client — {error.message}
        </Card.Body>
      </Card>
    );
  }

  return (
    <Card className="mb-6">
      <Card.Header
        title={meta?.display_name || slug}
        hint={
          meta ? (
            <span className="flex items-center gap-2">
              <Dot tone={meta.gateway_active ? "ok" : "err"} />
              {meta.gateway_active ? "LIVE" : "OFFLINE"}
            </span>
          ) : (
            "…"
          )
        }
      />
      <Card.Body>
        {loading && !meta ? (
          <div className="text-[0.75rem] opacity-40">…</div>
        ) : meta ? (
          <div className="grid grid-cols-2 gap-y-2 text-[0.78rem] md:grid-cols-4">
            <MetaCell label="Slug" value={<code>{meta.slug}</code>} />
            <MetaCell label="Site Type" value={meta.site_type} />
            <MetaCell label="Adapter" value={meta.adapter} />
            <MetaCell
              label="Gateway Port"
              value={meta.port != null ? String(meta.port) : "—"}
            />
            <MetaCell label="Sessions" value={String(meta.session_count)} />
            <MetaCell label="Last Active" value={timeAgo(meta.last_active)} />
            <MetaCell label="Cost" value={usd(meta.total_cost_usd)} />
            <MetaCell
              label="Tokens In/Out"
              value={`${meta.total_input_tokens} / ${meta.total_output_tokens}`}
            />
            {meta.brand_voice ? (
              <MetaCell
                label="Brand Voice"
                value={meta.brand_voice}
                className="col-span-2 md:col-span-4"
              />
            ) : null}
            {meta.services.length > 0 ? (
              <MetaCell
                label="Services"
                value={meta.services.join(", ")}
                className="col-span-2 md:col-span-4"
              />
            ) : null}
          </div>
        ) : (
          <div className="text-[0.75rem] opacity-40">unknown client</div>
        )}
      </Card.Body>
    </Card>
  );
}

function MetaCell({
  label,
  value,
  className,
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="font-mono text-[0.55rem] uppercase tracking-wider opacity-40">
        {label}
      </div>
      <div className="text-[0.78rem]">{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stats tiles (scoped to this client)
// ---------------------------------------------------------------------------

function StatsRowScoped({
  data,
  loading,
}: {
  data: ClientDetailT | null;
  loading: boolean;
}) {
  const tiles = [
    { label: "Leads (7d)", value: data ? String(data.leads_7d) : "—" },
    { label: "Leads (30d)", value: data ? String(data.leads_30d) : "—" },
    { label: "Approvals", value: data ? String(data.approvals_pending) : "—" },
    { label: "Mutations (24h)", value: data ? String(data.mutations_24h) : "—" },
  ];
  return (
    <div className="mb-6 overflow-hidden rounded-[var(--radius-card)] border border-mid/8 bg-mid/8">
      <div className="grid grid-cols-2 gap-px md:grid-cols-4">
        {tiles.map(({ label, value }) => (
          <div
            key={label}
            className="p-4"
            style={{
              background:
                "color-mix(in srgb, var(--color-mid) 2%, var(--color-bg))",
            }}
          >
            <div className="mb-1 font-mono text-[0.56rem] uppercase tracking-wider opacity-45">
              {label}
            </div>
            <div className="text-2xl font-bold tracking-tight">
              {loading ? <span className="opacity-40">…</span> : value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scoped audit + approvals
// ---------------------------------------------------------------------------

function ScopedAudit({
  slug,
  timeline,
  loading,
}: {
  slug: string;
  timeline: AuditEntry[];
  loading: boolean;
}) {
  // The aggregator's status.py timeline is already scoped to this profile, but
  // may not carry the slug field on every row — patch defensively.
  const rows = useMemo(
    () => timeline.map((r) => ({ ...r, slug: r.slug || slug })),
    [timeline, slug],
  );
  return (
    <Card>
      <Card.Header
        title="Audit Trail"
        hint={`last ${rows.length}`}
      />
      <Card.Body className="!py-0">
        {loading && rows.length === 0 ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">…</div>
        ) : rows.length === 0 ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">
            no mutations yet
          </div>
        ) : (
          rows.map((r) => <AuditLine key={r.id} row={r} />)
        )}
      </Card.Body>
    </Card>
  );
}

function AuditLine({ row }: { row: AuditEntry }) {
  return (
    <div className="flex items-center gap-2.5 border-b border-mid/[0.03] py-1.5 text-[0.73rem] last:border-b-0">
      <span className="min-w-[3rem] font-mono text-[0.56rem] tracking-wider opacity-40">
        {utcClock(row.ts)}
      </span>
      <span className="whitespace-nowrap rounded-[calc(var(--radius-card)*0.35)] border border-mid/7 px-1.5 py-[0.08rem] font-mono text-[0.53rem] uppercase tracking-wider opacity-55">
        {row.skill}
      </span>
      <span className="flex-1 truncate">
        {row.action}
        {row.target ? <span className="opacity-50"> · {row.target}</span> : null}
      </span>
      {row.status && row.status !== "ok" ? (
        <Badge tone={row.status === "error" ? "err" : "warn"}>{row.status}</Badge>
      ) : null}
    </div>
  );
}

function ScopedApprovals({
  approvals,
  loading,
}: {
  approvals: AuditEntry[];
  loading: boolean;
}) {
  return (
    <Card>
      <Card.Header
        title="Pending Approvals"
        hint={`${approvals.length} pending`}
      />
      <Card.Body className="!py-0">
        {loading && approvals.length === 0 ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">…</div>
        ) : approvals.length === 0 ? (
          <div className="py-4 text-center text-[0.7rem] text-mid/40">
            none waiting
          </div>
        ) : (
          approvals.map((row) => (
            <div
              key={row.id}
              className="flex items-start gap-2.5 border-b border-mid/4 py-2 text-[0.78rem] last:border-b-0"
            >
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
          ))
        )}
      </Card.Body>
    </Card>
  );
}
