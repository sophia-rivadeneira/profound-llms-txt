# Backend — Profound llms.txt Generator

FastAPI service that crawls websites, generates `llms.txt` files, and monitors them for changes.

See the [root README](../README.md) for architecture and the full project overview.

## Run locally

```bash
createdb profound                    # one-time, requires local Postgres
cp .env.example .env                 # edit DATABASE_URL if your local user differs
uv sync                              # install deps into .venv
uv run alembic upgrade head          # apply migrations
uv run uvicorn app.main:app --reload # http://localhost:8000
```

Health check: `curl http://localhost:8000/health`

## Common commands

| Command | What it does |
|---|---|
| `uv sync` | Install deps from `uv.lock` |
| `uv add <package>` | Add a new runtime dep |
| `uv add --dev <package>` | Add a dev-only dep |
| `uv run uvicorn app.main:app --reload` | Start the dev server |
| `uv run pytest` | Run the test suite |
| `uv run alembic revision --autogenerate -m "message"` | Generate a new migration from model changes |
| `uv run alembic upgrade head` | Apply all pending migrations |
| `uv run alembic downgrade -1` | Roll back the most recent migration |

## Layout

```
backend/
├── app/
│   ├── main.py          FastAPI app, CORS, router mounting
│   ├── config.py        Settings class (pydantic-settings)
│   ├── db/
│   │   ├── base.py      DeclarativeBase (Alembic imports this)
│   │   └── session.py   async engine + sessionmaker + get_db dependency
│   ├── models/          SQLAlchemy models — one file per table
│   ├── schemas/         Pydantic request/response models
│   ├── routers/         FastAPI route modules
│   └── services/        crawler, llms.txt generator, scheduler
├── alembic/
│   ├── env.py           wired to app.db.base.Base and app.config.settings
│   └── versions/        generated migration files
├── tests/
└── pyproject.toml
```

## Adding a new model

1. Create `app/models/<name>.py` with a class that inherits from `Base`.
2. Import the class from `app/models/__init__.py` — Alembic only sees models that are imported here.
3. Run `uv run alembic revision --autogenerate -m "add <name>"`.
4. Review the generated migration file before running it.
5. Run `uv run alembic upgrade head`.
