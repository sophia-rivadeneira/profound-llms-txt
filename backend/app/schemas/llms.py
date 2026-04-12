from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LlmsFileResponse(BaseModel):
    id: int
    site_id: int
    content: str
    content_hash: str
    summary: str | None
    generated_at: datetime

    model_config = {"from_attributes": True}
