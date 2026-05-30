/**
 * Display helpers — small + UI-agnostic so they're easy to unit-test later.
 */

export function timeAgo(epochOrIso: number | string | null | undefined): string {
  if (epochOrIso == null) return "—";
  const t =
    typeof epochOrIso === "number"
      ? epochOrIso * 1000
      : Date.parse(epochOrIso);
  if (!Number.isFinite(t)) return "—";
  const delta = Math.max(0, Date.now() - t);
  const s = Math.floor(delta / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  const mo = Math.floor(d / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(d / 365)}y ago`;
}

export function utcClock(epochOrIso: number | string | null | undefined): string {
  if (epochOrIso == null) return "—";
  const t =
    typeof epochOrIso === "number"
      ? epochOrIso * 1000
      : Date.parse(epochOrIso);
  if (!Number.isFinite(t)) return "—";
  return new Date(t).toISOString().slice(11, 16);
}

export function usd(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return `$${cents.toFixed(2)}`;
}
