"""add user locale

Revision ID: 20260524_0002
Revises: 20260524_0001
Create Date: 2026-05-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260524_0002"
down_revision: Union[str, None] = "20260524_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=8), server_default="en", nullable=False),
    )
    op.alter_column("users", "locale", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "locale")
