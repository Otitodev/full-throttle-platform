/**
 * Tiny typed wrapper around the admin aggregator API.
 *
 * Goals: keep this file the single place that knows the wire shapes,
 * so swapping endpoints or response keys is mechanical.
 */

import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Wire types — mirror aggregator's Pydantic models 1:1.
// ---------------------------------------------------------------------------

export interface PlatformStats {
  total_clients: number;
  active_clients: number;
  total_leads_7d: number;
  total_leads_30d: number;
  approvals_pending: number;
  mutations_24h: number;
}

export interface ProfileMeta {
  slug: string;
  display_name: string;
  site_type: string;
  adapter: string;
  port: number | null;
  brand_voice: string | null;
  services: string[];
  gateway_active: boolean;
  session_count: number;
  last_active: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface AuditEntry {
  id: string;
  ts: string;
  skill: string;
  action: string;
  target: string | null;
  status: string | null;
  rollback_ref: string | null;
  approval_state: string | null;
  repo: string | null;
  slug: string;
  // Extra fields the gateway might emit per skill — left open.
  [extra: string]: unknown;
}

// ---------------------------------------------------------------------------
// Fetch primitives.
// ---------------------------------------------------------------------------

async function fetchJson<T>(path: string): Promise<T> {
  const resp = await fetch(path, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`GET ${path} → ${resp.status} ${body.slice(0, 200)}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  platformStats: () => fetchJson<PlatformStats>("/api/admin/platform/stats"),
  clients: () => fetchJson<ProfileMeta[]>("/api/admin/clients"),
  client: (slug: string) =>
    fetchJson<Record<string, unknown>>(
      `/api/admin/clients/${encodeURIComponent(slug)}`,
    ),
  approvals: () => fetchJson<AuditEntry[]>("/api/admin/approvals"),
  audit: (params: { skill?: string; slug?: string; limit?: number } = {}) => {
    const sp = new URLSearchParams();
    if (params.skill) sp.set("skill", params.skill);
    if (params.slug) sp.set("slug", params.slug);
    if (params.limit !== undefined) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return fetchJson<AuditEntry[]>(`/api/admin/audit${qs ? `?${qs}` : ""}`);
  },
};

// ---------------------------------------------------------------------------
// Polling hook.
// ---------------------------------------------------------------------------

export interface PollState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

/**
 * Polls ``fetcher`` every ``intervalMs`` ms. Returns the latest value plus
 * the latest error (if the most recent fetch failed). The first fetch runs
 * immediately; subsequent fetches happen on the interval.
 *
 * Errors do NOT clear ``data`` — the UI keeps showing the last good values
 * so a transient blip doesn't blank the dashboard.
 */
export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs = 30_000,
): PollState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;

    const tick = async () => {
      try {
        const v = await fetcher();
        if (cancelled) return;
        setData(v);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e : new Error(String(e)));
      } finally {
        if (!cancelled) setLoading(false);
        if (!cancelled)
          timer = window.setTimeout(tick, intervalMs) as unknown as number;
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [fetcher, intervalMs]);

  return { data, error, loading };
}
