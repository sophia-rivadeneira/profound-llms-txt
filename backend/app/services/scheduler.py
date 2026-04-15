from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.models import CrawlJob, Monitor
from app.services.crawler import run_crawl_in_background

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 300
ORPHAN_REAPER_ERROR_MESSAGE = "Orphaned by process restart"

_task: asyncio.Task | None = None


async def reap_orphaned_crawls() -> int:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                update(CrawlJob)
                .where(CrawlJob.status.in_(("pending", "running")))
                .values(
                    status="failed",
                    error_message=ORPHAN_REAPER_ERROR_MESSAGE,
                    completed_at=datetime.now(timezone.utc),
                )
            )
        count = result.rowcount or 0
    if count:
        logger.info("reaped %d orphaned crawl(s) on startup", count)
    return count


async def _tick() -> None:
    # Phase 1: lock due monitors and advance their next_check_at atomically.
    due_sites: list[int] = []
    async with AsyncSessionLocal() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(Monitor)
                .where(Monitor.is_active.is_(True), Monitor.next_check_at <= now)
                .with_for_update(skip_locked=True)
            )
            for monitor in result.scalars().all():
                monitor.next_check_at = now + timedelta(hours=monitor.interval_hours)
                due_sites.append(monitor.site_id)

    # Phase 2: try to insert a pending crawl per due site. 
    dispatch: list[tuple[int, int]] = []
    for site_id in due_sites:
        async with AsyncSessionLocal() as session:
            crawl_job = CrawlJob(site_id=site_id, triggered_by="scheduled", status="pending")
            session.add(crawl_job)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.info( "scheduler: site %s already has an active crawl; skipping dispatch", site_id)
                continue
            dispatch.append((site_id, crawl_job.id))

    for site_id, job_id in dispatch:
        asyncio.create_task(run_crawl_in_background(site_id, job_id))

    if dispatch:
        logger.info("scheduler dispatched %d scheduled crawl(s)", len(dispatch))


async def _loop() -> None:
    while True:
        try:
            await _tick()
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(TICK_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop())
    logger.info("scheduler started (tick interval: %ds)", TICK_INTERVAL_SECONDS)


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("scheduler stopped")
