from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Expense, User


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def stats(self) -> dict[str, int | str]:
        users = await self.session.scalar(select(func.count(User.id)))
        categories = await self.session.scalar(select(func.count(Category.id)))
        expenses = await self.session.scalar(
            select(func.count(Expense.id)).where(Expense.deleted_at.is_(None))
        )
        deleted_expenses = await self.session.scalar(
            select(func.count(Expense.id)).where(Expense.deleted_at.is_not(None))
        )
        total_amount = await self.session.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.deleted_at.is_(None))
        )
        return {
            "users": users or 0,
            "categories": categories or 0,
            "expenses": expenses or 0,
            "deleted_expenses": deleted_expenses or 0,
            "total_amount": f"{total_amount or 0}",
        }

    async def users(self, limit: int = 20) -> list[User]:
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit)
        )
        return list(result.scalars())

    async def db_health(self) -> dict[str, str]:
        value = await self.session.scalar(text("select 1"))
        users = await self.session.scalar(select(func.count(User.id)))
        return {"status": "ok" if value == 1 else "failed", "users": str(users or 0)}
