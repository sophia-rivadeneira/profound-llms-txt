import { Card, CardContent } from "@/components/ui/card";
import { type CrawlJob } from "@/lib/api";

export function CrawlErrorCard({ crawl }: { crawl: CrawlJob }) {
  const isFailed = crawl.status === "failed";
  return (
    <Card className="border-destructive/40">
      <CardContent className="py-8 text-center">
        <p className="text-sm font-medium text-destructive mb-1">
          {isFailed ? "Crawl failed" : "No pages found"}
        </p>
        <p className="text-xs text-muted-foreground">
          {crawl.error_message
            ? crawl.error_message
            : "The site may be blocking crawlers, require authentication, or have no accessible pages."}
        </p>
      </CardContent>
    </Card>
  );
}

export function LlmsLoadErrorCard() {
  return (
    <Card className="border-destructive/40">
      <CardContent className="py-8 text-center">
        <p className="text-sm font-medium text-destructive mb-1">
          Failed to load llms.txt
        </p>
        <p className="text-xs text-muted-foreground">
          The crawl completed but we couldn&apos;t fetch the generated file. Try refreshing the page.
        </p>
      </CardContent>
    </Card>
  );
}
