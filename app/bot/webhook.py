from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, HTTPException, Request, status

from app.bot.handlers import router as bot_router
from app.core.config import get_settings

router = APIRouter()
dispatcher = Dispatcher()
dispatcher.include_router(bot_router)


@router.post(get_settings().telegram_webhook_path)
async def telegram_webhook(request: Request) -> dict[str, bool]:
    settings = get_settings()
    bot: Bot | None = request.app.state.bot
    if not bot:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}


async def setup_telegram_webhook(bot: Bot) -> None:
    settings = get_settings()
    await bot.set_webhook(
        settings.telegram_webhook_url,
        secret_token=settings.telegram_webhook_secret or None,
        drop_pending_updates=True,
    )
