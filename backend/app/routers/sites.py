from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db
from app.models import CrawlJob, Site
from app.schemas import SiteCreate, SiteCreateResponse, SiteResponse
from app.services.crawler import CrawlConfig, run_crawl
from app.services.urls import extract_domain, normalize_url

router = APIRouter(prefix="/sites", tags=["sites"])


async def _run_crawl_in_background(site_id: int, crawl_job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        site = await session.get(Site, site_id)
        crawl_job = await session.get(CrawlJob, crawl_job_id)
        if site and crawl_job:
            await run_crawl(site, crawl_job, session)


@router.post("", response_model=SiteCreateResponse, status_code=201)
async def create_site(
    body: SiteCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SiteCreateResponse:
    url = normalize_url(str(body.url))
    domain = extract_domain(url)

    existing = await db.execute(select(Site).where(Site.url == url))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Site already exists")

    site = Site(url=url, domain=domain)
    db.add(site)
    await db.flush()

    crawl_job = CrawlJob(
        site_id=site.id,
        triggered_by="initial",
        status="pending",
    )
    db.add(crawl_job)
    await db.commit()

    background_tasks.add_task(_run_crawl_in_background, site.id, crawl_job.id)

    return SiteCreateResponse(
        site=SiteResponse.model_validate(site),
        crawl_job_id=crawl_job.id,
        status=crawl_job.status,
    )


@router.get("", response_model=list[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db)) -> list[SiteResponse]:
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    sites = result.scalars().all()
    return [SiteResponse.model_validate(s) for s in sites]


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> SiteResponse:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteResponse.model_validate(site)
