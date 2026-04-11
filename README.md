# Profound llms.txt Generator

A web app that generates and monitors [llms.txt](https://llmstxt.org/) files for any website — a proposed standard (like `robots.txt`) that helps LLMs understand a site's content.

Submit a URL, the crawler fetches it, extracts page metadata, and emits a spec-compliant `llms.txt`. Files are re-crawled on a schedule and a change timeline records what was added, removed, or modified between crawls.

## Architecture

```
Vercel (frontend)              Railway (backend)
┌─────────────────────┐       ┌─────────────────────────┐
│ Next.js + Tailwind   │──API──│ FastAPI + SQLAlchemy     │
│ shadcn/ui (Radix)    │ calls │ httpx + BeautifulSoup    │
│                      │       │ Playwright (JS fallback) │
│                      │       │ APScheduler              │
│                      │       │ PostgreSQL               │
└─────────────────────┘       └─────────────────────────┘
```

Separate deployments so the crawler can scale independently of the UI and the API stays usable from other clients (CLI, browser extension).

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic, APScheduler, httpx, BeautifulSoup, Playwright. Managed with `uv`.
- **Frontend:** Next.js 16, TypeScript, Tailwind v4, shadcn/ui (Radix base, Nova preset — Geist + Lucide).
- **Database:** PostgreSQL 16.
- **Deployment:** Vercel (frontend), Railway (backend + Postgres).

## Run locally

### Prerequisites
- [`uv`](https://astral.sh/uv) for the backend
- Node.js 20+ for the frontend
- PostgreSQL 16 running locally (`brew install postgresql@16 && brew services start postgresql@16`)

### Backend

```bash
cd backend
createdb profound                        # one-time
cp .env.example .env                     # then edit DATABASE_URL if needed
uv sync                                  # install deps
uv run alembic upgrade head              # apply migrations
uv run uvicorn app.main:app --reload     # http://localhost:8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"ok","env":"development"}`

### Frontend

```bash
cd frontend
npm install
npm run dev                              # http://localhost:3000
```

The frontend reads `NEXT_PUBLIC_API_URL` from `.env.local` (defaults to `http://localhost:8000`).

## Project layout

```
profound-website/
├── backend/                  FastAPI service — crawler, generator, scheduler
│   ├── app/
│   │   ├── config.py         pydantic-settings
│   │   ├── db/               DeclarativeBase + async session
│   │   ├── models/           SQLAlchemy models (one per table)
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── routers/          FastAPI routes
│   │   └── services/         crawler, llms.txt generator, scheduler
│   ├── alembic/              migrations
│   └── pyproject.toml
├── frontend/                 Next.js app
└── PLAN.md                   full architecture, schema, API design
```

See `PLAN.md` for the database schema, API endpoint design, and implementation phases.

## Status

- [x] **Phase 1** — project scaffold (backend + frontend + migrations)
- [ ] **Phase 2** — crawler (httpx + BeautifulSoup, Playwright fallback)
- [ ] **Phase 3** — llms.txt generation per spec
- [ ] **Phase 4** — frontend UI
- [ ] **Phase 5** — monitoring system (APScheduler + change detection)
- [ ] **Phase 6** — deployment to Vercel + Railway
