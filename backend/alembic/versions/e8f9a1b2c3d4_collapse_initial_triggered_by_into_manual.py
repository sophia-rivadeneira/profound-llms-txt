"""collapse initial triggered_by into manual

Revision ID: e8f9a1b2c3d4
Revises: d7e4f5a6b7c8
Create Date: 2026-04-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e8f9a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d7e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE crawl_jobs SET triggered_by = 'manual' WHERE triggered_by = 'initial'")
    op.drop_constraint("crawl_jobs_triggered_by_check", "crawl_jobs", type_="check")
    op.create_check_constraint(
        "crawl_jobs_triggered_by_check",
        "crawl_jobs",
        "triggered_by IN ('scheduled', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("crawl_jobs_triggered_by_check", "crawl_jobs", type_="check")
    op.create_check_constraint(
        "crawl_jobs_triggered_by_check",
        "crawl_jobs",
        "triggered_by IN ('initial', 'scheduled', 'manual')",
    )
