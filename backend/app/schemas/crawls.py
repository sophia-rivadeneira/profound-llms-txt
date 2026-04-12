from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CrawlJobResponse(BaseModel):
    id: int
    site_id: int
    triggered_by: str
    status: str
    pages_found: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PageDataResponse(BaseModel):
    id: int
    url: str
    canonical_url: str | None
    title: str | None
    description: str | None
    section: str | None
    is_optional: bool
    status_code: int | None
    crawled_at: datetime

    model_config = {"from_attributes": True}


class CrawlJobDetailResponse(BaseModel):
    crawl_job: CrawlJobResponse
    pages: list[PageDataResponse]
