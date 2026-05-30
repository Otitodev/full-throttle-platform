import { Card } from "./ui/Card";

/**
 * Renders when ``auth.getToken()`` returns null — either the owner opened the
 * URL without the ``#token=`` fragment, or sessionStorage was wiped.
 *
 * Tells them what to do without saying anything they don't need to hear.
 */
export function NotAuthenticated() {
  return (
    <Card className="mx-auto max-w-md">
      <Card.Header title="Sign-in required" />
      <Card.Body className="space-y-3 text-[0.82rem] leading-relaxed">
        <p>
          This dashboard opens from the link your Full Throttle setup sent you
          (it ends with <span className="font-mono text-mid/70">#token=…</span>).
        </p>
        <p className="opacity-75">
          If you bookmarked it without the token, ask your operator to resend
          the link.
        </p>
      </Card.Body>
    </Card>
  );
}
