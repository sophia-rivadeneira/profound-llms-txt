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

**Design decisions** (interview-defensible rationale in DEVLOG):
- Route structure: Next.js App Router, multi-page. `/` is the unified landing + dashboard (URL input + table of previously-generated sites). `/sites/[id]` is the site detail view. No separate `/sites` index — having one page makes the tool feel "real" on first visit.
- Data fetching: **TanStack Query** for all server state. Polling the crawl status endpoint while `pending`/`running`, cache invalidation on successful mutations (edit summary, trigger re-crawl, monitor settings).
- Component library: **shadcn/ui** with Neutral palette as-is, Geist font. Visual direction pulled from tryprofound.com (Profound's actual brand), not peec.ai. Minimal custom CSS.
- Crawl progress UX: live `pages_found` counter from the existing backend field, updated via TanStack Query polling at 2s intervals. No streaming log — the counter is enough.
- Change notifications: **passive / pull-based**. localStorage tracks `lastSeenEventId` per site. Dashboard rows with unseen changes show a badge; the site detail page shows a banner with a "Review" button that scrolls to and auto-expands the unread change events in the timeline. Unread entries get a subtle background tint. No auth means no server-side "seen" state.
- Change visualization: **structured change timeline**, not a side-by-side diff. Each event shows counts (`+N -N ~N`), expandable to reveal specific pages added/removed/modified. Rejected side-by-side because users of an llms.txt tool want to know *what changed and whether they care*, not parse two walls of markdown.
- Editing scope: summary-only in Phase 4. Section re-assignment (drag-and-drop) is deferred — the dual-column edit tracking we built in Phase 3 supports it, but the UI is disproportionate work for Phase 4.
- Backend tweak: `POST /sites` returns the existing site id on duplicate instead of a bare 409, so the frontend can always POST and navigate to the returned id.

**Deliverables:**
- [ ] `frontend/` — Next.js App Router scaffold (already exists from Phase 1)
- [ ] Install shadcn/ui components: `button`, `input`, `card`, `table`, `dialog`, `badge`, `separator`, `textarea`
- [ ] `lib/api.ts` — typed fetch wrapper + TanStack Query setup
- [ ] `lib/seen.ts` — localStorage helpers for tracking `lastSeenEventId` per site
- [ ] `app/page.tsx` — landing + dashboard: URL input, search, table of generated sites with "new changes" badges
- [ ] `app/sites/[id]/page.tsx` — site detail view
  - [ ] Site header (domain, title, generated-at)
  - [ ] Current llms.txt preview with copy + download buttons
  - [ ] Editable summary field (inline edit, save via PATCH)
  - [ ] Pages grouped by section (read-only list)
  - [ ] Change timeline (collapsible events, unread banner, review-and-expand flow)
  - [ ] Monitor settings panel (interval, pause toggle)
- [ ] Loading / error states for every query
- [ ] Backend: `PATCH /sites/{id}` endpoint for summary editing
- [ ] Backend: `POST /sites` returns 200 with existing site id on duplicate (was 409)
- [ ] Test on diverse live sites: static blog, server-rendered docs, SPA
- [ ] Senior engineer review: run review agent, fix all issues

### Phase 5: Monitoring System

**Already shipped in earlier phases (call out in interview):**
- Change detection (`change_events` insert in `generator._compute_change_event`) — Phase 3.
- Manual refresh endpoint (`POST /sites/{id}/crawls` with 409 concurrent guard) — Phase 2.
- Change timeline UI (`change-timeline.tsx`, "unread" banner, localStorage `lastSeenEventId`) — Phase 4.

What's left for Phase 5 is the actual *automated* loop: a scheduler, monitor lifecycle, the endpoints the frontend monitor panel needs, and a small fix to stop the timeline from filling up with no-op events once monitoring fires every day.

**Design decisions** (interview-defensible rationale in DEVLOG):

- **Hand-rolled in-process `asyncio` loop, not APScheduler.** ~20 lines, started from FastAPI's `lifespan` hook and cancelled cleanly on shutdown. No new dependency, no library magic to defend in front of the panel. Exception isolation via `try/except` inside the loop body so a bad tick doesn't kill the loop forever. Same instinct as Phase 2's `BackgroundTasks` decision — match the tool to the scope, push complexity out of the demo. What APScheduler would buy us (cron expressions, persistent jobs, listeners) we don't need.

- **No message queue, so the timer and the worker live in the same process.** Phase 2 deliberately punted on a queue. Adding a separate scheduler service (Railway cron, APScheduler in its own container) would re-introduce the producer/consumer split we already chose not to pay for. The in-process loop reuses the existing `_run_crawl_in_background` helper as-is — same code path the manual `POST /crawls` already uses, called from a new place.

- **Tick cadence: every 5 minutes.** Each tick scans `monitors WHERE is_active AND next_check_at <= NOW()` and dispatches a scheduled crawl per due row. With `interval_hours` defaulting to 24, a 5-minute tick is way more resolution than any user-pickable interval needs, and the DB cost is rounding error (one indexed query, ~12 times per hour, returning 0 rows on the vast majority of ticks). The partial index on `(next_check_at) WHERE is_active` skips paused monitors entirely. Note: 5 minutes is how often the loop *checks the table*, not how often any site is re-crawled — re-crawls happen at each site's `interval_hours` cadence (default 24h).

- **Multi-worker safety from day one: `SELECT ... FOR UPDATE SKIP LOCKED`.** Two extra clauses on the due-monitors query, no extra deps. Within the locking transaction, the tick advances `next_check_at` for each claimed row before committing — so even if Railway scaled to multiple uvicorn workers tomorrow, two scheduler loops can't double-fire the same monitor. Pre-empts the obvious "what if you scale workers?" interview question. Documented in DEVLOG so the interviewer hears the reasoning even if they don't ask.

- **Opt-out monitor creation.** A `Monitor` row is auto-created (`is_active=true`, `interval_hours=24`, `next_check_at = now + 24h`) only on the *new-site* branch of `POST /sites`, not on the duplicate-return path — duplicate sites already have their monitor.

- **Every completed crawl bumps `last_checked_at` and `next_check_at`**, regardless of trigger source (`initial`, `manual`, `scheduled`). A manual refresh resets the schedule clock so the scheduler doesn't fire a redundant crawl five minutes later. The thing the schedule is preventing is *stale data* — a manual refresh just made the data fresh, so resetting the clock is consistent with what `next_check_at` actually means.

- **Failures advance the schedule normally; auto-pause after 3 consecutive failures.** Two new columns on `monitors`: `consecutive_failures` (int, default 0) and `paused_reason` (nullable: `null | "user" | "failures"`). Each failed crawl increments `consecutive_failures`, advances `next_check_at` by the normal interval, and — if the count hits 3 — also sets `is_active=false`, `paused_reason="failures"`. Each successful crawl resets `consecutive_failures` to 0. The frontend monitor settings panel branches on `paused_reason` and renders a warning banner ("Monitoring auto-paused after 3 failed checks") instead of the normal pause-toggle when the value is `"failures"`. Resume from auto-pause sets `next_check_at = now` so the next tick picks it back up immediately. Caps wasted crawl budget for permanently broken sites at 3 attempts; the rest of the time it behaves exactly like the simple bump-and-retry path.

- **ChangeEvent dedup gate.** Today the generator emits a `ChangeEvent` after *every* crawl, including the first one (where `old_hash is None`) and unchanged re-crawls. Once daily monitoring runs, that floods the timeline with "llms.txt content changed" rows. Fix: gate `ChangeEvent` insertion on `old_hash is not None AND old_hash != new_hash`. The hash check is the real signal — counts can be zero on a meaningful re-section without being misleading. No special "initial generation" event on first crawl — the change timeline is for *changes*, and the site creation timestamp + first `crawl_job` already record when monitoring began.

- **`triggered_by` propagates to the change timeline.** Scheduled crawls get `triggered_by="scheduled"` so the frontend can label each event ("automatic check found 2 new pages" vs "you manually refreshed").

- **Time zones: everything UTC.** `next_check_at` is timezone-aware UTC; the loop compares against `datetime.now(timezone.utc)`. Interval math uses `timedelta(hours=...)`.

**Deliverables:**

- [ ] Alembic migration: add `consecutive_failures int default 0` and `paused_reason text null` to `monitors`
- [ ] `app/services/scheduler.py`
  - [ ] ~20-line `asyncio` loop with `try/except` exception isolation and `await asyncio.sleep(300)` between ticks
  - [ ] `_tick()` — `SELECT FROM monitors WHERE is_active AND next_check_at <= NOW() FOR UPDATE SKIP LOCKED`, advance `next_check_at` per claimed row inside the transaction, commit, then dispatch each crawl via the existing `_run_crawl_in_background` helper
  - [ ] `start()` / `stop()` helpers; `stop()` cancels the task and awaits the `CancelledError`
- [ ] Wire scheduler into `app/main.py` via `lifespan` (start on app boot, shutdown on exit)
- [ ] `app/routers/sites.py` — auto-create `Monitor` row on the new-site branch of `create_site` (not on `_response_for_existing_site`)
- [ ] `app/services/crawler.py` (or wherever `run_crawl` finalizes) — after every crawl completes:
  - [ ] On success: set `last_checked_at = now`, `next_check_at = now + interval_hours`, `consecutive_failures = 0`
  - [ ] On failure: same `last_checked_at` / `next_check_at` update, increment `consecutive_failures`, and if it hits 3 also set `is_active=false`, `paused_reason="failures"`
  - [ ] Skip silently if no monitor row exists (defensive — shouldn't happen post-Phase-5)
- [ ] `app/services/generator.py` — gate `ChangeEvent` creation on `old_hash is not None and old_hash != new_hash`. Update Phase 3 tests that assumed an event is always created.
- [ ] `app/routers/monitors.py` — new router
  - [ ] `GET /sites/{id}/monitor` → `{interval_hours, is_active, paused_reason, last_checked_at, next_check_at, consecutive_failures}`
  - [ ] `PATCH /sites/{id}/monitor` → body `{interval_hours?, is_active?}`
    - [ ] On `interval_hours` change: recompute `next_check_at = last_checked_at + interval_hours` (or `now + interval` if never checked)
    - [ ] On `is_active=true` after a pause: set `next_check_at = now`, clear `paused_reason`, reset `consecutive_failures = 0`
    - [ ] On `is_active=false`: set `paused_reason="user"`
    - [ ] Validation: `interval_hours` between 1 and 168 (one week), 422 otherwise
- [ ] `GET /sites/{id}/changes` returning the timeline newest-first, joined with `crawl_jobs.triggered_by` so the frontend can label each event. (Phase 4's `change-timeline.tsx` likely already calls this — verify before duplicating.)
- [ ] Schemas: `MonitorResponse`, `MonitorPatch`, `ChangeEventResponse` (with `triggered_by`)
- [ ] Wire new routers into `app/main.py`
- [ ] Frontend: monitor settings panel branches on `paused_reason`
  - [ ] If `paused_reason === "failures"`: render warning banner ("Monitoring auto-paused after 3 failed checks") with a Resume button
  - [ ] If `paused_reason === "user"` or `null`: render the normal pause/resume toggle + interval input
- [ ] Tests:
  - [ ] `_tick()` selects only `is_active AND next_check_at <= now` monitors
  - [ ] `_tick()` advances `next_check_at` inside the transaction (so a second concurrent tick wouldn't see the row)
  - [ ] `_tick()` gracefully handles a raised exception without killing the loop
  - [ ] Monitor auto-created on first `POST /sites`, not on duplicate POSTs
  - [ ] `last_checked_at` / `next_check_at` updated after success and after failure
  - [ ] `consecutive_failures` increments on failure, resets on success
  - [ ] 3 consecutive failures flips `is_active=false` and sets `paused_reason="failures"`
  - [ ] `ChangeEvent` not created on first crawl; not created on unchanged re-crawl; *is* created when `old_hash != new_hash`
  - [ ] `PATCH /monitor` interval validation (rejects 0, rejects 999)
  - [ ] `PATCH /monitor` resume from auto-pause clears `paused_reason` and resets `consecutive_failures`
- [ ] Manual smoke test: set a site's `interval_hours=1`, force `next_check_at` into the past, watch the next tick fire a scheduled crawl in the logs
- [ ] Senior engineer review: run review agent on all Phase 5 code, fix all issues, re-run tests

**Explicitly deferred (not in scope for Phase 5):**
- Email / webhook / Slack notifications on change events — already in Future Work.
- Exponential backoff between failed retries — auto-pause already caps wasted budget; backoff would be redundant complexity.
- Per-site "force re-check now" button distinct from the existing manual refresh — `POST /crawls` already covers this.
- Adaptive intervals (back off on unchanged sites, speed up on flaky ones).
- Switching to a real task queue (arq) — same threshold reasoning as Phase 2; would unlock durable jobs and retries but isn't needed at take-home scale.

### Phase 6: Code Quality Pass

Final sweep before deployment focused on **cleanliness, efficiency, and scalability** — the "at large" view that per-phase review misses. Running-system QA (fresh-clone setup walk, error-path behavior, logging quality, demo readiness) is handled manually by the author and explicitly out of scope for this phase; every item below produces a code change, not a runbook entry.

**Design decisions** (interview-defensible rationale in DEVLOG):

- **Scope is code quality, not behavioral QA.** Per-phase review already caught single-file issues. This phase targets cross-phase drift, seams between phases, and "at large" code quality that's only visible when you zoom out across the whole repo.
- **Test philosophy: functionality, not appearance.** Tests must verify observable behavior (button click → API call → UI updates) not implementation details (CSS classes, call counts, exact mock arguments). Audit every existing test against this rule and delete/rewrite the ones that fail.
- **Env var organization gets its own exercise.** Config drift across phases is a known pain point — auditing `config.py`, `.env`, `.env.example`, and frontend `NEXT_PUBLIC_*` usage in one pass is cheaper than hunting them as they surface.
- **Don't over-abstract.** Extract duplication only for patterns that appear 3+ times. A helper for "used once" is just indirection.

**Deliverables:**

*Cleanliness:*
- [ ] **Router thinness audit** — every router in `app/routers/` should parse input, call a service, serialize output. Move business logic into `app/services/` where it leaked in.
- [ ] **Duplication sweep** — extract repeated patterns (find-site-or-404, response envelopes, error mapping) into shared helpers. 3+ uses only.
- [ ] **Dead code & unused deps** — remove unreferenced helpers, commented experiments, and entries in `pyproject.toml` / `package.json` that nothing imports.
- [ ] **Naming consistency across phases** — rename drifted identifiers so related things have related names (e.g. crawl dispatch paths from Phase 2 vs Phase 5).
- [ ] **Schema/model hygiene** — Pydantic response shapes consistent across routers (field names, optionality, datetime serialization). No SQLAlchemy models leaking into responses.
- [ ] **Idiomatic patterns sweep** — rewrite code that's written in a verbose / Java-ish style into the native idiom of the language it's in. Backend: list/dict comprehensions instead of `for`-loop-plus-`append`, ternaries instead of 4-line `if/else` assignments, early returns instead of nested conditionals, f-strings instead of concatenation, `dict.get(k, default)` instead of `if k in dict`. Frontend: `.map()` in JSX, optional chaining (`?.`), nullish coalescing (`??`), ternary JSX instead of `if` blocks. Goal is the code reads like someone fluent wrote it, not translated from another language.
- [ ] **General syntax cleanup** — run the formatters and linters end-to-end and fix everything they flag. Backend: `ruff format` + `ruff check --fix` across `app/` and `tests/`, plus a `mypy` pass if configured. Frontend: `prettier --write` + `eslint --fix` + `tsc --noEmit`. Then a manual pass for things formatters miss: consistent import ordering, no trailing whitespace, consistent quote style, line length, trailing commas in multi-line literals, blank-line conventions between top-level defs. Single commit so the diff is easy to skim.
- [ ] **Env var / config audit** — cross-check `backend/app/config.py` against `backend/.env` and `backend/.env.example`; same for `frontend/.env.local` and `NEXT_PUBLIC_*` usage. Remove unused vars, add missing ones, normalize naming, verify the frontend/backend split is correct.

*Efficiency:*
- [ ] **Async correctness sweep** — grep for sync I/O inside `async def` paths (`requests`, sync file reads, sync DB calls hidden in helpers). Fix any found.
- [ ] **N+1 sweep** — trace the queries behind `GET /api/sites` (dashboard) and `GET /api/sites/{id}` (detail). Add `selectinload` / `joinedload` for relationships always rendered together.
- [ ] **Over-fetching check** — any route loading full rows when 2–3 columns would do? Select only what's used.
- [ ] **Frontend query-cache scope** — audit TanStack Query `invalidateQueries` calls. Narrow any nuclear invalidations to the specific keys affected.

*Scalability:*
- [ ] **Orphaned `running` crawls on restart** — add a startup reconciliation in `lifespan` that flips stale `running` crawl_jobs to `failed` with an explanatory `error_message`. Answers the "what if the process crashes mid-crawl" interview question with ~10 lines.
- [ ] **Unbounded list endpoints** — `GET /api/sites` returns everything today. Either paginate or document the take-home-scale decision in DEVLOG.
- [ ] **Crawler concurrency bounds** — verify the per-domain semaphore is process-global, not per-crawl. Two concurrent crawls of the same domain should not double the load.
- [ ] **Scheduler lock correctness** — re-read the `FOR UPDATE SKIP LOCKED` path and confirm `next_check_at` advances inside the same transaction.
- [ ] **Index verification** — every index listed in the PLAN.md schema section actually exists in an Alembic migration.

*Schema integrity:*
- [ ] **Column usage audit** — for every column on every model, confirm it's both *written* and *read* somewhere in the codebase. Flag any column that's set but never read (dead data) or read but never set (silent nulls).
- [ ] **Silent-drop check** — walk every `POST` / `PATCH` handler and confirm that no request field is accepted but then dropped before the DB write. Pydantic should reject unknown fields, but verify for each schema.
- [ ] **Response completeness** — every column the frontend needs should appear in the corresponding Pydantic response schema. No "I forgot to add this field" gaps.
- [ ] **Migration vs model reconciliation** — run `alembic check` (or diff `--autogenerate` output) to confirm the current models match what the migrations actually produced. No drift.
- [ ] **Cascade behavior** — confirm `ON DELETE CASCADE` is set on every FK listed in the PLAN.md schema section. A `DELETE FROM sites` should clean the full graph.
- [ ] **Enum / CHECK constraint coverage** — every value the code writes into `triggered_by`, `status`, `paused_reason` etc. is actually allowed by the DB-level constraint.

*Test intentionality:*
- [ ] **Test audit** — for each existing test, ask: "if I refactored the implementation without changing behavior, would this still pass?" If no, rewrite or delete. Drop tests that assert on CSS, exact call counts, or mock internals.
- [ ] Add tests only for behaviors newly uncovered during cleanup (e.g. orphaned-crawl reconciliation).

*Narrative sync:*
- [ ] **DEVLOG update** — note scalability decisions made during this phase (pagination deferral, orphaned-crawl handling, concurrency bounds).
- [ ] **PLAN.md checkbox sync** — mark earlier phases accurately so the final state reflects what actually shipped.
- [ ] **Senior engineer review** — run review agent on all Phase 6 changes, fix issues, re-run tests.

**Explicitly out of scope:**
- Running-system QA: fresh-clone setup walk, error-path behavior, logging quality, demo readiness. Handled manually by the author.
- README / local-run docs — Phase 7.
- New features, design changes, or scope additions of any kind.

### Phase 7: Deployment & Polish
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

## Future Work / Stretch Goals

Bullets below are presentation-ready — each one is a thing I considered, has a concrete reason it was deferred, and a note on how I'd implement it with more time.

**LLM-powered enrichment**
- *What:* Claude Haiku fallback for section classification when URL patterns miss, plus polished summary generation instead of using the raw meta description.
- *Why deferred:* A deployed demo with an LLM dependency adds an API key to manage, per-request cost, latency on the critical path, and a new failure mode right before the interview. Deterministic generation is boring but defensible.
- *How:* Add `ANTHROPIC_API_KEY` to backend env, wrap calls in a try/except that falls back to the current behavior on any error, cache responses by content hash so re-crawls don't re-pay.

**Active change notifications (email / webhook / Slack)**
- *What:* When a change event is detected, push it to the user instead of waiting for them to revisit the dashboard.
- *Why deferred:* No auth means no stable identity to send to. Also touches deliverability, unsubscribe flows, and a worker for outbound delivery — all scope creep.
- *How:* Add a `notifications` table keyed by site id + destination (email / webhook url / Slack channel), fire on `ChangeEvent` insert, use Resend for email and raw POST for webhooks. Slack is just a webhook with a formatted payload.

**Section editing UI (drag-and-drop)**
- *What:* Let users re-classify pages into different sections, rename sections, or hide pages from the generated file.
- *Why deferred:* The dual-column edit-tracking we built in Phase 3 already supports preserving manual overrides, but building the DnD UI and the override-persistence rules is disproportionate work for Phase 4.
- *How:* `dnd-kit` for the drag interaction, a `PageOverride` table storing `(page_url, section_override, hidden)`, generator merges overrides at markdown-build time.

**Full version history + side-by-side diff**
- *What:* Archive every generated llms.txt and render a git-style side-by-side diff between any two versions.
- *Why deferred:* Rejected in favor of the structured change timeline — users of this tool want "what changed that I care about," not two walls of markdown to parse. But a power-user "show me the raw diff" view would still be nice.
- *How:* Store each generated `content` snapshot in a `llms_file_versions` table, render with `react-diff-viewer-continued` behind a "View raw diff" toggle on the timeline event.

**Authentication & multi-user dashboards**
- *What:* User accounts, per-user site lists, team sharing.
- *Why deferred:* Explicitly out of scope for the take-home — the assignment is a public utility, not a SaaS product.
- *How:* Clerk or Auth.js on the frontend, `user_id` foreign key on `sites`, row-level scoping in every query.

**Distributed crawler**
- *What:* Move crawling off `BackgroundTasks` onto a real queue (arq or Celery) with worker pods so larger sites don't block the API process.
- *Why deferred:* Adds Redis, a worker deployment, and failure-mode debugging — all for a demo that will crawl sites in the 50–200 page range. `BackgroundTasks` is the right call at this scale and easier to defend in the interview.
- *How:* arq is the lightest lift — Redis URL in config, `@arq.worker` wrapping `run_crawl`, worker as a second Railway service.

**Retry with exponential backoff**
- *What:* Transient 5xx / timeout errors during a crawl currently mark the page as failed. Retrying 2–3 times with backoff would catch flaky responses.
- *Why deferred:* Wasn't load-bearing for the demo path — real sites rarely flake during a single crawl window.
- *How:* `tenacity` retry decorator around the `httpx` and Playwright fetches, capped at ~3 attempts with jitter.

**Hybrid sitemap + link-graph crawling**
- *What:* Current crawler is pure link-following from the seed URL. Consuming `sitemap.xml` when available would find pages that aren't linked from the homepage (e.g. old blog posts, deep docs).
- *Why deferred:* Most demo sites are small enough that link-following reaches everything relevant.
- *How:* Before the BFS crawl, fetch `/sitemap.xml` and `/sitemap_index.xml`, parse with `lxml`, seed the frontier with every URL on the same host.

**TTL-based robots.txt cache**
- *What:* Robots.txt is fetched once per crawl. For long-running monitors, we should refetch periodically in case the site changes its rules.
- *Why deferred:* Monitoring isn't shipping in Phase 4 anyway, and a fresh fetch per crawl is correct if slower.
- *How:* Cache keyed by host with a 24h TTL, invalidated at the start of each monitor cycle.

**Lazy-loaded content handling**
- *What:* Sites that load content on scroll (infinite-scroll blogs, JS-rendered catalogs) currently only return what's in the initial viewport.
- *Why deferred:* Playwright already handles the dominant JS-rendering case, and scroll automation is site-specific and fragile.
- *How:* In the Playwright fallback, detect `scroll` or `IntersectionObserver` triggers, scroll to bottom in a loop until page height stabilizes, then extract.

**Real-time streaming crawl log**
- *What:* Show a live log of "Fetching /docs/intro... Fetching /blog/..." as the crawl runs.
- *Why deferred:* Rejected in favor of the `pages_found` counter — the counter communicates progress without the complexity of SSE/WebSockets and without overwhelming the UI.
- *How:* SSE endpoint streaming log lines from a per-crawl-job queue, consumed on the frontend with `EventSource`.
