import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

type Tone = "neutral" | "ok" | "warn" | "err" | "filled-ok" | "filled-warn" | "filled-neutral";

const toneClass: Record<Tone, string> = {
  neutral: "border border-mid/12 text-mid/60",
  ok: "border border-ok/25 text-ok",
  warn: "border border-warn/25 text-warn",
  err: "border border-err/25 text-err",
  // Filled "status pills" used on lead rows.
  "filled-ok": "bg-ok/15 text-ok",
  "filled-warn": "bg-warn/15 text-warn",
  "filled-neutral": "bg-mid/12 text-mid",
};

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
        "rounded-[calc(var(--radius-card)*0.4)] px-2 py-[0.15rem] font-mono text-[0.58rem] uppercase tracking-wider",
        toneClass[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
