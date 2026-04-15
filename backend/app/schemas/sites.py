from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class SiteCreate(BaseModel):
    url: HttpUrl


class SiteResponse(BaseModel):
    id: int
    url: str
    domain: str
    slug: str | None
    title: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_crawled_at: datetime | None = None
    last_crawl_status: str | None = None
    event_count: int = 0
    latest_event_id: int | None = None

    model_config = {"from_attributes": True}


class SiteCreateResponse(BaseModel):
    site: SiteResponse
    crawl_job_id: int
    status: str
