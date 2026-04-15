"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SimpleTooltip } from "@/components/simple-tooltip";
import { api, ApiError, isStatusInFlight } from "@/lib/api";
import { markSiteSeen, useLastSeenEventId } from "@/lib/seen";
import { ChangeTimeline } from "@/components/change-timeline";
import { PagesBySection } from "@/components/pages-by-section";
import { CrawlErrorCard, LlmsLoadErrorCard } from "@/components/message-card";
import { DeleteSiteDialog } from "@/components/delete-site-dialog";
import { CrawlProgressBanner } from "@/components/crawl-progress-banner";
import { LlmsPreview } from "@/components/llms-preview";
import { MonitorSettings } from "@/components/monitor-settings";

export function SiteDetail({ siteId }: { siteId: number }) {
  const queryClient = useQueryClient();
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const prevStatusRef = useRef<string | undefined>(undefined);
  const [reviewTick, setReviewTick] = useState(0);
  const lastSeenEventId = useLastSeenEventId(siteId);

  const siteQuery = useQuery({
    queryKey: ["site", siteId],
    queryFn: () => api.getSite(siteId),
  });

  const crawlsQuery = useQuery({
    queryKey: ["crawls", siteId],
    queryFn: () => api.listCrawls(siteId),
    refetchInterval: (query) =>
      isStatusInFlight(query.state.data?.[0]?.status) ? 2000 : false,
  });

  const latestCrawl = crawlsQuery.data?.[0];
  const latestCompleted = crawlsQuery.data?.find((j) => j.status === "completed");
  const isInProgress = isStatusInFlight(latestCrawl?.status);

  const llmsQuery = useQuery({
    queryKey: ["llms", siteId],
    queryFn: () => api.getLlms(siteId),
    enabled: !!latestCompleted,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404),
  });

  const crawlDetailQuery = useQuery({
    queryKey: ["crawl-detail", siteId, latestCompleted?.id],
    queryFn: () =>
      latestCompleted
        ? api.getCrawl(siteId, latestCompleted.id)
        : Promise.resolve(null),
    enabled: !!latestCompleted,
  });

  const changesQuery = useQuery({
    queryKey: ["changes", siteId],
    queryFn: () => api.listChangeEvents(siteId),
  });

  const site = siteQuery.data;
  const changeEvents = changesQuery.data ?? [];
  const unreadChanges = changeEvents.filter((e) => e.id > lastSeenEventId);
  const pages = crawlDetailQuery.data?.pages ?? [];

  const triggerMutation = useMutation({
    mutationFn: () => api.triggerCrawl(siteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawls", siteId] });
    },
  });

  const recentlyRejected409 = triggerMutation.error instanceof ApiError && triggerMutation.error.status === 409;
  const triggerDisabled = isInProgress || triggerMutation.isPending || recentlyRejected409;

  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = latestCrawl?.status;
    if (prev && prev !== "completed" && curr === "completed") {
      for (const key of ["site", "llms", "changes", "crawl-detail"] as const) {
        queryClient.invalidateQueries({ queryKey: [key, siteId] });
      }
    }
    if (prev && prev !== curr && (curr === "completed" || curr === "failed")) {
      queryClient.invalidateQueries({ queryKey: ["sites"] });
      queryClient.invalidateQueries({ queryKey: ["monitor", siteId] });
    }
    prevStatusRef.current = curr;
  }, [latestCrawl?.status, queryClient, siteId]);

  if (siteQuery.isLoading) {
    return <Centered>Loading…</Centered>;
  }
  if (siteQuery.isError || !site) {
    return <Centered>Site not found.</Centered>;
  }

  const markAllChangesSeen = () => {
    if (changeEvents.length > 0) markSiteSeen(siteId, changeEvents[0].id);
  };

  const handleReviewUnreadChanges = () => {
    setReviewTick((t) => t + 1);
    timelineRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    markAllChangesSeen();
  };

  return (
    <main className="flex-1 w-full">
      <div className="px-10 py-8 flex flex-col gap-6">
        <Link href="/" className="text-sm text-muted-foreground hover:underline">
          ← Back to all sites
        </Link>
        <header className="flex flex-col gap-3">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex flex-col gap-2">
              <h1 className="text-4xl font-medium tracking-tight">
                <a href={site.url} target="_blank" rel="noreferrer" className="hover:underline" >
                  {site.domain}
                </a>
              </h1>
              {site.title && (<p className="text-muted-foreground">{site.title}</p>)}
            </div>
            <div className="flex items-center gap-2">
              <SimpleTooltip content="Re-crawl this site to refresh its llms.txt.">
                <Button onClick={() => triggerMutation.mutate()} disabled={triggerDisabled}>
                  {isInProgress ? "Crawling…" : triggerMutation.isPending ? "Starting…" : "Re-crawl now"}
                </Button>
              </SimpleTooltip>
              <DeleteSiteDialog siteId={site.id} siteDomain={site.domain} />
            </div>
          </div>
          {isInProgress && latestCrawl && (
            <CrawlProgressBanner
              domain={site.domain}
              status={latestCrawl.status}
              pagesFound={latestCrawl.pages_found}
              startedAt={latestCrawl.started_at}
              maxPages={latestCrawl.max_pages}
              maxSeconds={latestCrawl.max_duration_seconds}
            />
          )}
        </header>

        {unreadChanges.length > 0 && (
          <div className="flex items-center justify-between rounded-xl border border-border/60 bg-card/40 px-4 py-3">
            <p className="text-sm">
              <strong>{unreadChanges.length} new change event
              {unreadChanges.length === 1 ? "" : "s"}</strong> detected since your last visit.
            </p>
            <Button size="sm" onClick={handleReviewUnreadChanges}> Review </Button>
          </div>
        )}
        {isInProgress && !llmsQuery.data && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              First crawl in progress. This page will update automatically when
              it&apos;s done.
            </CardContent>
          </Card>
        )}
        {renderErrorCard()}

        {llmsQuery.data && (<LlmsPreview siteId={siteId} content={llmsQuery.data.content} /> )}

        {pages.length > 0 && <PagesBySection pages={pages} />}

        <MonitorSettings siteId={siteId} />

        <div ref={timelineRef}>
          <ChangeTimeline events={changeEvents} lastSeen={lastSeenEventId} reviewTick={reviewTick} onOpen={markAllChangesSeen} />
        </div>
      </div>
    </main>
  );

  function renderErrorCard() {
    if (isInProgress || llmsQuery.data) return null;
    if (latestCrawl?.status === "failed") return <CrawlErrorCard crawl={latestCrawl} />;
    if (latestCompleted && llmsQuery.isError) {
      const is404 = llmsQuery.error instanceof ApiError && llmsQuery.error.status === 404;
      return is404 ? <CrawlErrorCard crawl={latestCompleted} /> : <LlmsLoadErrorCard />;
    }
    return null;
  }
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex-1 flex items-center justify-center">
      <p className="text-muted-foreground">{children}</p>
    </main>
  );
}


