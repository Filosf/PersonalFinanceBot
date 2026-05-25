from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Category, Expense, MonthlyBudget

BUDGET_THRESHOLDS = (Decimal("0.50"), Decimal("0.75"), Decimal("0.90"), Decimal("1.00"))


@dataclass(slots=True)
class BudgetLine:
    category_id: int | None
    category_name: str | None
    amount: Decimal
    spent: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.spent

    @property
    def ratio(self) -> Decimal:
        if self.amount <= 0:
            return Decimal("0")
        return self.spent / self.amount


class BudgetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_month_budget(
        self,
        user_id: int,
        month_start: date,
        amount: Decimal | None,
        category_id: int | None = None,
    ) -> None:
        budget = await self._get_budget(user_id, month_start, category_id)
        if amount is None or amount <= 0:
            if budget:
                await self.session.delete(budget)
            return

        if category_id is not None:
            await self._require_category(user_id, category_id)

        if budget:
            budget.amount = amount
        else:
            self.session.add(
                MonthlyBudget(
                    user_id=user_id,
                    category_id=category_id,
                    month_start=month_start,
                    amount=amount,
                )
            )
        await self.session.flush()

    async def list_month_budgets(self, user_id: int, month_start: date) -> list[MonthlyBudget]:
        result = await self.session.execute(
            select(MonthlyBudget)
            .options(selectinload(MonthlyBudget.category))
            .where(MonthlyBudget.user_id == user_id, MonthlyBudget.month_start == month_start)
            .order_by(MonthlyBudget.category_id.is_not(None), MonthlyBudget.category_id)
        )
        return list(result.scalars())

    async def report(self, user_id: int, month_start: date) -> list[BudgetLine]:
        budgets = await self.list_month_budgets(user_id, month_start)
        if not budgets:
            return []

        start_at, end_at = month_bounds(month_start)
        total_spent = await self._spent(user_id, start_at, end_at)
        category_spent = await self._category_spent(user_id, start_at, end_at)

        lines: list[BudgetLine] = []
        for budget in budgets:
            if budget.category_id is None:
                spent = total_spent
                category_name = None
            else:
                spent = category_spent.get(budget.category_id, Decimal("0"))
                category_name = budget.category.name if budget.category else None
            lines.append(
                BudgetLine(
                    category_id=budget.category_id,
                    category_name=category_name,
                    amount=Decimal(budget.amount),
                    spent=Decimal(spent),
                )
            )
        return lines

    async def warnings_for_expense(self, expense: Expense) -> list[BudgetLine]:
        month_start = expense.spent_at.date().replace(day=1)
        lines = await self.report(expense.user_id, month_start)
        warnings = []
        for line in lines:
            if line.category_id is not None and line.category_id != expense.category_id:
                continue
            previous_spent = line.spent - Decimal(expense.amount)
            crossed = _crossed_threshold(previous_spent, line.spent, line.amount)
            if crossed is not None:
                warnings.append(line)
        return warnings

    async def _get_budget(
        self, user_id: int, month_start: date, category_id: int | None
    ) -> MonthlyBudget | None:
        category_filter = (
            MonthlyBudget.category_id.is_(None)
            if category_id is None
            else MonthlyBudget.category_id == category_id
        )
        result = await self.session.execute(
            select(MonthlyBudget).where(
                MonthlyBudget.user_id == user_id,
                MonthlyBudget.month_start == month_start,
                category_filter,
            )
        )
        return result.scalar_one_or_none()

    async def _require_category(self, user_id: int, category_id: int) -> Category:
        result = await self.session.execute(
            select(Category).where(Category.id == category_id, Category.user_id == user_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise PermissionError("Category not found")
        return category

    async def _spent(
        self,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
        category_id: int | None = None,
    ) -> Decimal:
        filters = [
            Expense.user_id == user_id,
            Expense.deleted_at.is_(None),
            Expense.spent_at >= start_at,
            Expense.spent_at < end_at,
        ]
        if category_id is not None:
            filters.append(Expense.category_id == category_id)
        result = await self.session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(*filters)
        )
        return Decimal(result.scalar_one())

    async def _category_spent(
        self, user_id: int, start_at: datetime, end_at: datetime
    ) -> dict[int, Decimal]:
        result = await self.session.execute(
            select(Expense.category_id, func.coalesce(func.sum(Expense.amount), 0))
            .where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.spent_at >= start_at,
                Expense.spent_at < end_at,
            )
            .group_by(Expense.category_id)
        )
        return {category_id: Decimal(total) for category_id, total in result}


def month_start_from_iso(value: str | None = None) -> date:
    if not value:
        today = datetime.now(UTC).date()
        return today.replace(day=1)
    if len(value) == 7:
        return date.fromisoformat(f"{value}-01")
    parsed = date.fromisoformat(value)
    return parsed.replace(day=1)


def month_bounds(month_start: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(month_start, datetime.min.time(), tzinfo=UTC)
    if month_start.month == 12:
        end = date(month_start.year + 1, 1, 1)
    else:
        end = date(month_start.year, month_start.month + 1, 1)
    return start_at, datetime.combine(end, datetime.min.time(), tzinfo=UTC)


def _crossed_threshold(
    previous_spent: Decimal, current_spent: Decimal, amount: Decimal
) -> Decimal | None:
    if amount <= 0:
        return None
    previous_ratio = previous_spent / amount
    current_ratio = current_spent / amount
    crossed = [
        threshold
        for threshold in BUDGET_THRESHOLDS
        if previous_ratio < threshold <= current_ratio
    ]
    return crossed[-1] if crossed else None
