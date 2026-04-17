# Frontend — Profound llms.txt Generator

Next.js 16 app for submitting URLs, viewing generated `llms.txt` files, and tracking change history.

See the [root README](../README.md) for architecture and the full project overview.

## Run locally

The backend should be running on `http://localhost:8000` first (see `../backend/README.md`).

```bash
npm install
npm run dev    # http://localhost:3000
```

Environment variables live in `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Common commands

| Command | What it does |
|---|---|
| `npm run dev` | Start the dev server with hot reload |
| `npm run build` | Production build (also runs TypeScript check) |
| `npm run start` | Run the production build locally |
| `npm run lint` | Run ESLint |

## Stack

- **Next.js 16** with the App Router (`src/app/`)
- **TypeScript**
- **Tailwind CSS v4**
- **shadcn/ui** — Radix base, Nova preset (Geist font, Lucide icons)
- **TanStack Query** — server state, polling, and cache invalidation
- **`lib/api.ts`** — typed fetch wrapper pointing at `NEXT_PUBLIC_API_URL`

## Layout

```
frontend/
├── src/
│   ├── app/              App Router pages and layouts
│   ├── components/
│   │   └── ui/           shadcn/ui components
│   └── lib/
│       ├── api.ts        typed fetch wrapper for the backend
│       ├── seen.ts       localStorage helper for "seen" change markers
│       └── utils.ts      cn() helper from shadcn
├── public/
├── components.json       shadcn config
└── next.config.ts
```
