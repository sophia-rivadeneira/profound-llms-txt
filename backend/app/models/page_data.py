from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.crawl_job import CrawlJob


class PageData(Base):
    __tablename__ = "page_data"
    __table_args__ = (
        UniqueConstraint("crawl_job_id", "url", name="uq_page_data_crawl_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(String)
    is_optional: Mapped[bool] = mapped_column(default=False)
    crawled_at: Mapped[datetime] = mapped_column(server_default=func.now())

    crawl_job: Mapped[CrawlJob] = relationship(back_populates="pages")
