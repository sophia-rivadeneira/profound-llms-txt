# Profound Interview — llms.txt Generator

## Context
Building a web application for Profound's final round interview. The tool lets users input a website URL and receive a generated llms.txt file (a proposed standard that helps LLMs understand website content). Must be deployed live, with source code on GitHub.

## Architecture

```
Vercel (frontend)              Railway (backend)
┌─────────────────────┐       ┌─────────────────────────┐
│ Next.js              │       │ FastAPI                  │
│ - Tailwind CSS       │──API──│ - httpx + BeautifulSoup  │
│ - shadcn/ui          │ calls │ - Playwright (fallback)  │
│ - Geist font         │       │ - APScheduler            │
│                      │       │ - PostgreSQL (Railway)   │
└─────────────────────┘       └─────────────────────────┘
```

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Strongest language, best crawling libs, async-native |
| Frontend | Next.js + Tailwind + shadcn/ui | Matches Peec's design, comfortable with React |
| Architecture | Separate services | Separation of concerns, clean API, independent scaling |
| Crawler | httpx + BeautifulSoup + Playwright fallback | Full control, async, smart JS detection |
| Concurrency | Async background tasks | API stays responsive, handles multiple users |
| Monitoring | Scheduled re-crawl + manual refresh | Meets "automated" spec, plus user control |
| Database | PostgreSQL | Concurrent writes, relational data, cloud-native |
| Deployment | Vercel + Railway | Best-in-class for each piece, always-on |
| Design | Match Peec brand | Geist font, neutral palette, minimal SaaS aesthetic |

## Database Schema

```sql
sites:       id,
             url UNIQUE,          -- one row per URL; prevents duplicates
             domain,              -- denormalized for "all sites under example.com" queries
             title,               -- llms.txt H1 (site-level, user-editable)
             description,         -- llms.txt blockquote (site-level, user-editable)
             created_at,
             updated_at           -- tracks edits to title/description
crawl_jobs:  id,
             site_id,
             triggered_by,        -- 'initial' | 'scheduled' | 'manual' — every crawl
                                  -- has a trigger source, not just the ones that
                                  -- result in changes. change_events derives its
                                  -- trigger via the crawl_job_id FK.
             status,              -- enum: 'pending' | 'running' | 'completed' | 'failed'
                                  -- CHECK constraint keeps invalid states out at the DB level
             pages_found,
             error_message,       -- NULL on success; populated when status='failed'
                                  -- (timeout, DNS error, robots.txt block, 5xx, etc.)
             started_at,
             completed_at
llms_files:  id, site_id, content, content_hash, generated_at
             -- UNIQUE(site_id): one current file per site, UPDATE in place.
             -- The brief says "updates the llms.txt file" (singular), so the
             -- file is mutable state — not a version archive.
change_events: id,
               site_id,
               crawl_job_id,      -- FK to the crawl that detected this change;
                                  -- makes the monitoring pipeline end-to-end auditable.
                                  -- triggered_by is derived through this FK.
               detected_at,
               old_hash,          -- hash of the file before this change. We don't store
                                  -- the "after" hash because it's always derivable:
                                  -- latest event → llms_files.content_hash;
                                  -- older events → the next event's old_hash.
               pages_added,       -- int: # of new URLs vs previous crawl
               pages_removed,     -- int: # of URLs that disappeared
               pages_modified,    -- int: # of URLs with changed content
               summary            -- short text: "Added /blog/new-post; removed /old-page"
               -- Immutable event stream. Satisfies the brief's "detects changes"
               -- requirement. Users want to see *what changed*, not download
               -- historical files.
monitors:    id,
             site_id UNIQUE,      -- one monitor per site
             interval_hours,      -- re-check frequency (default: 24 = daily)
             is_active,           -- can be paused without deleting the row
             last_checked_at,     -- for display ("last checked X ago")
             next_check_at,       -- indexed; scheduler query is `WHERE next_check_at <= NOW()`
             created_at           -- when monitoring was first enabled
             -- Opt-out model: a monitor row is auto-created (is_active=true)
             -- when a user first generates an llms.txt for a site. Users can
             -- pause it via is_active=false without losing their settings.
             -- Matches the brief's "automated updates" requirement by default.
page_data:   id,
             crawl_job_id,
             url,              -- as crawled
             canonical_url,    -- from <link rel="canonical">, dedupes ?utm params
             title,            -- <title> or og:title → link text in llms.txt
             description,      -- <meta description> or og:description → link description
             section,          -- inferred bucket: "docs" | "blog" | "api" | "marketing" | ...
             is_optional,      -- true = page belongs under spec's `## Optional` section
             status_code,      -- HTTP status: 200, 301, 404... for debug + filtering
             crawled_at,       -- when this specific page was fetched
             UNIQUE(crawl_job_id, url)
```

**Why these fields:** every column earns its place by mapping directly to llms.txt output or supporting change detection. `title` + `description` + `url` + `section` feed the output. `is_optional` populates the spec's `## Optional` section. `canonical_url` dedupes tracking-param variants. `status_code` enables debugging ("why isn't this page in my llms.txt?") and lets us filter non-200 responses. `UNIQUE(crawl_job_id, url)` guards against redirect loops inserting the same URL twice.

**Why no `content_hash` per page:** `change_events.pages_modified` is computed by comparing the stored fields (title, description, section) between the latest and previous crawl. Since those are *exactly* the fields that appear in the llms.txt output, field comparison is both simpler and more semantically correct than hashing — a body-level change that doesn't affect any of those fields wouldn't affect the output either.

### Indexes

```sql
CREATE INDEX idx_monitors_next_check       ON monitors(next_check_at) WHERE is_active;
CREATE INDEX idx_page_data_crawl           ON page_data(crawl_job_id);
CREATE INDEX idx_page_data_url             ON page_data(url);
CREATE INDEX idx_crawl_jobs_site           ON crawl_jobs(site_id);
CREATE INDEX idx_change_events_site_time   ON change_events(site_id, detected_at DESC);
```

**Why each one:**
- **`monitors.next_check_at` (partial on `is_active`)** — the scheduler runs `WHERE next_check_at <= NOW() AND is_active` on every tick. Partial index excludes paused monitors from the index entirely.
- **`page_data.crawl_job_id`** — every generation reads all pages for a crawl; without this it's a table scan.
- **`page_data.url`** — powers cross-crawl diffs (joining current crawl's `/pricing` row to previous crawl's `/pricing` row).
- **`crawl_jobs.site_id`** — supports "show crawl history for this site."
- **`change_events(site_id, detected_at DESC)`** — composite index serves the common timeline query "show this site's changes, newest first" from the index alone.

### Cascade delete behavior

All foreign keys use `ON DELETE CASCADE`, so removing a site cleans up its entire graph:

```
sites (deleted)
  ├─→ crawl_jobs → page_data
  ├─→ llms_files
  ├─→ change_events
  └─→ monitors
```

Prevents orphaned rows and makes "forget this site" a single `DELETE FROM sites WHERE id = X` operation.

## API Endpoints

```
# Sites (primary resource)
POST    /api/sites                      Create/find a site by URL, kick off initial crawl
                                        Body:    {url}
                                        Returns: {site_id, crawl_job_id}
GET     /api/sites                      List all sites (dashboard view)
GET     /api/sites/{id}                 Site details: url, title, description,
                                        latest crawl status, last change
PATCH   /api/sites/{id}                 Edit user-editable fields
                                        Body:    {title?, description?}
DELETE  /api/sites/{id}                 Remove site (cascades to crawls, pages,
                                        files, events, monitor)

# Crawls
POST    /api/sites/{id}/crawls          Trigger a new crawl (manual refresh)
                                        Returns: {crawl_job_id}
GET     /api/sites/{id}/crawls          Crawl history for a site
GET     /api/crawls/{job_id}            Status/progress for a specific crawl
                                        (polling endpoint)
                                        Returns: {status, pages_found,
                                                  error_message?, started_at,
                                                  completed_at?}

# llms.txt file (two endpoints for two audiences)
GET     /api/sites/{id}/llms            JSON wrapper for the frontend
                                        Returns: {content, content_hash, generated_at}
GET     /api/sites/{id}/llms.txt        Raw markdown (Content-Type: text/plain)
                                        For direct downloads and `curl | tee` usage

# Change events (monitoring timeline)
GET     /api/sites/{id}/changes         List change_events newest-first
                                        Returns: [{detected_at, pages_added,
                                                   pages_removed, pages_modified,
                                                   summary, triggered_by}, ...]

# Monitor settings
GET     /api/sites/{id}/monitor         Current settings
                                        Returns: {interval_hours, is_active,
                                                  last_checked_at, next_check_at}
PATCH   /api/sites/{id}/monitor         Pause/resume, change interval
                                        Body:    {interval_hours?, is_active?}
```

**Design notes:**
- **Nouns, not verbs.** Every URL is a resource; the HTTP method names the action. `POST /api/sites/{id}/crawls` replaces the earlier `POST /api/refresh/{site_id}`.
- **Nested under `/api/sites/{id}`.** Sites are the primary resource; everything else (crawls, llms file, changes, monitor) belongs to a site. The only top-level exception is `GET /api/crawls/{job_id}` for polling — the frontend already has the job id and doesn't need the site context to ask "is it done yet?"
- **Two file endpoints.** `/llms` returns JSON so the frontend can display metadata alongside the content; `/llms.txt` returns raw markdown so `curl` and browser downloads work naturally.
- **Monitor is PATCH-only**, not POST/DELETE. Monitoring is auto-created opt-out, so you never "create" or "destroy" a monitor — you toggle `is_active` and adjust `interval_hours`. Settings survive across pauses.
- **No version-history endpoint.** The change_events timeline replaces it; users see "what changed and when," not "download my file from three weeks ago."

## Implementation Phases

### Phase 1: Project Setup

**Repo layout** — monorepo with two top-level folders:
```
profound-website/
├── backend/
│   ├── pyproject.toml          # uv-managed deps
│   ├── uv.lock
│   ├── alembic.ini             # top-level Alembic config
│   ├── alembic/
│   │   ├── env.py              # how Alembic connects + finds models
│   │   └── versions/           # generated migration files
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, router mounting
│   │   ├── config.py           # pydantic-settings Settings class
│   │   ├── db/
│   │   │   ├── base.py         # DeclarativeBase (Alembic imports this)
│   │   │   └── session.py      # async engine + sessionmaker + get_db
│   │   ├── models/             # SQLAlchemy models, one file per table
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── routers/            # FastAPI route modules
│   │   └── services/           # crawler, llms.txt generator, scheduler
│   └── tests/
├── frontend/                   # Next.js app (own package.json)
└── README.md
```

**Backend setup**
- [ ] Install `uv` (single binary; `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] `uv init backend && cd backend`
- [ ] Add runtime deps:
  - `fastapi` — web framework
  - `uvicorn[standard]` — ASGI server
  - `sqlalchemy` — ORM + query builder (2.0 async style)
  - `asyncpg` — async Postgres driver
  - `alembic` — migrations
  - `pydantic-settings` — typed env config (reads `.env` natively)
  - `httpx` — async HTTP client for the crawler
  - `beautifulsoup4` — HTML parsing
- [ ] Add dev deps: `pytest`, `pytest-asyncio`
- [ ] Create `app/config.py` with a `Settings` class: `DATABASE_URL`, `CORS_ORIGINS`, `ENV`
- [ ] Create `app/db/base.py` (DeclarativeBase) and `app/db/session.py` (async engine + `get_db` dependency)
- [ ] Create `app/main.py`:
  - Instantiate `FastAPI()`
  - Add `CORSMiddleware` — origins from settings, `allow_credentials=False`, methods `["GET", "POST", "PATCH", "DELETE"]`
  - Mount routers from `app/routers/`
  - Health check at `GET /health`
- [ ] Write SQLAlchemy models in `app/models/` matching the schema above (one file per table, imported into `app/models/__init__.py` so Alembic sees them)
- [ ] Initialize Alembic: `alembic init alembic`, point `env.py` at `app.db.base.Base.metadata`, read `DATABASE_URL` from settings
- [ ] Generate first migration: `alembic revision --autogenerate -m "initial schema"`
- [ ] Run `alembic upgrade head` against local Postgres to verify

**Frontend setup**
- [ ] `npx create-next-app@latest frontend --typescript --tailwind --app`
- [ ] Install shadcn/ui: `npx shadcn@latest init` (pick Neutral palette to match Peec)
- [ ] Add Geist font via `next/font/google` in `app/layout.tsx`
- [ ] Create `lib/api.ts` — typed fetch wrapper pointing at `NEXT_PUBLIC_API_URL`
- [ ] Add `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`

**Local Postgres**
- [ ] Run Postgres via Docker: `docker run --name profound-db -e POSTGRES_PASSWORD=dev -p 5432:5432 -d postgres:16`
- [ ] Set `DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost:5432/profound` in `backend/.env`

**Repo hygiene**
- [ ] `git init` at project root
- [ ] `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `node_modules/`, `.next/`, `uv.lock` (keep — it's the lockfile)
- [ ] Push to GitHub
- [ ] README stub with "run locally" instructions (fill in during Phase 6)

### Phase 2: Core Crawler

**Design decisions** (interview-defensible rationale in DEVLOG):
- URL discovery: sitemap-first (`/sitemap.xml`, also read from `robots.txt`), link-crawl fallback when no sitemap exists.
- `robots.txt`: respect it via stdlib `urllib.robotparser`. Check before fetching every URL.
- URL normalization: strip fragments, normalize trailing slashes, lowercase scheme/host, resolve redirects, same registered-domain enforcement (subdomains allowed).
- Crawl limits: `max_pages=200`, `max_depth=5`, `max_duration_seconds=120` as defaults.
- Rate limiting: `httpx.AsyncClient` with a per-domain semaphore (5 concurrent), 100ms delay between requests, identifiable User-Agent (`ProfoundLlmsTxtBot/0.1 (+<github-url>)`).
- Playwright fallback: trigger when the httpx response looks like a JS shell (empty body, `<div id="root">`/`<div id="__next">` with no content, or <500 bytes of visible text).
- Background task orchestration: FastAPI `BackgroundTasks` — built in, sufficient for take-home scope, avoids Celery/arq/Redis complexity.
- Error handling: per-URL exceptions are caught and recorded to `PageData.status_code`; unhandled exceptions mark the `CrawlJob.status='failed'` with `error_message`. No per-page retries in v1.
- `POST /sites` is immediate: creates the `Site` row *and* kicks off the initial `CrawlJob` in the background, returning `{site_id, crawl_job_id, status}`. Frontend polls `GET /sites/{id}/crawls/{crawl_job_id}` for progress.

**Deliverables:**
- [ ] Add deps: `httpx`, `beautifulsoup4`, `lxml`, `playwright`
- [ ] `playwright install chromium` (installs the browser binary)
- [ ] `app/services/crawler.py` — async `Crawler` class
  - [ ] `robots.txt` check via `urllib.robotparser`
  - [ ] `sitemap.xml` discovery + parsing (also check `robots.txt` for sitemap locations)
  - [ ] URL normalization helpers + same-registered-domain guard
  - [ ] `httpx.AsyncClient` with semaphore, delay, custom User-Agent
  - [ ] BFS link extraction respecting `max_pages` / `max_depth` / `max_duration`
  - [ ] Metadata extraction: `<title>`, `<meta name="description">`, `<meta property="og:*">`, `<link rel="canonical">`, `<h1>`
  - [ ] Playwright fallback trigger via the JS-shell heuristic
- [ ] `app/services/playwright_fetcher.py` — async Playwright wrapper that returns rendered HTML for a single URL
- [ ] `app/schemas/` — Pydantic request/response models for `Site`, `CrawlJob`, `PageData`
- [ ] `app/routers/sites.py` — `POST /sites` (creates + triggers crawl), `GET /sites/{id}`
- [ ] `app/routers/crawls.py` — `GET /sites/{id}/crawls/{crawl_id}` (status polling)
- [ ] Wire routers into `app/main.py`
- [ ] Tests: fixture HTML pages covering sitemap parsing, link extraction, URL normalization, metadata extraction, limit enforcement, robots.txt respect

**Explicitly deferred (not in scope for Phase 2):**
- Authentication / user accounts.
- Retry-with-backoff for transient errors (add only if encountered in testing).
- Incremental re-crawls — full re-crawls only. Change detection is Phase 5.
- Sitemap index files (sitemaps of sitemaps) — add only if trivial.
- Section classification (docs / blog / API) — Phase 3, belongs with llms.txt generation.

### Phase 3: llms.txt Generation

**Design decisions** (interview-defensible rationale in DEVLOG):
- Section classification pipeline: C → A → B. User-configured rules first, URL path pattern matching second (`/docs/*` → Documentation, `/blog/*` → Blog, etc.), LLM fallback third for unmatched pages.
- LLM integration: single Claude Haiku call per crawl generates site summary (blockquote) + classifies remaining unmatched pages. Keeps costs low, deterministic path handles the common case.
- llms.txt spec compliance: H1 (site name from `Site.title`), blockquote (LLM-generated summary), H2-delimited sections with `- [title](url): description` links, `## Optional` section for blog/changelog/legal.
- User edit support: users can edit summary and section assignments after generation. Re-crawl preserves edits unless the underlying content changed (dual-column tracking: `summary` + `summary_generated`). If LLM produces a different summary on re-crawl, user edit is stale and gets overwritten.
- Change detection: diff new llms.txt output against previous `content_hash`. Log a `change_event` row when different.
- Generation trigger: automatic after every completed crawl (initial, manual, or scheduled re-crawl). Generation itself is a fast post-crawl step; the LLM call adds ~1-2s.

**Deliverables:**
- [ ] Add dep: `anthropic` (Claude API client)
- [ ] `app/services/classifier.py` — section classification pipeline
  - [ ] Default URL path pattern rules (docs, blog, api, guides, changelog, legal, etc.)
  - [ ] User-override lookup from site config
  - [ ] LLM fallback for unmatched pages (Claude Haiku)
- [ ] `app/services/generator.py` — llms.txt builder
  - [ ] Assemble markdown per spec from classified pages
  - [ ] LLM call for site summary generation
  - [ ] Dual-column edit tracking (`summary` / `summary_generated`)
  - [ ] Content hashing and change detection vs previous version
  - [ ] Create/update `llms_files` row and `change_events` row
- [ ] `app/routers/llms.py` — endpoints
  - [ ] `GET /sites/{id}/llms` — JSON response with content + metadata
  - [ ] `GET /sites/{id}/llms.txt` — raw markdown (text/plain)
- [ ] Update `app/services/crawler.py` — call generator after crawl completes
- [ ] Update schemas: `LlmsFileResponse`
- [ ] Tests: section classification rules, llms.txt output format, change detection, edit preservation
- [ ] Senior engineer review: run review agent, fix all issues, re-run tests

### Phase 4: Frontend UI
- [ ] Landing page with URL input
- [ ] Crawl progress/status view
- [ ] llms.txt preview with copy/download
- [ ] Monitoring dashboard with version diffs
- [ ] Senior engineer review: run review agent, fix all issues, re-run tests

### Phase 5: Monitoring System
- [ ] APScheduler integration for periodic re-crawls
- [ ] Content diffing and change detection
- [ ] Version history storage and display
- [ ] Manual refresh endpoint
- [ ] Senior engineer review: run review agent, fix all issues, re-run tests

### Phase 6: Deployment & Polish
- [ ] Deploy frontend to Vercel
- [ ] Deploy backend to Railway (Docker for Playwright)
- [ ] Set up PostgreSQL on Railway
- [ ] README with setup/deployment docs
- [ ] Screenshots/demo video

## Verification
- Test crawling on diverse sites: static (blog), server-rendered (Next.js docs), JS-heavy (SPA)
- Test concurrent crawl submissions
- Test monitoring detects changes
- Test Playwright fallback triggers on JS-rendered sites
- Verify llms.txt output conforms to spec at llmstxt.org
