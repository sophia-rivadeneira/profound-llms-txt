import { SiteDetail } from "@/components/site-detail";
import { api } from "@/lib/api";

export default async function SiteDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  let siteId: number;
  try {
    const site = await api.getSite(slug);
    siteId = site.id;
  } catch {
    return (
      <main className="flex-1 px-10 py-16">
        <p className="text-destructive">Site not found.</p>
      </main>
    );
  }

  return <SiteDetail siteId={siteId} />;
}
