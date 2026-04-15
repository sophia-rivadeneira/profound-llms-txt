from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.services.crawler import CrawlConfig

# Limits come from the crawler's live CrawlConfig so the frontend never has
# to hardcode them — single source of truth for the progress banner's
# N/max_pages counter and the "stops in Ms" timer.
_CONFIG = CrawlConfig()


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
    max_pages: int = _CONFIG.max_pages
    max_duration_seconds: int = _CONFIG.max_duration_seconds

    model_config = {"from_attributes": True}


class PageDataResponse(BaseModel):
    id: int
    url: str
    canonical_url: str | None
    title: str | None
    description: str | None
    section: str | None
    is_optional: bool
    crawled_at: datetime

    model_config = {"from_attributes": True}


class CrawlJobDetailResponse(BaseModel):
    crawl_job: CrawlJobResponse
    pages: list[PageDataResponse]
