from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.change_event import ChangeEvent
    from app.models.crawl_job import CrawlJob
    from app.models.llms_file import LlmsFile
    from app.models.monitor import Monitor


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    slug: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    crawl_jobs: Mapped[list[CrawlJob]] = relationship(
        back_populates="site", cascade="all, delete-orphan", passive_deletes=True
    )
    llms_file: Mapped[LlmsFile | None] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    change_events: Mapped[list[ChangeEvent]] = relationship(
        back_populates="site", cascade="all, delete-orphan", passive_deletes=True
    )
    monitor: Mapped[Monitor | None] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
