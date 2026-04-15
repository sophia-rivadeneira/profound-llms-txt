from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LlmsFileResponse(BaseModel):
    id: int
    site_id: int
    content: str
    content_hash: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class ChangeEventResponse(BaseModel):
    id: int
    site_id: int
    crawl_job_id: int
    detected_at: datetime
    pages_added: int
    pages_removed: int
    pages_modified: int
    summary: str | None

    model_config = {"from_attributes": True}
