from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChangeEvent, CrawlJob, LlmsFile
from app.routers._deps import get_site_or_404
from app.schemas import ChangeEventResponse, LlmsFileResponse

router = APIRouter(prefix="/sites/{site_id}", tags=["llms"])


async def get_llms_or_404(
    site_id: int, db: AsyncSession = Depends(get_db)
) -> LlmsFile:
    result = await db.execute(select(LlmsFile).where(LlmsFile.site_id == site_id))
    llms_file = result.scalar_one_or_none()
    if not llms_file:
        raise HTTPException(status_code=404, detail="No llms.txt generated yet")
    return llms_file


@router.get(
    "/llms",
    response_model=LlmsFileResponse,
    dependencies=[Depends(get_site_or_404)],
)
async def get_llms_json(
    llms_file: LlmsFile = Depends(get_llms_or_404),
) -> LlmsFileResponse:
    return LlmsFileResponse.model_validate(llms_file)


@router.get("/llms.txt", dependencies=[Depends(get_site_or_404)])
async def get_llms_raw(
    llms_file: LlmsFile = Depends(get_llms_or_404),
) -> PlainTextResponse:
    return PlainTextResponse(
        llms_file.content,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="llms.txt"'},
    )


@router.get(
    "/changes",
    response_model=list[ChangeEventResponse],
    dependencies=[Depends(get_site_or_404)],
)
async def list_change_events(
    site_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[ChangeEventResponse]:
    result = await db.execute(
        select(ChangeEvent, CrawlJob.triggered_by)
        .join(CrawlJob, CrawlJob.id == ChangeEvent.crawl_job_id)
        .where(ChangeEvent.site_id == site_id)
        .order_by(ChangeEvent.detected_at.desc())
        .limit(50)
    )
    return [
        ChangeEventResponse(
            id=event.id,
            site_id=event.site_id,
            crawl_job_id=event.crawl_job_id,
            detected_at=event.detected_at,
            pages_added=event.pages_added,
            pages_removed=event.pages_removed,
            pages_modified=event.pages_modified,
            summary=event.summary,
            triggered_by=triggered_by,
        )
        for event, triggered_by in result.all()
    ]
