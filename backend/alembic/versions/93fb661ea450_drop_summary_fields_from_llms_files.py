"""drop summary fields from llms files

Revision ID: 93fb661ea450
Revises: b4b4235162ba
Create Date: 2026-04-13 21:58:04.016426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93fb661ea450'
down_revision: Union[str, Sequence[str], None] = 'b4b4235162ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("llms_files", "summary_generated")
    op.drop_column("llms_files", "summary")


def downgrade() -> None:
    op.add_column("llms_files", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("llms_files", sa.Column("summary_generated", sa.Text(), nullable=True))
