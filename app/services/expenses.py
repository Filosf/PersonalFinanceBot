from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Category, Expense
from app.services.categories import CategoryService


@dataclass(slots=True)
class ExpenseFilters:
    date_from: datetime | None = None
    date_to: datetime | None = None
    category_id: int | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    text: str | None = None


class ExpenseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.categories = CategoryService(session)

    async def add_expense(
        self,
        user_id: int,
        amount: Decimal,
        description: str = "",
        category_name: str | None = None,
        spent_at: datetime | None = None,
        currency: str = "ILS",
        kind: str = "expense",
    ) -> Expense:
        if kind not in {"expense", "income"}:
            raise ValueError("Unknown expense kind")
        if kind == "income":
            category_name = "Income"
        category = await self._pick_category(user_id, description, category_name)
        if category.name == "Income":
            kind = "income"
        expense = Expense(
            user_id=user_id,
            category_id=category.id,
            amount=amount,
            currency=currency,
            kind=kind,
            description=description,
            spent_at=spent_at or datetime.now(UTC),
        )
        self.session.add(expense)
        await self.session.flush()
        await self.session.refresh(expense, ["category"])
        return expense

    async def update_expense(
        self,
        user_id: int,
        expense_id: int,
        amount: Decimal | None = None,
        category_id: int | None = None,
        description: str | None = None,
        spent_at: datetime | None = None,
        kind: str | None = None,
    ) -> Expense:
        expense = await self.require_owned(user_id, expense_id)
        if amount is not None:
            expense.amount = amount
        if category_id is not None:
            category = await self.categories.require_owned(user_id, category_id)
            expense.category_id = category_id
            expense.kind = "income" if category.name == "Income" else "expense"
        if description is not None:
            expense.description = description
        if spent_at is not None:
            expense.spent_at = spent_at
        if kind is not None:
            if kind not in {"expense", "income"}:
                raise ValueError("Unknown expense kind")
            expense.kind = kind
            if kind == "income":
                income = await self.categories.get_or_create(user_id, "Income")
                expense.category_id = income.id
        await self.session.flush()
        await self.session.refresh(expense, ["category"])
        return expense

    async def delete_expense(self, user_id: int, expense_id: int) -> None:
        expense = await self.require_owned(user_id, expense_id)
        expense.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def delete_last(self, user_id: int) -> Expense | None:
        expense = await self.get_last(user_id)
        if not expense:
            return None
        expense.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return expense

    async def get_last(self, user_id: int) -> Expense | None:
        result = await self.session.execute(
            select(Expense)
            .options(selectinload(Expense.category))
            .where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
            .order_by(Expense.spent_at.desc(), Expense.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_expenses(
        self,
        user_id: int,
        filters: ExpenseFilters | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Expense]:
        stmt = self._filtered_query(user_id, filters)
        result = await self.session.execute(
            stmt.options(selectinload(Expense.category))
            .order_by(Expense.spent_at.desc(), Expense.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars())

    async def summary(self, user_id: int, date_from: datetime, date_to: datetime) -> dict:
        total_result = await self.session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id)).where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.kind == "expense",
                Expense.spent_at >= date_from,
                Expense.spent_at < date_to,
            )
        )
        total, count = total_result.one()

        categories_result = await self.session.execute(
            select(
                Category.name,
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            )
            .join(Expense, Expense.category_id == Category.id)
            .where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.kind == "expense",
                Expense.spent_at >= date_from,
                Expense.spent_at < date_to,
            )
            .group_by(Category.name)
            .order_by(func.sum(Expense.amount).desc())
        )
        return {
            "total": total,
            "count": count,
            "categories": [
                {"category": name, "total": amount, "count": category_count}
                for name, amount, category_count in categories_result
            ],
        }

    async def cashflow_summary(self, user_id: int, date_from: datetime, date_to: datetime) -> dict:
        result = await self.session.execute(
            select(
                Expense.kind,
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            )
            .where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.spent_at >= date_from,
                Expense.spent_at < date_to,
            )
            .group_by(Expense.kind)
        )
        totals = {
            kind: {"total": Decimal(amount), "count": count}
            for kind, amount, count in result
        }
        income = totals.get("income", {"total": Decimal("0"), "count": 0})
        expense = totals.get("expense", {"total": Decimal("0"), "count": 0})
        return {
            "income": income["total"],
            "expense": expense["total"],
            "balance": income["total"] - expense["total"],
            "count": income["count"] + expense["count"],
        }

    async def time_series(
        self, user_id: int, date_from: datetime, date_to: datetime, granularity: str
    ) -> list[dict]:
        bucket = func.date_trunc(granularity, Expense.spent_at).label("bucket")
        result = await self.session.execute(
            select(bucket, func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.id))
            .where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.spent_at >= date_from,
                Expense.spent_at < date_to,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        return [
            {"bucket": bucket_value, "total": amount, "count": count}
            for bucket_value, amount, count in result
        ]

    async def cashflow_time_series(
        self, user_id: int, date_from: datetime, date_to: datetime, granularity: str
    ) -> list[dict]:
        bucket = func.date_trunc(granularity, Expense.spent_at).label("bucket")
        result = await self.session.execute(
            select(
                bucket,
                Expense.kind,
                func.coalesce(func.sum(Expense.amount), 0),
                func.count(Expense.id),
            )
            .where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.spent_at >= date_from,
                Expense.spent_at < date_to,
            )
            .group_by(bucket, Expense.kind)
            .order_by(bucket)
        )
        by_bucket: dict[datetime, dict] = {}
        for bucket_value, kind, amount, count in result:
            item = by_bucket.setdefault(
                bucket_value,
                {
                    "bucket": bucket_value,
                    "income": Decimal("0"),
                    "expense": Decimal("0"),
                    "count": 0,
                },
            )
            item[kind] = Decimal(amount)
            item["count"] += count
        return list(by_bucket.values())

    async def require_owned(self, user_id: int, expense_id: int) -> Expense:
        result = await self.session.execute(
            select(Expense)
            .options(selectinload(Expense.category))
            .where(
                Expense.id == expense_id,
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
            )
        )
        expense = result.scalar_one_or_none()
        if not expense:
            raise PermissionError("Expense not found")
        return expense

    async def _pick_category(
        self, user_id: int, description: str, category_name: str | None
    ) -> Category:
        if category_name:
            return await self.categories.get_or_create(user_id, category_name)

        normalized = description.lower()
        for name in ("Food", "Taxi", "Rent", "Entertainment"):
            if name.lower() in normalized:
                return await self.categories.get_or_create(user_id, name)
        return await self.categories.get_or_create(user_id, "General")

    def _filtered_query(
        self, user_id: int, filters: ExpenseFilters | None
    ) -> Select[tuple[Expense]]:
        stmt = select(Expense).where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
        if not filters:
            return stmt
        if filters.date_from:
            stmt = stmt.where(Expense.spent_at >= filters.date_from)
        if filters.date_to:
            stmt = stmt.where(Expense.spent_at < filters.date_to)
        if filters.category_id:
            stmt = stmt.where(Expense.category_id == filters.category_id)
        if filters.min_amount is not None:
            stmt = stmt.where(Expense.amount >= filters.min_amount)
        if filters.max_amount is not None:
            stmt = stmt.where(Expense.amount <= filters.max_amount)
        if filters.text:
            stmt = stmt.where(Expense.description.ilike(f"%{filters.text}%"))
        return stmt
