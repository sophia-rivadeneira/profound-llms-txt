from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.crawl_job import CrawlJob
    from app.models.site import Site


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = (
        Index("idx_change_events_site_time", "site_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"))
    crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE")
    )
    detected_at: Mapped[datetime] = mapped_column(server_default=func.now())
    old_hash: Mapped[str | None] = mapped_column(String(64))
    pages_added: Mapped[int] = mapped_column(default=0)
    pages_removed: Mapped[int] = mapped_column(default=0)
    pages_modified: Mapped[int] = mapped_column(default=0)
    summary: Mapped[str | None] = mapped_column(Text)

    site: Mapped[Site] = relationship(back_populates="change_events")
    crawl_job: Mapped[CrawlJob] = relationship(back_populates="change_events")
