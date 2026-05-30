/**
 * Typed wrapper around the client aggregator API.
 *
 * Every call automatically includes the Bearer header from ``auth.getToken``
 * and the slug from ``auth.getSlug``. Callers don't pass them. A missing
 * token surfaces as ``AuthError`` so the UI can render the NotAuthenticated
 * fallback instead of a generic error.
 */

import { useEffect, useState } from "react";

import { clearToken, getSlug, getToken } from "./auth";

// ---------------------------------------------------------------------------
// Wire types (mirror aggregator's Pydantic models).
// ---------------------------------------------------------------------------

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
  [extra: string]: unknown;
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

export interface ClientStats {
  slug: string;
  leads_7d: number;
  leads_30d: number;
  recent_publishes_30d: number;
  mutations_24h: number;
  approvals_pending: number;
  meta?: ProfileMeta;
  // governance/status.py fields — surfaced opaquely.
  timeline?: AuditEntry[];
  approval_queue?: AuditEntry[];
  counts_by_action?: Record<string, number>;
  counts_by_status?: Record<string, number>;
  cron_jobs?: unknown[];
  total_mutations?: number;
  [extra: string]: unknown;
}

export class AuthError extends Error {
  constructor(message = "not authenticated") {
    super(message);
    this.name = "AuthError";
  }
}

async function fetchJson<T>(path: string): Promise<T> {
  const token = getToken();
  if (!token) throw new AuthError();
  const resp = await fetch(path, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    credentials: "same-origin",
  });
  if (resp.status === 401) {
    clearToken();
    throw new AuthError("token rejected (401)");
  }
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`GET ${path} → ${resp.status} ${body.slice(0, 200)}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  stats: () => fetchJson<ClientStats>(`/api/client/${getSlug()}/stats`),
  leads: (limit = 20) =>
    fetchJson<AuditEntry[]>(`/api/client/${getSlug()}/leads?limit=${limit}`),
  approvals: () =>
    fetchJson<AuditEntry[]>(`/api/client/${getSlug()}/approvals`),
  content: (limit = 20) =>
    fetchJson<AuditEntry[]>(`/api/client/${getSlug()}/content?limit=${limit}`),
  activity: (limit = 50) =>
    fetchJson<AuditEntry[]>(`/api/client/${getSlug()}/activity?limit=${limit}`),
};

// ---------------------------------------------------------------------------
// Polling hook (mirrors admin SPA's usePoll).
// ---------------------------------------------------------------------------

export interface PollState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

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
