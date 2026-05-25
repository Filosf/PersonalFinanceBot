from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.services.users import UserService


async def get_current_user(
    x_telegram_id: int | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if x_telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Telegram-Id required",
        )
    user = await UserService(session).get_by_telegram_id(x_telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
