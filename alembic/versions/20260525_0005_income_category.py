"""add income category

Revision ID: 20260525_0005
Revises: 20260525_0004
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260525_0005"
down_revision: Union[str, None] = "20260525_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO categories (user_id, name)
            SELECT users.id, 'Income'
            FROM users
            WHERE NOT EXISTS (
                SELECT 1
                FROM categories
                WHERE categories.user_id = users.id
                  AND categories.name = 'Income'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE expenses
            SET category_id = categories.id
            FROM categories
            WHERE expenses.user_id = categories.user_id
              AND categories.name = 'Income'
              AND expenses.kind = 'income'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE expenses
            SET category_id = general.id
            FROM categories AS income
            JOIN categories AS general
              ON general.user_id = income.user_id
             AND general.name = 'General'
            WHERE expenses.category_id = income.id
              AND income.name = 'Income'
            """
        )
    )
    op.execute(sa.text("DELETE FROM categories WHERE name = 'Income'"))
