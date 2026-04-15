from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import CrawlJob, PageData, Site
from app.routers._deps import get_site_or_404
from app.schemas import CrawlJobDetailResponse, CrawlJobResponse, PageDataResponse
from app.services.classifier import SECTION_ORDER
from app.services.crawler import run_crawl_in_background
from app.services.generator import normalize_text

_SECTION_RANK = {name: i for i, name in enumerate(SECTION_ORDER)}
_UNKNOWN_SECTION_RANK = len(SECTION_ORDER)


def _page_sort_key(page: PageData) -> tuple[int, int, str]:
    section = page.section or "General"
    section_rank = _SECTION_RANK.get(section, _UNKNOWN_SECTION_RANK)
    # Non-optional first (0), optional second (1), then section rank, then URL.
    return (1 if page.is_optional else 0, section_rank, page.url)


def _page_to_response(
    page: PageData, site_description_normalized: str | None
) -> PageDataResponse:
    response = PageDataResponse.model_validate(page)
    if (response.description and normalize_text(response.description) == site_description_normalized):
        response.description = None
    return response


router = APIRouter(prefix="/sites/{site_id}/crawls", tags=["crawls"])


@router.get(
    "",
    response_model=list[CrawlJobResponse],
    dependencies=[Depends(get_site_or_404)],
)
async def list_crawls(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[CrawlJobResponse]:
    result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == site_id)
        .order_by(CrawlJob.created_at.desc())
    )
    return [CrawlJobResponse.model_validate(j) for j in result.scalars().all()]


@router.get("/{crawl_id}", response_model=CrawlJobDetailResponse)
async def get_crawl(
    crawl_id: int,
    site: Site = Depends(get_site_or_404),
    db: AsyncSession = Depends(get_db),
) -> CrawlJobDetailResponse:
    crawl_job = await db.get(CrawlJob, crawl_id)
    if not crawl_job or crawl_job.site_id != site.id:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    site_description_normalized = normalize_text(site.description)

    result = await db.execute(
        select(PageData).where(PageData.crawl_job_id == crawl_id)
    )
    pages = sorted(result.scalars().all(), key=_page_sort_key)

    return CrawlJobDetailResponse(
        crawl_job=CrawlJobResponse.model_validate(crawl_job),
        pages=[_page_to_response(p, site_description_normalized) for p in pages],
    )


@router.post("", response_model=CrawlJobResponse, status_code=201)
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    site: Site = Depends(get_site_or_404),
    db: AsyncSession = Depends(get_db),
) -> CrawlJobResponse:
    crawl_job = CrawlJob(
        site_id=site.id,
        triggered_by="manual",
        status="pending",
    )
    db.add(crawl_job)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A crawl is already in progress")

    background_tasks.add_task(run_crawl_in_background, site.id, crawl_job.id)
    return CrawlJobResponse.model_validate(crawl_job)
