from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Expense
from app.services.defaults import DEFAULT_CATEGORIES

PROTECTED_CATEGORIES = {"General", "Income"}


def is_default_category(name: str) -> bool:
    return name in DEFAULT_CATEGORIES


def is_protected_category(name: str) -> bool:
    return name in PROTECTED_CATEGORIES


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_categories(self, user_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.user_id == user_id).order_by(Category.name)
        )
        return list(result.scalars())

    async def get_by_name(self, user_id: int, name: str) -> Category | None:
        result = await self.session.execute(
            select(Category).where(Category.user_id == user_id, Category.name.ilike(name))
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int, name: str) -> Category:
        category = await self.get_by_name(user_id, name)
        if category:
            return category
        category = Category(user_id=user_id, name=name.strip())
        self.session.add(category)
        await self.session.flush()
        return category

    async def rename(self, user_id: int, category_id: int, name: str) -> Category:
        category = await self.require_owned(user_id, category_id)
        if is_protected_category(category.name):
            raise ValueError("Protected categories cannot be renamed")
        category.name = name.strip()
        await self.session.flush()
        return category

    async def delete(self, user_id: int, category_id: int) -> None:
        category = await self.require_owned(user_id, category_id)
        if is_protected_category(category.name):
            raise ValueError("Protected categories cannot be deleted")
        await self.session.delete(category)

    async def delete_or_merge(
        self, user_id: int, category_id: int, merge_category_id: int | None = None
    ) -> None:
        category = await self.require_owned(user_id, category_id)
        if is_protected_category(category.name):
            raise ValueError("Protected categories cannot be deleted")

        expense_count = await self.expense_count(user_id, category_id)
        if expense_count:
            if merge_category_id is None or merge_category_id == category_id:
                raise ValueError("Choose a category to merge into")
            target = await self.require_owned(user_id, merge_category_id)
            if target.id == category.id:
                raise ValueError("Choose another category to merge into")
            if target.name == "Income":
                raise ValueError("Expenses cannot be merged into Income")
            await self.session.execute(
                Expense.__table__.update()
                .where(Expense.user_id == user_id, Expense.category_id == category_id)
                .values(category_id=target.id)
            )
        await self.session.delete(category)

    async def expense_count(self, user_id: int, category_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Expense.id)).where(
                Expense.user_id == user_id,
                Expense.category_id == category_id,
            )
        )
        return int(result.scalar_one())

    async def require_owned(self, user_id: int, category_id: int) -> Category:
        result = await self.session.execute(
            select(Category).where(Category.id == category_id, Category.user_id == user_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise PermissionError("Category not found")
        return category
