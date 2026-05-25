from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.bot.webhook import router as telegram_webhook_router
from app.bot.webhook import setup_telegram_webhook
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.web.routes import router as web_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.bot = None
    if settings.enable_bot_webhook:
        if not settings.bot_token:
            raise RuntimeError("BOT_TOKEN is required when ENABLE_BOT_WEBHOOK=true")
        bot = Bot(settings.bot_token)
        await setup_telegram_webhook(bot)
        app.state.bot = bot
    try:
        yield
    finally:
        bot = app.state.bot
        if bot:
            await bot.session.close()


app = FastAPI(title="Personal Finance Bot Dashboard", lifespan=lifespan)
app.state.templates = Jinja2Templates(directory="app/web/templates")
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(api_router)
app.include_router(telegram_webhook_router)
app.include_router(web_router)
