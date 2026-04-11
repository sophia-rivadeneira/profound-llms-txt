from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.site import Site


class Monitor(Base):
    __tablename__ = "monitors"
    __table_args__ = (
        Index(
            "idx_monitors_next_check",
            "next_check_at",
            postgresql_where="is_active",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), unique=True
    )
    interval_hours: Mapped[int] = mapped_column(default=24)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_checked_at: Mapped[datetime | None]
    next_check_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    site: Mapped[Site] = relationship(back_populates="monitor")
