from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class MonitorResponse(BaseModel):
    site_id: int
    interval_hours: int
    is_active: bool
    last_checked_at: datetime | None
    next_check_at: datetime | None

    model_config = {"from_attributes": True}


class MonitorPatch(BaseModel):
    interval_hours: int | None = Field(default=None, ge=1, le=168)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "MonitorPatch":
        if self.interval_hours is None and self.is_active is None:
            raise ValueError("at least one of interval_hours, is_active is required")
        return self
