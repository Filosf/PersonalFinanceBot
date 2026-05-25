from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category


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
        category.name = name.strip()
        await self.session.flush()
        return category

    async def delete(self, user_id: int, category_id: int) -> None:
        category = await self.require_owned(user_id, category_id)
        await self.session.delete(category)

    async def require_owned(self, user_id: int, category_id: int) -> Category:
        result = await self.session.execute(
            select(Category).where(Category.id == category_id, Category.user_id == user_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise PermissionError("Category not found")
        return category
