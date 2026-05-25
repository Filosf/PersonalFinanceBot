"""add income kind to expenses

Revision ID: 20260525_0004
Revises: 20260525_0003
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260525_0004"
down_revision: Union[str, None] = "20260525_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("kind", sa.String(length=16), server_default="expense", nullable=False),
    )
    op.alter_column("expenses", "kind", server_default=None)
    op.create_index(op.f("ix_expenses_kind"), "expenses", ["kind"])


def downgrade() -> None:
    op.drop_index(op.f("ix_expenses_kind"), table_name="expenses")
    op.drop_column("expenses", "kind")
