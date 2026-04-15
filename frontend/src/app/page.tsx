import { SiteUrlForm } from "@/components/site-url-form";
import { SitesTable } from "@/components/sites-table";

export default function Home() {
  return (
    <main className="flex-1 w-full">
      <section className="border-b border-white/15">
        <div className="px-10 pt-24 pb-16 flex flex-col gap-8">
          <div className="flex flex-col gap-4">
            <h1 className="text-5xl md:text-6xl font-medium tracking-tight leading-[1.05]">
              Generate an llms.txt
              <br />
              <span className="text-muted-foreground">for any website.</span>
            </h1>
            <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
              Crawl a site, get a clean llms.txt, and watch for changes over
              time. Built for teams making their docs legible to AI.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <SiteUrlForm />
            <div className="flex flex-col gap-0.5">
              <p className="text-xs text-muted-foreground">
                Works best with developer docs, SaaS marketing sites, and open documentation.
                Paywalled or heavily bot-protected sites may not crawl successfully.
              </p>
              <p className="text-xs text-muted-foreground">
                Re-crawl any site anytime to refresh its llms.txt and capture a new change event.
              </p>
            </div>
          </div>
        </div>
      </section>
      <section className="px-10 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-medium text-foreground">
            Generated sites
          </h2>
        </div>
        <SitesTable />
      </section>
    </main>
  );
}
