"""add recurring payments

Revision ID: 20260602_0007
Revises: 20260528_0006
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260602_0007"
down_revision: str | None = "20260528_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount_source", sa.String(length=16), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_count", sa.Integer(), nullable=True),
        sa.Column("charge_day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("description", sa.String(length=500), server_default="", nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("end_month", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_payments_category_id", "recurring_payments", ["category_id"])
    op.create_index("ix_recurring_payments_deleted_at", "recurring_payments", ["deleted_at"])
    op.create_index("ix_recurring_payments_end_month", "recurring_payments", ["end_month"])
    op.create_index("ix_recurring_payments_series_id", "recurring_payments", ["series_id"])
    op.create_index("ix_recurring_payments_start_month", "recurring_payments", ["start_month"])
    op.create_index("ix_recurring_payments_user_id", "recurring_payments", ["user_id"])
    op.create_index(
        "ix_recurring_payments_user_period",
        "recurring_payments",
        ["user_id", "start_month", "end_month"],
    )
    op.create_index(
        "ix_recurring_payments_user_series",
        "recurring_payments",
        ["user_id", "series_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_payments_user_series", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_user_period", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_user_id", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_start_month", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_series_id", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_end_month", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_deleted_at", table_name="recurring_payments")
    op.drop_index("ix_recurring_payments_category_id", table_name="recurring_payments")
    op.drop_table("recurring_payments")
