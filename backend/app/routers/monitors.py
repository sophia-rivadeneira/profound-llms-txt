from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Monitor
from app.routers._deps import get_monitor_or_404
from app.schemas import MonitorPatch, MonitorResponse

router = APIRouter(prefix="/sites/{site_id}", tags=["monitors"])


@router.get("/monitor", response_model=MonitorResponse)
async def get_monitor(
    monitor: Monitor = Depends(get_monitor_or_404),
) -> MonitorResponse:
    return MonitorResponse.model_validate(monitor)


@router.patch("/monitor", response_model=MonitorResponse)
async def patch_monitor(
    body: MonitorPatch,
    monitor: Monitor = Depends(get_monitor_or_404),
    db: AsyncSession = Depends(get_db),
) -> MonitorResponse:
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
