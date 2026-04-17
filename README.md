# llms.txt Generator

A web app that generates and monitors [llms.txt](https://llmstxt.org/) files for any website. llms.txt is a proposed standard (like `robots.txt`) that helps LLMs understand a site's content.

Paste a URL, the crawler fetches every reachable page, classifies them into sections, and emits a spec-compliant llms.txt file. A built-in scheduler re-crawls on a configurable interval and a change timeline tracks what was added, removed, or modified between crawls.

## Demo

- **Live app:** [llmtxtgenerator.vercel.app](https://llmtxtgenerator.vercel.app/)
- **Walkthrough & demo video:** [Google Slides presentation](https://docs.google.com/presentation/d/1TPY65Cf1I824olDAuoBqk4v59_l753Ka/edit?usp=sharing&ouid=117857723883217353471&rtpof=true&sd=true)

## Features

- **Async BFS crawler** — httpx for speed, Playwright fallback for JS-rendered SPAs, robots.txt respected, sitemap-first discovery
- **Deterministic llms.txt generation** — pages classified by URL path patterns, no LLM dependency in the critical path
- **Automated monitoring** — configurable re-crawl interval (1–168 hours), change detection via content hashing, auto-pause after repeated failures
- **Change timeline** — semantic diffs showing pages added, removed, and modified per crawl
- **One active crawl per site** — enforced by a database-level unique partial index, not application locking
- **Live progress** — frontend polls for page count and elapsed time during crawls

## Architecture

```
Vercel (frontend)              Railway (backend)
┌─────────────────────┐       ┌─────────────────────────┐
│ Next.js + Tailwind   │──API──│ FastAPI + SQLAlchemy     │
│ shadcn/ui            │ calls │ httpx + BeautifulSoup    │
│ TanStack Query       │       │ Playwright (JS fallback) │
│                      │       │ asyncio scheduler        │
│                      │       │ PostgreSQL               │
└─────────────────────┘       └─────────────────────────┘
```

Frontend and backend are separate deployments so the crawler can scale independently of the UI and the API is usable from other clients.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, httpx, BeautifulSoup, Playwright. Managed with [uv](https://astral.sh/uv).
- **Frontend:** Next.js 16, TypeScript, Tailwind v4, shadcn/ui, TanStack Query.
- **Database:** PostgreSQL 16.
- **Deployment:** Vercel (frontend), Railway (backend + Postgres).

## Run locally

### Prerequisites

- [uv](https://astral.sh/uv) (Python package manager)
- Node.js 20+
- PostgreSQL 16 (`brew install postgresql@16 && brew services start postgresql@16`)

### Backend

```bash
cd backend
createdb profound                          # one-time
cp .env.example .env                       # edit DATABASE_URL if needed
uv sync                                    # install Python deps
uv run playwright install --with-deps chromium  # install headless browser for JS fallback
uv run alembic upgrade head                # apply database migrations
uv run uvicorn app.main:app --reload       # starts at http://localhost:8000
```

Verify: `curl http://localhost:8000/health` should return `{"status":"ok","env":"development"}`.

### Frontend

```bash
cd frontend
cp .env.example .env.local                 # edit API URL if needed
npm install                                # install Node deps
npm run dev                                # starts at http://localhost:3000
```

### Environment variables

**Backend** (`backend/.env`):

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string. Accepts `postgres://`, `postgresql://`, or `postgresql+asyncpg://` — auto-translated at runtime. | (required) |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |
| `ENV` | Environment name (shown in `/health`) | `development` |

**Frontend** (`frontend/.env.local`):

| Variable | Description | Default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL (used in browser) | `http://localhost:8000` |

## How it works

### Crawling (`backend/app/services/crawler.py`)

When a user submits a URL, the backend creates a `CrawlJob` and runs the crawl as a background task. The crawler:

1. Fetches `robots.txt` and respects its rules
2. Discovers pages via `sitemap.xml` (if available), then follows links via BFS
3. Extracts metadata from each page (title, description, canonical URL, outbound links)
4. If a page looks like a JS-rendered shell (empty body with a framework root div), re-fetches it with Playwright
5. Stops at 200 pages, depth 5, or 120 seconds — whichever comes first

### Generation (`backend/app/services/generator.py`)

After a crawl completes, the generator:

1. Classifies each page into a section (Documentation, Blog, API Reference, etc.) based on URL path patterns
2. Assembles the llms.txt markdown: site title as H1, meta description as blockquote, pages grouped under section headings, optional sections (Blog, Changelog, Legal) under `## Optional`
3. Hashes the output and compares to the previous version — if different, records a change event with semantic diff counts

### Scheduling (`backend/app/services/scheduler.py`)

An in-process asyncio loop ticks every 5 minutes and checks for monitors whose `next_check_at` has passed. Due monitors get a scheduled crawl dispatched. The scheduler uses `SELECT ... FOR UPDATE SKIP LOCKED` so multiple workers can't double-dispatch the same monitor. On startup, a reaper marks any orphaned pending/running crawl jobs as failed.

### Data model (`backend/app/models/`)

| Table | Purpose |
|---|---|
| `sites` | One row per submitted URL. Stores domain, title, description. |
| `crawl_jobs` | Lifecycle row per crawl — status, page count, error message, timestamps. |
| `page_data` | One row per page per crawl — URL, title, description, section, optional flag. |
| `llms_files` | The current llms.txt content per site, updated in place. Content hash for change detection. |
| `change_events` | Immutable log of changes — pages added, removed, modified, with a human-readable summary. |
| `monitors` | One per site. Interval, active flag, next check time. Auto-created, opt-out. |

### API endpoints (`backend/app/routers/`)

```
POST   /sites                    Create or return a site, kick off initial crawl
GET    /sites                    List all sites with latest crawl status
GET    /sites/{id}               Site detail (accepts numeric ID or slug)
DELETE /sites/{id}               Remove site and all associated data (cascades)

POST   /sites/{id}/crawls        Trigger a manual re-crawl (409 if one is active)
GET    /sites/{id}/crawls        Crawl history
GET    /sites/{id}/crawls/{id}   Crawl detail with page list

GET    /sites/{id}/llms          Generated llms.txt as JSON (with metadata)
GET    /sites/{id}/llms.txt      Raw llms.txt markdown (text/plain, downloadable)

GET    /sites/{id}/changes       Change event timeline (newest first)

GET    /sites/{id}/monitor       Monitor settings
PATCH  /sites/{id}/monitor       Update interval (1–168h) or pause/resume
```

## Project layout

```
profound-website/
├── backend/
│   ├── app/
│   │   ├── config.py            pydantic-settings, env var loading
│   │   ├── main.py              FastAPI app, CORS, lifespan, router mounting
│   │   ├── db/                  async engine, session factory, base model
│   │   ├── models/              SQLAlchemy models (one file per table)
│   │   ├── schemas/             Pydantic request/response shapes
│   │   ├── routers/             API route handlers + shared dependencies
│   │   └── services/            crawler, generator, classifier, scheduler,
│   │                            robots checker, sitemap parser, Playwright renderer
│   ├── alembic/                 database migrations
│   ├── tests/                   pytest suite (113 tests)
│   └── pyproject.toml           Python deps (uv-managed)
├── frontend/
│   ├── src/
│   │   ├── app/                 Next.js App Router pages + layout
│   │   ├── components/          React components (site detail, dashboard,
│   │   │                        progress banner, change timeline, etc.)
│   │   └── lib/                 API client, types, localStorage helpers
│   └── package.json
├── PLAN.md                      architecture, schema, API design, phase plans
└── README.md                    this file
```

## Deployment

The app is deployed as two services:

- **Frontend** on [Vercel](https://vercel.com) — auto-deploys from the `frontend/` directory on push to `main`
- **Backend** on [Railway](https://railway.com) — Docker-based deploy from `backend/` with a Dockerfile that installs Playwright's Chromium dependency

PostgreSQL is provisioned as a Railway service in the same project. The backend's `DATABASE_URL` is wired via Railway's service reference variables.
