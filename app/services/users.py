from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.i18n import normalize_locale
from app.db.models import Category, User
from app.services.defaults import DEFAULT_CATEGORIES


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        timezone: str | None = None,
        currency: str | None = None,
        locale: str | None = None,
        update_locale: bool = False,
    ) -> User:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            if username and user.username != username:
                user.username = username
            if locale and update_locale:
                user.locale = normalize_locale(locale)
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            timezone=timezone or self.settings.default_timezone,
            currency=currency or self.settings.default_currency,
            locale=normalize_locale(locale),
        )
        self.session.add(user)
        await self.session.flush()

        self.session.add_all([Category(user_id=user.id, name=name) for name in DEFAULT_CATEGORIES])
        await self.session.flush()
        return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def set_locale(self, user_id: int, locale: str) -> User:
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.locale = normalize_locale(locale)
        await self.session.flush()
        return user
