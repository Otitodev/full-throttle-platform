/**
 * Owner-dashboard auth flow.
 *
 *   1. The owner gets a URL like
 *        https://mrfence.hooks.fullthrottle.io/dash#token=abc123
 *      from promote_client.sh's stdout (printed once at promotion time).
 *   2. On first load this module reads ``location.hash``, extracts the token,
 *      stores it in ``sessionStorage`` (per-tab, cleared when the tab closes),
 *      and *strips the hash from the URL* so the token never leaks into
 *      browser history, the access log, or anything a screenshot might catch.
 *   3. Subsequent API calls read the token from ``sessionStorage``.
 *
 * Slug is inferred from the hostname's first DNS label
 * (``mrfence.hooks.fullthrottle.io`` → ``mrfence``). For local dev with
 * ``localhost``, set ``VITE_FT_DEV_SLUG`` in .env.local.
 */

const TOKEN_KEY = "ft.dashboard.token";

let _slug: string | null = null;
let _bootRan = false;

/** Idempotent — safe to call from every component. Runs the hash → storage
 *  promotion exactly once per page load. */
export function bootAuth(): void {
  if (_bootRan) return;
  _bootRan = true;

  try {
    const hash = window.location.hash;
    if (hash && hash.includes("token=")) {
      const params = new URLSearchParams(
        hash.startsWith("#") ? hash.slice(1) : hash,
      );
      const tok = params.get("token");
      if (tok) {
        window.sessionStorage.setItem(TOKEN_KEY, tok);
        // Strip the hash without polluting history.
        const clean = window.location.pathname + window.location.search;
        window.history.replaceState(null, "", clean);
      }
    }
  } catch {
    // sessionStorage can throw in private-browsing modes; fall through and the
    // SPA will show the NotAuthenticated state.
  }
}

export function getToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function getSlug(): string {
  if (_slug !== null) return _slug;
  // Dev override for local Vite (`npm run dev` against localhost).
  const fromEnv = (import.meta.env.VITE_FT_DEV_SLUG as string | undefined) ?? "";
  if (fromEnv) return (_slug = fromEnv);

  const host = window.location.hostname;
  // Pull the first DNS label as the slug. Strip a leading IPv6 bracket if any.
  const first = host.split(".")[0] ?? "";
  _slug = first || "unknown";
  return _slug;
}
