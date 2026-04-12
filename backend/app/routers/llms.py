from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import LlmsFile, Site
from app.schemas import LlmsFileResponse

router = APIRouter(prefix="/sites/{site_id}", tags=["llms"])


@router.get("/llms", response_model=LlmsFileResponse)
async def get_llms_json(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> LlmsFileResponse:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = await db.execute(
        select(LlmsFile).where(LlmsFile.site_id == site_id)
    )
    llms_file = result.scalar_one_or_none()
    if not llms_file:
        raise HTTPException(status_code=404, detail="No llms.txt generated yet")

    return LlmsFileResponse.model_validate(llms_file)


@router.get("/llms.txt")
async def get_llms_raw(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    result = await db.execute(
        select(LlmsFile).where(LlmsFile.site_id == site_id)
    )
    llms_file = result.scalar_one_or_none()
    if not llms_file:
        raise HTTPException(status_code=404, detail="No llms.txt generated yet")

    return PlainTextResponse(llms_file.content, media_type="text/plain")
