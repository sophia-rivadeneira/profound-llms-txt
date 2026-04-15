"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, isStatusInFlight, type Site } from "@/lib/api";
import { useLastSeenEventId } from "@/lib/seen";

function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function SitesTable() {
  const [query, setQuery] = useState("");

  const sitesQuery = useQuery({
    queryKey: ["sites"],
    queryFn: () => api.listSites(),
    refetchInterval: (query) => {
      const anyInFlight = query.state.data?.some((s) =>
        isStatusInFlight(s.last_crawl_status),
      );
      return anyInFlight ? 2000 : false;
    },
  });

  const sites = useMemo(() => sitesQuery.data ?? [], [sitesQuery.data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sites;
    return sites.filter(
      (s) =>
        s.domain.toLowerCase().includes(q) ||
        s.url.toLowerCase().includes(q) ||
        (s.title ?? "").toLowerCase().includes(q),
    );
  }, [sites, query]);

  if (sitesQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading sites…</p>;
  }

  if (sitesQuery.isError) {
    return (
      <p className="text-sm text-destructive">
        Failed to load sites. Is the backend running?
      </p>
    );
  }

  if (sites.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No sites yet. Generate your first llms.txt above.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Input placeholder="Search sites…" value={query} onChange={(e) => setQuery(e.target.value)} className="max-w-sm"/>
      <div className="rounded-xl border border-border/60 bg-card/30">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Domain</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Last crawled</TableHead>
              <TableHead className="text-right">Change events</TableHead>
              <TableHead aria-label="Actions" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((site) => (<SiteRow key={site.id} site={site} /> ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground" >
                  No matches for &ldquo;{query}&rdquo;.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function SiteRow({ site }: { site: Site }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const lastSeen = useLastSeenEventId(site.id);
  const hasUnread = (site.latest_event_id ?? 0) > lastSeen;

  const recrawlMutation = useMutation({
    mutationFn: () => api.triggerCrawl(site.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sites"] });
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["sites"] });
    },
  });

  const isCrawlInFlight = isStatusInFlight(site.last_crawl_status);

  return (
    <TableRow
      className="cursor-pointer hover:bg-white/5 transition-colors"
      onClick={() => router.push(`/sites/${site.slug ?? site.domain}`)}
    >
      <TableCell className="font-medium">
        <a href={site.url} target="_blank" rel="noreferrer" className="hover:underline" onClick={(e) => e.stopPropagation()} >
          {site.domain}
        </a>
      </TableCell>
      <TableCell className="text-muted-foreground max-w-xs truncate">
        {site.title ?? "—"}
      </TableCell>
      <TableCell className="text-muted-foreground tabular-nums">
        {site.last_crawl_status === "failed" ? (
          <span className="text-destructive text-sm">Failed</span>
        ) : isCrawlInFlight ? (
          <span className="text-muted-foreground text-sm">Crawling…</span>
        ) : (
          formatRelative(site.last_crawled_at)
        )}
      </TableCell>
      <TableCell className="text-right">
        {hasUnread ? ( <Badge>New</Badge> ) : (
          <span className="text-sm text-muted-foreground">
            {site.event_count > 0 ? `${site.event_count} event${site.event_count === 1 ? "" : "s"}` : "—"}
          </span>
        )}
      </TableCell>
      <TableCell className="text-right">
        <Button
          size="sm"
          variant="outline"
          disabled={isCrawlInFlight || recrawlMutation.isPending}
          onClick={(e) => {
            e.stopPropagation();
            recrawlMutation.mutate();
          }}
        >
          {isCrawlInFlight? "Crawling…" : recrawlMutation.isPending ? "Starting…" : "Re-crawl"}
        </Button>
      </TableCell>
    </TableRow>
  );
}
