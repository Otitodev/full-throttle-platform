import { useEffect, useState } from "react";

function useUtcClock() {
  const [s, setS] = useState(() => new Date().toISOString().slice(11, 19));
  useEffect(() => {
    const t = window.setInterval(
      () => setS(new Date().toISOString().slice(11, 19)),
      1000,
    );
    return () => window.clearInterval(t);
  }, []);
  return s;
}

export function Topbar({ slug }: { slug: string }) {
  const clock = useUtcClock();
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-2 border-b border-mid/10 pb-4">
      <div className="flex items-center gap-2.5">
        <div className="font-mono text-[0.7rem] uppercase tracking-[0.08em]">
          Full<span className="opacity-45">Throttle</span>
        </div>
        <span className="rounded-[calc(var(--radius-card)*0.5)] border border-mid/15 bg-mid/[0.03] px-2 py-0.5 font-mono text-[0.6rem]">
          Profile: {slug}
        </span>
        <div className="flex items-center gap-1 font-mono text-[0.58rem] uppercase tracking-wider opacity-55">
          <span className="rec-dot" />
          REC
        </div>
      </div>
      <div className="font-mono text-[0.6rem] tracking-wider opacity-45">
        {clock} UTC
      </div>
    </div>
  );
}
