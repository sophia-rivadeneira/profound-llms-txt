from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChangeEvent, CrawlJob, Site
from app.schemas import SiteCreate, SiteCreateResponse, SiteResponse
from app.services.crawler import run_crawl_in_background
from app.services.urls import domain_to_slug, extract_domain, normalize_to_origin

router = APIRouter(prefix="/sites", tags=["sites"])


async def _response_for_existing_site(
    existing: Site,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> SiteCreateResponse:
    latest_job_result = await db.execute(
        select(CrawlJob)
        .where(CrawlJob.site_id == existing.id)
        .order_by(CrawlJob.id.desc())
        .limit(1)
    )
    latest_job = latest_job_result.scalar_one_or_none()
    if latest_job is None:
        latest_job = CrawlJob(
            site_id=existing.id,
            triggered_by="initial",
            status="pending",
        )
        db.add(latest_job)
        await db.commit()
        background_tasks.add_task(
            run_crawl_in_background, existing.id, latest_job.id
        )
    return SiteCreateResponse(
        site=SiteResponse.model_validate(existing),
        crawl_job_id=latest_job.id,
        status=latest_job.status,
    )


@router.post("", response_model=SiteCreateResponse, status_code=201)
async def create_site(
    body: SiteCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SiteCreateResponse:
    url = normalize_to_origin(str(body.url))
    domain = extract_domain(url)

    existing_result = await db.execute(select(Site).where(Site.url == url))
    existing = existing_result.scalar_one_or_none()
    if existing:
        return await _response_for_existing_site(existing, db, background_tasks)

    base_slug = domain_to_slug(domain)
    slug_taken = await db.scalar(select(Site.id).where(Site.slug == base_slug))
    site = Site(url=url, domain=domain, slug=None if slug_taken else base_slug)
    db.add(site)
    await db.flush()
    site.slug = site.slug or f"{base_slug}-{site.id}"

    crawl_job = CrawlJob(
        site_id=site.id,
        triggered_by="initial",
        status="pending",
    )
    db.add(crawl_job)
    await db.commit()

    background_tasks.add_task(run_crawl_in_background, site.id, crawl_job.id)

    return SiteCreateResponse(
        site=SiteResponse.model_validate(site),
        crawl_job_id=crawl_job.id,
        status=crawl_job.status,
    )


@router.get("", response_model=list[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db)) -> list[SiteResponse]:
    last_crawled_subq = (
        select(func.max(CrawlJob.completed_at))
        .where(CrawlJob.site_id == Site.id, CrawlJob.status == "completed")
        .correlate(Site)
        .scalar_subquery()
    )
    last_crawl_status_subq = (
        select(CrawlJob.status)
        .where(CrawlJob.site_id == Site.id)
        .order_by(CrawlJob.id.desc())
        .limit(1)
        .correlate(Site)
        .scalar_subquery()
    )
    event_count_subq = (
        select(func.count(ChangeEvent.id))
        .where(ChangeEvent.site_id == Site.id)
        .correlate(Site)
        .scalar_subquery()
    )
    latest_event_id_subq = (
        select(func.max(ChangeEvent.id))
        .where(ChangeEvent.site_id == Site.id)
        .correlate(Site)
        .scalar_subquery()
    )
    result = await db.execute(
        select(
            Site,
            last_crawled_subq.label("last_crawled_at"),
            last_crawl_status_subq.label("last_crawl_status"),
            event_count_subq.label("event_count"),
            latest_event_id_subq.label("latest_event_id"),
        ).order_by(Site.created_at.desc())
    )
    return [
        SiteResponse.model_validate(site).model_copy(
            update={
                "last_crawled_at": last_crawled_at,
                "last_crawl_status": last_crawl_status,
                "event_count": event_count,
                "latest_event_id": latest_event_id,
            }
        )
        for site, last_crawled_at, last_crawl_status, event_count, latest_event_id in result.all()
    ]


@router.delete("/{site_id}", status_code=204)
async def delete_site(site_id: str, db: AsyncSession = Depends(get_db)) -> None:
    if site_id.isdigit():
        site = await db.get(Site, int(site_id))
    else:
        result = await db.execute(select(Site).where((Site.slug == site_id) | (Site.domain == site_id)))
        site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await db.delete(site)
    await db.commit()


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: str,
    db: AsyncSession = Depends(get_db),
) -> SiteResponse:
    if site_id.isdigit():
        site = await db.get(Site, int(site_id))
    else:
        result = await db.execute(
            select(Site).where((Site.slug == site_id) | (Site.domain == site_id))
        )
        site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteResponse.model_validate(site)
