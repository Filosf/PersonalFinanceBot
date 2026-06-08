"""add recurring payment occurrences

Revision ID: 20260608_0008
Revises: 20260602_0007
Create Date: 2026-06-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0008"
down_revision: str | None = "20260602_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_payment_occurrences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recurring_payment_id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recurring_payment_id"], ["recurring_payments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "series_id", "month_start", name="uq_recurring_series_month"
        ),
    )
    op.create_index(
        "ix_recurring_payment_occurrences_expense_id",
        "recurring_payment_occurrences",
        ["expense_id"],
        unique=True,
    )
    op.create_index(
        "ix_recurring_payment_occurrences_month_start",
        "recurring_payment_occurrences",
        ["month_start"],
    )
    op.create_index(
        "ix_recurring_payment_occurrences_recurring_payment_id",
        "recurring_payment_occurrences",
        ["recurring_payment_id"],
    )
    op.create_index(
        "ix_recurring_payment_occurrences_series_id",
        "recurring_payment_occurrences",
        ["series_id"],
    )
    op.create_index(
        "ix_recurring_payment_occurrences_user_id",
        "recurring_payment_occurrences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recurring_payment_occurrences_user_id",
        table_name="recurring_payment_occurrences",
    )
    op.drop_index(
        "ix_recurring_payment_occurrences_series_id",
        table_name="recurring_payment_occurrences",
    )
    op.drop_index(
        "ix_recurring_payment_occurrences_recurring_payment_id",
        table_name="recurring_payment_occurrences",
    )
    op.drop_index(
        "ix_recurring_payment_occurrences_month_start",
        table_name="recurring_payment_occurrences",
    )
    op.drop_index(
        "ix_recurring_payment_occurrences_expense_id",
        table_name="recurring_payment_occurrences",
    )
    op.drop_table("recurring_payment_occurrences")
