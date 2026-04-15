"""enforce one active crawl per site and backfill monitors

Revision ID: d7e4f5a6b7c8
Revises: 93fb661ea450
Create Date: 2026-04-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "93fb661ea450"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill Monitor rows for sites that predate Phase 5's auto-create on
    # POST /sites, so the monitoring endpoints and frontend panel never see
    # a 404 for existing sites.
    op.execute(
        """
        INSERT INTO monitors (
            site_id, interval_hours, is_active, next_check_at, created_at
        )
        SELECT s.id, 24, true, NOW() + interval '24 hours', NOW()
        FROM sites s
        WHERE NOT EXISTS (SELECT 1 FROM monitors m WHERE m.site_id = s.id)
        """
    )

    # Enforce "at most one pending/running crawl per site" at the DB level so
    # the manual POST /crawls path and the scheduler tick can't race each
    # other into a double-dispatch. This is the single source of truth for
    # the invariant — no application-level lock needed.
    op.create_index(
        "uq_crawl_jobs_one_active_per_site",
        "crawl_jobs",
        ["site_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_crawl_jobs_one_active_per_site", table_name="crawl_jobs")
    # Intentional: do not delete backfilled monitor rows on downgrade.
