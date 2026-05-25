import asyncio
import random
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Expense
from app.db.session import SessionLocal
from app.services.categories import CategoryService
from app.services.expenses import ExpenseService
from app.services.users import UserService

TELEGRAM_ID = 122078682
USERNAME = "Filosf"
CURRENCY = "ILS"
SEED_PREFIX = "[seed]"

EXPENSE_TEMPLATES = [
    ("Food", "groceries", 35, 180),
    ("Food", "lunch", 28, 95),
    ("Taxi", "taxi", 25, 140),
    ("Entertainment", "movie", 45, 160),
    ("Entertainment", "coffee with friends", 18, 70),
    ("Rent", "home supplies", 80, 260),
    ("General", "pharmacy", 20, 120),
    ("General", "mobile service", 30, 90),
]


async def main() -> None:
    random.seed(122078682)
    today = datetime.now(UTC).date()
    first_this_month = today.replace(day=1)
    if first_this_month.month == 1:
        start_date = first_this_month.replace(year=first_this_month.year - 1, month=12)
    else:
        start_date = first_this_month.replace(month=first_this_month.month - 1)
    end_date = today

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create_user(
            telegram_id=TELEGRAM_ID,
            username=USERNAME,
            currency=CURRENCY,
        )
        user.username = USERNAME
        user.currency = CURRENCY

        categories = CategoryService(session)
        for name, *_ in EXPENSE_TEMPLATES:
            await categories.get_or_create(user.id, name)

        existing = await session.execute(
            select(Expense).where(
                Expense.user_id == user.id,
                Expense.description.startswith(SEED_PREFIX),
                Expense.deleted_at.is_(None),
            )
        )
        for expense in existing.scalars():
            expense.deleted_at = datetime.now(UTC)

        expense_service = ExpenseService(session)
        current = start_date
        created = 0
        while current <= end_date:
            for _ in range(random.randint(1, 5)):
                category, description, min_amount, max_amount = random.choice(EXPENSE_TEMPLATES)
                amount = Decimal(str(random.randint(min_amount * 100, max_amount * 100) / 100))
                spent_at = datetime.combine(
                    current,
                    time(hour=random.randint(7, 22), minute=random.choice((0, 10, 20, 30, 40, 50))),
                    tzinfo=UTC,
                )
                await expense_service.add_expense(
                    user_id=user.id,
                    amount=amount.quantize(Decimal("0.01")),
                    description=f"{SEED_PREFIX} {description}",
                    category_name=category,
                    spent_at=spent_at,
                    currency=CURRENCY,
                )
                created += 1
            current += timedelta(days=1)

        await session.commit()
        print(
            f"Seeded {created} expenses for {USERNAME} ({TELEGRAM_ID}) "
            f"from {start_date} to {end_date}."
        )


if __name__ == "__main__":
    asyncio.run(main())
