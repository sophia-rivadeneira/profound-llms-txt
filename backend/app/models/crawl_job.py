from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.change_event import ChangeEvent
    from app.models.page_data import PageData
    from app.models.site import Site


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        CheckConstraint(
            "triggered_by IN ('scheduled', 'manual')",
            name="crawl_jobs_triggered_by_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="crawl_jobs_status_check",
        ),
        Index(
            "uq_crawl_jobs_one_active_per_site",
            "site_id",
            unique=True,
            postgresql_where="status IN ('pending', 'running')",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    triggered_by: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    pages_found: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    site: Mapped[Site] = relationship(back_populates="crawl_jobs")
    pages: Mapped[list[PageData]] = relationship(
        back_populates="crawl_job", cascade="all, delete-orphan", passive_deletes=True
    )
    change_events: Mapped[list[ChangeEvent]] = relationship(back_populates="crawl_job")
