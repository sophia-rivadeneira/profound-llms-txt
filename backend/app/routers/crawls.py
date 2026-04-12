from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db
from app.models import CrawlJob, PageData, Site
from app.schemas import CrawlJobDetailResponse, CrawlJobResponse, PageDataResponse
from app.services.crawler import run_crawl

router = APIRouter(prefix="/sites/{site_id}/crawls", tags=["crawls"])


async def _run_crawl_in_background(site_id: int, crawl_job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        site = await session.get(Site, site_id)
        crawl_job = await session.get(CrawlJob, crawl_job_id)
        if site and crawl_job:
            await run_crawl(site, crawl_job, session)


@router.get("", response_model=list[CrawlJobResponse])
async def list_crawls(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[CrawlJobResponse]:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.created_at.desc())
    )
    jobs = result.scalars().all()
    return [CrawlJobResponse.model_validate(j) for j in jobs]


@router.get("/{crawl_id}", response_model=CrawlJobDetailResponse)
async def get_crawl(
    site_id: int,
    crawl_id: int,
    db: AsyncSession = Depends(get_db),
) -> CrawlJobDetailResponse:
    crawl_job = await db.get(CrawlJob, crawl_id)
    if not crawl_job or crawl_job.site_id != site_id:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    result = await db.execute(
        select(PageData)
        .where(PageData.crawl_job_id == crawl_id)
        .order_by(PageData.crawled_at)
    )
    pages = result.scalars().all()

    return CrawlJobDetailResponse(
        crawl_job=CrawlJobResponse.model_validate(crawl_job),
        pages=[PageDataResponse.model_validate(p) for p in pages],
    )


@router.post("", response_model=CrawlJobResponse, status_code=201)
async def trigger_crawl(
    site_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> CrawlJobResponse:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    active = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id, CrawlJob.status.in_(["pending", "running"]))
        .limit(1)
    )
    if active.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A crawl is already in progress")

    crawl_job = CrawlJob(
        site_id=site.id,
        triggered_by="manual",
        status="pending",
    )
    db.add(crawl_job)
    await db.commit()

    background_tasks.add_task(_run_crawl_in_background, site.id, crawl_job.id)

    return CrawlJobResponse.model_validate(crawl_job)
