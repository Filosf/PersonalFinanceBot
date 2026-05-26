from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_session
from app.services.access_tokens import AccessTokenError, verify_access_token
from app.services.users import UserService


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_telegram_id: int | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    telegram_id: int | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(maxsplit=1)[1]
        try:
            telegram_id = verify_access_token(token)
        except AccessTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
    elif get_settings().allow_developer_login and x_telegram_id is not None:
        telegram_id = x_telegram_id

    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
        )
    user = await UserService(session).get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
