import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

type Tone = "neutral" | "ok" | "warn" | "err";

const toneClass: Record<Tone, string> = {
  neutral: "border-mid/12 text-mid/60",
  ok: "border-ok/25 text-ok",
  warn: "border-warn/25 text-warn",
  err: "border-err/25 text-err",
};

/**
 * Tiny pill used for OPERATOR / LIVE / DEGRADED / OFFLINE chips.
 */
export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "rounded-[calc(var(--radius-card)*0.4)] border px-2 py-[0.15rem] font-mono text-[0.58rem] uppercase tracking-wider",
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
