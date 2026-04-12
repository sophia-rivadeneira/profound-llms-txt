from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class SiteCreate(BaseModel):
    url: HttpUrl


class SiteResponse(BaseModel):
    id: int
    url: str
    domain: str
    title: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SiteCreateResponse(BaseModel):
    site: SiteResponse
    crawl_job_id: int
    status: str
