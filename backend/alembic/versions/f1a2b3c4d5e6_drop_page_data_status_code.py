"""drop page_data.status_code

Revision ID: f1a2b3c4d5e6
Revises: e8f9a1b2c3d4
Create Date: 2026-04-15 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8f9a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("page_data", "status_code")


def downgrade() -> None:
    op.add_column(
        "page_data",
        sa.Column("status_code", sa.Integer(), nullable=True),
    )
