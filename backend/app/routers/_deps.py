from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Monitor, Site


async def get_site_or_404(
    site_id: int, db: AsyncSession = Depends(get_db)
) -> Site:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


async def get_monitor_or_404(
    site_id: int, db: AsyncSession = Depends(get_db)
) -> Monitor:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    result = await db.execute(select(Monitor).where(Monitor.site_id == site_id))
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor
