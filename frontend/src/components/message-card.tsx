import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { type CrawlJob } from "@/lib/api";

export function MessageCard({
  title,
  description,
  tone = "muted",
}: {
  title: string;
  description?: string;
  tone?: "error" | "muted";
}) {
  return (
    <Card className={tone === "error" ? "border-destructive/40" : undefined}>
      <CardContent className="py-8 text-center">
        <p
          className={cn(
            "text-sm font-medium mb-1",
            tone === "error" && "text-destructive",
          )}
        >
          {title}
        </p>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function CrawlErrorCard({ crawl }: { crawl: CrawlJob }) {
  return (
    <MessageCard
      tone="error"
      title={crawl.status === "failed" ? "Crawl failed" : "No pages found"}
      description={
        crawl.error_message ??
        "The site may be blocking crawlers, require authentication, or have no accessible pages."
      }
    />
  );
}

export function LlmsLoadErrorCard() {
  return (
    <MessageCard
      tone="error"
      title="Failed to load llms.txt"
      description="The crawl completed but we couldn't fetch the generated file. Try refreshing the page."
    />
  );
}
