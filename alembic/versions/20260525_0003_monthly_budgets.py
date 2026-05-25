"""add monthly budgets

Revision ID: 20260525_0003
Revises: 20260524_0002
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260525_0003"
down_revision: Union[str, None] = "20260524_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monthly_budgets_category_id"), "monthly_budgets", ["category_id"])
    op.create_index(op.f("ix_monthly_budgets_user_id"), "monthly_budgets", ["user_id"])
    op.create_index(
        "uq_monthly_budgets_user_month_total",
        "monthly_budgets",
        ["user_id", "month_start"],
        unique=True,
        postgresql_where=sa.text("category_id IS NULL"),
    )
    op.create_index(
        "uq_monthly_budgets_user_month_category",
        "monthly_budgets",
        ["user_id", "month_start", "category_id"],
        unique=True,
        postgresql_where=sa.text("category_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_monthly_budgets_user_month_category", table_name="monthly_budgets")
    op.drop_index("uq_monthly_budgets_user_month_total", table_name="monthly_budgets")
    op.drop_index(op.f("ix_monthly_budgets_user_id"), table_name="monthly_budgets")
    op.drop_index(op.f("ix_monthly_budgets_category_id"), table_name="monthly_budgets")
    op.drop_table("monthly_budgets")
