from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChangeEvent(Base):
    __tablename__ = "change_events"
    __table_args__ = (
        Index("idx_change_events_site_time", "site_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    old_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pages_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_modified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship(back_populates="change_events")  # noqa: F821
    crawl_job: Mapped["CrawlJob"] = relationship(back_populates="change_events")  # noqa: F821
