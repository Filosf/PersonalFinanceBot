from contextlib import asynccontextmanager
from datetime import UTC, timedelta
from datetime import timezone as fixed_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.bot.webhook import router as telegram_webhook_router
from app.bot.webhook import setup_telegram_webhook
from app.core.config import get_settings
from app.core.i18n import category_label
from app.core.logging import configure_logging
from app.core.runtime_state import record_error
from app.web.routes import router as web_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.validate_runtime_secrets()
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
app.state.templates.env.filters["category_label"] = category_label


def datetime_local(value, timezone: str):
    tz = _timezone(timezone)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz)


def _timezone(timezone: str):
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        if timezone == "Asia/Jerusalem":
            return fixed_timezone(timedelta(hours=3))
        return UTC


app.state.templates.env.filters["datetime_local"] = datetime_local
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(api_router)
app.include_router(telegram_webhook_router)
app.include_router(web_router)


@app.middleware("http")
async def capture_errors(request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        record_error(f"{request.method} {request.url.path}", exc)
        raise
