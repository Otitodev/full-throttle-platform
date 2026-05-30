import { cx } from "../../lib/cx";

type Tone = "ok" | "warn" | "err";

const toneClass: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  err: "bg-err",
};

/** 6×6 colored circle used in client-name rows and status indicators. */
export function Dot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden
      className={cx("inline-block size-1.5 rounded-full", toneClass[tone])}
    />
  );
}
