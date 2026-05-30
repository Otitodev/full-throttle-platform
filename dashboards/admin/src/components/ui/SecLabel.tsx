import type { ReactNode } from "react";

/**
 * Tiny uppercase section header with a thin rule trailing off to the right.
 *
 *   <SecLabel>Platform Overview</SecLabel>
 */
export function SecLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 font-mono text-[0.6rem] uppercase tracking-[0.06em] opacity-45">
      <span>{children}</span>
      <span className="h-px flex-1 bg-mid/10" />
    </div>
  );
}
