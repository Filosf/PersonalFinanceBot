from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode, urlparse

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import expense_actions
from app.core.config import get_settings
from app.core.i18n import tr
from app.db.session import SessionLocal
from app.services.access_tokens import create_access_token
from app.services.categories import CategoryService
from app.services.expenses import ExpenseService
from app.services.parsing import parse_expense_text
from app.services.users import UserService

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()
    await message.answer(
        tr(user.locale, "welcome"),
        parse_mode="Markdown",
        reply_markup=_main_menu(user.locale),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()
    await message.answer(tr(user.locale, "help"), reply_markup=_main_menu(user.locale))


@router.message(F.text.startswith("/помощь"))
async def help_command_ru(message: Message) -> None:
    await help_command(message)


@router.message(Command("language"))
async def language_command(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()
    await message.answer(
        tr(user.locale, "choose_language"),
        reply_markup=_language_keyboard(),
    )


@router.message(F.text.startswith("/язык"))
async def language_command_ru(message: Message) -> None:
    await language_command(message)


@router.message(Command("web"))
async def web_login(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()

    token = create_access_token(user.telegram_id)
    settings = get_settings()
    login_url = f"{settings.public_base_url}/login/token?{urlencode({'token': token})}"
    keyboard = None
    login_line = login_url
    if _is_public_http_url(login_url):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=tr(user.locale, "open_dashboard"), url=login_url)]
            ]
        )
        login_line = f"[{tr(user.locale, 'open_dashboard')}]({login_url})"
    await message.answer(
        f"{tr(user.locale, 'web_key_intro')}\n"
        f"`{token}`\n\n"
        f"{login_line}\n\n"
        f"{tr(user.locale, 'valid_for_minutes', minutes=settings.access_token_ttl_minutes)}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@router.message(F.text.in_({tr("en", "menu_web"), tr("ru", "menu_web")}))
async def web_login_menu(message: Message) -> None:
    await web_login(message)


@router.message(F.text.in_({tr("en", "menu_help"), tr("ru", "menu_help")}))
async def help_menu(message: Message) -> None:
    await help_command(message)


@router.message(
    F.text.startswith("/сайт") | F.text.startswith("/веб") | F.text.startswith("/войти")
)
async def web_login_ru(message: Message) -> None:
    await web_login(message)


@router.message(Command("categories"))
async def categories(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        items = await CategoryService(session).list_categories(user.id)
    await message.answer(
        "\n".join(category.name for category in items) or tr(user.locale, "no_categories")
    )


@router.message(F.text.startswith("/категории"))
async def categories_ru(message: Message) -> None:
    await categories(message)


@router.message(Command("add_category"))
async def add_category(message: Message, command: CommandObject) -> None:
    name = (command.args or "").strip()
    if not name:
        await message.answer(tr(_telegram_locale(message), "usage_add_category"))
        return
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        category = await CategoryService(session).get_or_create(user.id, name)
        await session.commit()
    await message.answer(tr(user.locale, "category_added", name=category.name))


@router.message(F.text.startswith("/добавить_категорию"))
async def add_category_ru(message: Message) -> None:
    name = _text_args(message.text)
    if not name:
        await message.answer(tr(_telegram_locale(message), "usage_add_category"))
        return
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        category = await CategoryService(session).get_or_create(user.id, name)
        await session.commit()
    await message.answer(tr(user.locale, "category_added", name=category.name))


@router.message(Command("month"))
async def month(message: Message, command: CommandObject) -> None:
    try:
        start_at, end_at = _month_range(command.args)
    except ValueError:
        await message.answer(tr(_telegram_locale(message), "usage_month"))
        return
    await _send_summary(message, start_at, end_at)


@router.message(F.text.startswith("/месяц"))
async def month_ru(message: Message) -> None:
    try:
        start_at, end_at = _month_range(_text_args(message.text))
    except ValueError:
        await message.answer(tr(_telegram_locale(message), "usage_month"))
        return
    await _send_summary(message, start_at, end_at)


@router.message(Command("range"))
async def range_command(message: Message, command: CommandObject) -> None:
    try:
        start_raw, end_raw = (command.args or "").split(maxsplit=1)
        start_at = datetime.fromisoformat(start_raw).replace(tzinfo=UTC)
        end_at = datetime.fromisoformat(end_raw).replace(tzinfo=UTC)
    except ValueError:
        await message.answer(tr(_telegram_locale(message), "usage_range"))
        return
    await _send_summary(message, start_at, end_at)


@router.message(F.text.startswith("/период"))
async def range_command_ru(message: Message) -> None:
    try:
        start_raw, end_raw = _text_args(message.text).split(maxsplit=1)
        start_at = datetime.fromisoformat(start_raw).replace(tzinfo=UTC)
        end_at = datetime.fromisoformat(end_raw).replace(tzinfo=UTC)
    except ValueError:
        await message.answer(tr(_telegram_locale(message), "usage_range"))
        return
    await _send_summary(message, start_at, end_at)


@router.message(Command("last"))
async def last(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        expense = await ExpenseService(session).get_last(user.id)
    if not expense:
        await message.answer(tr(user.locale, "no_expenses_yet"))
        return
    await message.answer(_format_expense(expense))


@router.message(F.text.startswith("/последний"))
async def last_ru(message: Message) -> None:
    await last(message)


@router.message(Command("delete_last"))
async def delete_last(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        expense = await ExpenseService(session).delete_last(user.id)
        await session.commit()
    if not expense:
        await message.answer(tr(user.locale, "no_expenses_to_delete"))
        return
    await message.answer(f"{tr(user.locale, 'deleted')}: {_format_expense(expense)}")


@router.message(F.text.startswith("/удалить_последний"))
async def delete_last_ru(message: Message) -> None:
    await delete_last(message)


@router.callback_query(F.data.startswith("cat:"))
async def set_category(callback: CallbackQuery) -> None:
    _, expense_id, category_id = callback.data.split(":")
    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        expense = await ExpenseService(session).update_expense(
            user.id, int(expense_id), category_id=int(category_id)
        )
        await session.commit()
        categories = await CategoryService(session).list_categories(user.id)
    try:
        await callback.message.edit_text(
            _format_added(expense, user.locale),
            reply_markup=expense_actions(expense, categories, user.locale),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
    await callback.answer(tr(user.locale, "category_updated"))


@router.callback_query(F.data.startswith("del:"))
async def delete_expense(callback: CallbackQuery) -> None:
    _, expense_id = callback.data.split(":")
    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        await ExpenseService(session).delete_expense(user.id, int(expense_id))
        await session.commit()
    await callback.message.edit_text(tr(user.locale, "expense_deleted"))
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery) -> None:
    _, locale = callback.data.split(":", maxsplit=1)
    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        user = await UserService(session).set_locale(user.id, locale)
        await session.commit()
    try:
        await callback.message.edit_text(
            tr(user.locale, "language_updated"),
            reply_markup=_language_keyboard(user.locale),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
    await callback.message.answer(
        tr(user.locale, "language_updated"),
        reply_markup=_main_menu(user.locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit:"))
async def edit_hint(callback: CallbackQuery) -> None:
    await callback.answer(tr(_telegram_locale(callback), "edit_hint"), show_alert=True)


@router.message(F.text)
async def add_expense(message: Message) -> None:
    try:
        amount, description = parse_expense_text(message.text or "")
    except ValueError as exc:
        key = "amount_positive_error" if "greater than zero" in str(exc) else "amount_error"
        await message.answer(tr(_telegram_locale(message), key))
        return

    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        expense = await ExpenseService(session).add_expense(
            user.id,
            amount,
            description=description,
            currency=user.currency,
        )
        categories = await CategoryService(session).list_categories(user.id)
        await session.commit()
    await message.answer(
        _format_added(expense, user.locale),
        reply_markup=expense_actions(expense, categories, user.locale),
    )


async def _ensure_user(session: AsyncSession, message: Message):
    return await _ensure_user_from_telegram(session, message.from_user)


async def _ensure_user_from_telegram(session: AsyncSession, tg_user):
    return await UserService(session).get_or_create_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        locale=getattr(tg_user, "language_code", None),
    )


async def _send_summary(message: Message, start_at: datetime, end_at: datetime) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        summary = await ExpenseService(session).summary(user.id, start_at, end_at)

    lines = [
        f"{tr(user.locale, 'period')}: {start_at.date()} - {end_at.date()}",
        f"{tr(user.locale, 'total')}: {Decimal(summary['total']):.2f} {user.currency}",
        f"{tr(user.locale, 'operations')}: {summary['count']}",
        "",
        f"{tr(user.locale, 'by_category')}:",
    ]
    lines.extend(
        f"{item['category']}: {Decimal(item['total']):.2f} ({item['count']})"
        for item in summary["categories"]
    )
    await message.answer("\n".join(lines))


def _month_range(value: str | None) -> tuple[datetime, datetime]:
    if value:
        year, month_number = map(int, value.strip().split("-", maxsplit=1))
    else:
        now = datetime.now(UTC)
        year, month_number = now.year, now.month
    start_at = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end_at = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end_at = datetime(year, month_number + 1, 1, tzinfo=UTC)
    return start_at, end_at


def _format_added(expense, locale: str) -> str:
    return (
        f"{tr(locale, 'expense_added')}: {expense.amount} {expense.currency}\n"
        f"{tr(locale, 'category')}: {expense.category.name}\n"
        f"{tr(locale, 'description')}: {expense.description or '-'}"
    )


def _format_expense(expense) -> str:
    return (
        f"{expense.spent_at:%Y-%m-%d %H:%M} - {expense.amount} {expense.currency} - "
        f"{expense.category.name} - {expense.description or '-'}"
    )


def _telegram_locale(source) -> str | None:
    user = getattr(source, "from_user", None)
    return getattr(user, "language_code", None)


def _text_args(text: str | None) -> str:
    parts = (text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _language_keyboard(active_locale: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✓ English" if active_locale == "en" else "English"),
                    callback_data="lang:en",
                ),
                InlineKeyboardButton(
                    text=("✓ Русский" if active_locale == "ru" else "Русский"),
                    callback_data="lang:ru",
                ),
            ]
        ]
    )


def _main_menu(locale: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=tr(locale, "menu_web")),
                KeyboardButton(text=tr(locale, "menu_help")),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def _is_public_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname not in {"localhost", "127.0.0.1", "::1"}
