from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(  # noqa: F821
        back_populates="site", cascade="all, delete-orphan", passive_deletes=True
    )
    llms_file: Mapped["LlmsFile | None"] = relationship(  # noqa: F821
        back_populates="site",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    change_events: Mapped[list["ChangeEvent"]] = relationship(  # noqa: F821
        back_populates="site", cascade="all, delete-orphan", passive_deletes=True
    )
    monitor: Mapped["Monitor | None"] = relationship(  # noqa: F821
        back_populates="site",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
