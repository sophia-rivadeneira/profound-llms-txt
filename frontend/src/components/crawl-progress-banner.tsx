"use client";

import { useEffect, useState } from "react";

export function CrawlProgressBanner({
  domain,
  status,
  pagesFound,
  startedAt,
  maxPages,
  maxSeconds,
}: {
  domain: string;
  status: string;
  pagesFound: number;
  startedAt: string | null;
  maxPages: number;
  maxSeconds: number;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (status !== "running" || !startedAt) return;
    const update = () =>
      setElapsed(Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [status, startedAt]);

  const pagesPct = Math.min((pagesFound / maxPages) * 100, 100);
  const timePct = Math.min((elapsed / maxSeconds) * 100, 100);
  const progressPct = Math.max(pagesPct, timePct);
  const timeLeft = Math.max(maxSeconds - elapsed, 0);

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border/60 bg-card/40 px-4 py-3">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-foreground/60" />
            <span className="relative inline-flex size-2 rounded-full bg-foreground" />
          </span>
          {status === "running" ? `Crawling ${domain}…` : "Queued…"}
        </span>
        <span className="text-muted-foreground tabular-nums text-xs">
          {pagesFound} / {maxPages} pages
          {status === "running" && elapsed > 0 && (
            <> · stops in {timeLeft}s</>
          )}
        </span>
      </div>
      <div className="h-0.5 w-full overflow-hidden rounded-full bg-border/60">
        {status === "running" && elapsed > 0 ? (
          <div
            className="h-full rounded-full bg-foreground/80 transition-all duration-1000"
            style={{ width: `${progressPct}%` }}
          />
        ) : (
          <div className="h-full w-1/3 animate-[progress_1.5s_ease-in-out_infinite] bg-foreground/80" />
        )}
      </div>
    </div>
  );
}
