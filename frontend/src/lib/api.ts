const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_URL = typeof window === "undefined" ? process.env.BACKEND_API_URL ?? PUBLIC_API_URL : PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ?? res.statusText;
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type Site = {
  id: number;
  url: string;
  domain: string;
  slug: string | null;
  title: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
  last_crawled_at: string | null;
  last_crawl_status: string | null;
  event_count: number;
  latest_event_id: number | null;
};

export type CrawlJob = {
  id: number;
  site_id: number;
  triggered_by: string;
  status: "pending" | "running" | "completed" | "failed";
  pages_found: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  max_pages: number;
  max_duration_seconds: number;
};

export type CreateSiteResponse = {
  site: Site;
  crawl_job_id: number;
  status: CrawlJob["status"];
};

export type LlmsFile = {
  id: number;
  site_id: number;
  content: string;
  content_hash: string;
  generated_at: string;
};

export type ChangeEvent = {
  id: number;
  site_id: number;
  crawl_job_id: number;
  detected_at: string;
  pages_added: number;
  pages_removed: number;
  pages_modified: number;
  summary: string | null;
  triggered_by: "scheduled" | "manual";
};

export type Monitor = {
  site_id: number;
  interval_hours: number;
  is_active: boolean;
  last_checked_at: string | null;
  next_check_at: string | null;
};

export type MonitorPatch = {
  interval_hours?: number;
  is_active?: boolean;
};

export type PageDataRow = {
  id: number;
  url: string;
  canonical_url: string | null;
  title: string | null;
  description: string | null;
  section: string | null;
  is_optional: boolean;
  status_code: number | null;
  crawled_at: string;
};

export type CrawlJobDetail = {
  crawl_job: CrawlJob;
  pages: PageDataRow[];
};

export const api = {
  createSite: (url: string) =>
    request<CreateSiteResponse>("/sites", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  listSites: () => request<Site[]>("/sites"),

  getSite: (siteId: number | string) => request<Site>(`/sites/${siteId}`),

  listCrawls: (siteId: number) =>
    request<CrawlJob[]>(`/sites/${siteId}/crawls`),

  getCrawl: (siteId: number, crawlId: number) =>
    request<CrawlJobDetail>(`/sites/${siteId}/crawls/${crawlId}`),

  triggerCrawl: (siteId: number) =>
    request<CrawlJob>(`/sites/${siteId}/crawls`, { method: "POST" }),

  getLlms: (siteId: number) => request<LlmsFile>(`/sites/${siteId}/llms`),

  llmsRawUrl: (siteId: number) => `${PUBLIC_API_URL}/sites/${siteId}/llms.txt`,

  listChangeEvents: (siteId: number) =>
    request<ChangeEvent[]>(`/sites/${siteId}/changes`),

  getMonitor: (siteId: number) =>
    request<Monitor>(`/sites/${siteId}/monitor`),

  patchMonitor: (siteId: number, body: MonitorPatch) =>
    request<Monitor>(`/sites/${siteId}/monitor`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteSite: (siteId: number) =>
    request<void>(`/sites/${siteId}`, { method: "DELETE" }),
};
