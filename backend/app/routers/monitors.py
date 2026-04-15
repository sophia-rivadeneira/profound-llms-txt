from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Monitor, Site
from app.schemas import MonitorPatch, MonitorResponse

router = APIRouter(prefix="/sites/{site_id}", tags=["monitors"])


async def _get_monitor_or_404(site_id: int, db: AsyncSession) -> Monitor:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    result = await db.execute(select(Monitor).where(Monitor.site_id == site_id))
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.get("/monitor", response_model=MonitorResponse)
async def get_monitor(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> MonitorResponse:
    monitor = await _get_monitor_or_404(site_id, db)
    return MonitorResponse.model_validate(monitor)


@router.patch("/monitor", response_model=MonitorResponse)
async def patch_monitor(
    site_id: int,
    body: MonitorPatch,
    db: AsyncSession = Depends(get_db),
) -> MonitorResponse:
    monitor = await _get_monitor_or_404(site_id, db)
    now = datetime.now(timezone.utc)

    if body.interval_hours is not None and body.interval_hours != monitor.interval_hours:
        monitor.interval_hours = body.interval_hours
        base = monitor.last_checked_at or now
        monitor.next_check_at = base + timedelta(hours=body.interval_hours)

    if body.is_active is not None and body.is_active != monitor.is_active:
        monitor.is_active = body.is_active
        if body.is_active:
            monitor.next_check_at = now

    await db.commit()
    await db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)
