import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

/**
 * Broadcast-terminal card with viewfinder corner ticks.
 *
 *   <Card>
 *     <Card.Header title="Clients" hint="7 active" />
 *     <Card.Body>…</Card.Body>
 *   </Card>
 */
export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "relative overflow-hidden rounded-[var(--radius-card)] border border-mid/8 bg-mid/2",
        className,
      )}
    >
      <span className="cm cm-tl" />
      <span className="cm cm-tr" />
      <span className="cm cm-bl" />
      <span className="cm cm-br" />
      {children}
    </div>
  );
}

function CardHeader({
  title,
  hint,
}: {
  title: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-mid/6 px-4 py-2.5 font-mono text-[0.6rem] uppercase tracking-[0.05em]">
      <span>{title}</span>
      {hint ? <span className="opacity-40">{hint}</span> : null}
    </div>
  );
}

function CardBody({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cx("px-4 py-2", className)}>{children}</div>;
}

Card.Header = CardHeader;
Card.Body = CardBody;
