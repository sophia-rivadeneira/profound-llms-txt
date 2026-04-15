from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.routers import crawls, llms, monitors, sites
from app.services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await scheduler.reap_orphaned_crawls()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="Profound llms.txt Generator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "env": settings.ENV}


app.include_router(sites.router)
app.include_router(crawls.router)
app.include_router(llms.router)
app.include_router(monitors.router)
