import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
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

from app.bot.keyboards import expense_actions, receipt_draft_actions
from app.core.config import get_settings
from app.core.i18n import category_label, tr
from app.core.runtime_state import get_last_errors
from app.db.session import SessionLocal
from app.services.access_tokens import create_access_token
from app.services.admin import AdminService
from app.services.budgets import BudgetService, month_start_from_iso
from app.services.categories import CategoryService
from app.services.expenses import ExpenseService
from app.services.parsing import parse_expense_text
from app.services.receipt_drafts import ReceiptDraftService
from app.services.receipt_ocr import ParsedReceipt, extract_receipt_from_image
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


@router.message(Command("commands"))
async def commands_command(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()
    text = tr(user.locale, "commands")
    if _is_admin(message):
        text = f"{text}\n\n{tr(user.locale, 'admin_help')}"
    await message.answer(text, reply_markup=_main_menu(user.locale))


@router.message(F.text.startswith("/помощь"))
async def help_command_ru(message: Message) -> None:
    await help_command(message)


@router.message(F.text.startswith("/команды"))
async def commands_command_ru(message: Message) -> None:
    await commands_command(message)


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
    if _is_public_http_url(login_url):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=tr(user.locale, "open_dashboard"), url=login_url)]
            ]
        )
        await message.answer(
            f"[{tr(user.locale, 'open_dashboard')}]({login_url})\n"
            f"{tr(user.locale, 'valid_for_minutes', minutes=settings.access_token_ttl_minutes)}",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return

    await message.answer(
        f"{tr(user.locale, 'web_key_intro')}\n"
        f"{token}\n\n"
        f"{login_url}\n\n"
        f"{tr(user.locale, 'valid_for_minutes', minutes=settings.access_token_ttl_minutes)}",
    )


@router.message(F.text.in_({tr("en", "menu_web"), tr("ru", "menu_web")}))
async def web_login_menu(message: Message) -> None:
    await web_login(message)


@router.message(F.text.in_({tr("en", "menu_commands"), tr("ru", "menu_commands")}))
async def commands_menu(message: Message) -> None:
    await commands_command(message)


@router.message(F.text.in_({tr("en", "menu_help"), tr("ru", "menu_help")}))
async def legacy_help_menu(message: Message) -> None:
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
        "\n".join(category_label(category.name, user.locale) for category in items)
        or tr(user.locale, "no_categories")
    )


@router.message(F.text.startswith("/категории"))
async def categories_ru(message: Message) -> None:
    await categories(message)


@router.message(Command("add_category"))
async def add_category(message: Message, command: CommandObject) -> None:
    name = (command.args or "").strip()
    if not name:
        async with SessionLocal() as session:
            user = await _ensure_user(session, message)
        await message.answer(tr(user.locale, "usage_add_category"))
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
        async with SessionLocal() as session:
            user = await _ensure_user(session, message)
        await message.answer(tr(user.locale, "usage_add_category"))
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
    await message.answer(_format_expense(expense, user.locale))


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
    await message.answer(f"{tr(user.locale, 'deleted')}: {_format_expense(expense, user.locale)}")


@router.message(F.text.startswith("/удалить_последний"))
async def delete_last_ru(message: Message) -> None:
    await delete_last(message)


@router.message(Command("budgets"))
async def budgets(message: Message) -> None:
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        report = await BudgetService(session).report(user.id, month_start_from_iso())
    await message.answer(_format_budget_report(report, user.locale, user.currency))


@router.message(F.text.startswith("/бюджеты"))
async def budgets_ru(message: Message) -> None:
    await budgets(message)


@router.message(F.photo)
async def receipt_photo(message: Message) -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        user = await _ensure_user(session, message)
        await session.commit()
        locale = user.locale
        telegram_user_id = user.telegram_id

    processing = await message.answer(tr(locale, "receipt_photo_processing"))
    photo = message.photo[-1]
    max_bytes = settings.ocr_max_image_mb * 1024 * 1024
    if photo.file_size and photo.file_size > max_bytes:
        await processing.edit_text(
            _format_receipt_failure(
                locale,
                "image_too_large",
                max_image_mb=settings.ocr_max_image_mb,
            )
        )
        return

    try:
        image_buffer = BytesIO()
        await message.bot.download(photo, destination=image_buffer)
        image_bytes = image_buffer.getvalue()
    except Exception:
        await processing.edit_text(
            f"{tr(locale, 'receipt_ocr_failed')}\n"
            f"{tr(locale, 'receipt_manual_hint')}"
        )
        return

    result = extract_receipt_from_image(image_bytes, settings)
    async with SessionLocal() as session:
        if not result.success or not result.parsed or not result.parsed.amount:
            await session.commit()
            text = _format_receipt_failure(locale, result.error)
            await processing.edit_text(text)
            return

        draft = await ReceiptDraftService(session).create_draft(
            telegram_user_id=telegram_user_id,
            amount=result.parsed.amount,
            currency=result.parsed.currency,
            spent_at=result.parsed.spent_at,
            merchant=result.parsed.merchant,
            raw_text=result.parsed.raw_text,
            confidence=result.parsed.confidence,
        )
        await session.commit()

    await processing.edit_text(
        _format_receipt_recognized(result.parsed, locale),
        reply_markup=receipt_draft_actions(str(draft.id), locale),
    )


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
            reply_markup=(
                expense_actions(expense, categories, user.locale)
                if expense.kind == "expense"
                else None
            ),
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


@router.callback_query(F.data.startswith("receipt_confirm_date:"))
async def receipt_confirm_with_date(callback: CallbackQuery) -> None:
    await _receipt_confirm(callback, use_draft_date=True)


@router.callback_query(F.data.startswith("receipt_confirm_today:"))
async def receipt_confirm_today(callback: CallbackQuery) -> None:
    await _receipt_confirm(callback, use_draft_date=False)


async def _receipt_confirm(callback: CallbackQuery, use_draft_date: bool) -> None:
    draft_id = _receipt_draft_id(callback.data)
    if draft_id is None:
        await callback.answer(tr(_telegram_locale(callback), "receipt_not_found"), show_alert=True)
        return

    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        drafts = ReceiptDraftService(session)
        draft = await drafts.get_pending_draft(draft_id, user.telegram_id)
        if not draft:
            await session.rollback()
            await _edit_callback_message(callback, tr(user.locale, "receipt_not_found"))
            await callback.answer(tr(user.locale, "receipt_not_found"), show_alert=True)
            return

        description = draft.merchant or "Receipt"
        spent_at = (
            datetime.combine(draft.spent_at, datetime.min.time(), tzinfo=UTC)
            if use_draft_date and draft.spent_at
            else None
        )
        try:
            expense = await ExpenseService(session).add_expense(
                user.id,
                draft.amount,
                description=description,
                spent_at=spent_at,
                currency=draft.currency or user.currency,
            )
            await drafts.confirm_draft(draft.id, user.telegram_id)
            await session.commit()
        except Exception:
            await session.rollback()
            await callback.answer(tr(user.locale, "receipt_confirm_error"), show_alert=True)
            return

    await _edit_callback_message(
        callback,
        f"{tr(user.locale, 'receipt_saved')}\n\n{_format_added(expense, user.locale)}",
    )
    await callback.answer(tr(user.locale, "receipt_saved"))


@router.callback_query(F.data.startswith("receipt_cancel:"))
async def receipt_cancel(callback: CallbackQuery) -> None:
    draft_id = _receipt_draft_id(callback.data)
    if draft_id is None:
        await callback.answer(tr(_telegram_locale(callback), "receipt_not_found"), show_alert=True)
        return

    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        drafts = ReceiptDraftService(session)
        draft = await drafts.get_pending_draft(draft_id, user.telegram_id)
        if not draft:
            await session.rollback()
            await _edit_callback_message(callback, tr(user.locale, "receipt_not_found"))
            await callback.answer(tr(user.locale, "receipt_not_found"), show_alert=True)
            return
        await drafts.cancel_draft(draft.id, user.telegram_id)
        await session.commit()

    await _edit_callback_message(callback, tr(user.locale, "receipt_cancelled"))
    await callback.answer(tr(user.locale, "receipt_cancelled"))


@router.callback_query(F.data.startswith("receipt_manual:"))
async def receipt_manual(callback: CallbackQuery) -> None:
    draft_id = _receipt_draft_id(callback.data)
    if draft_id is None:
        await callback.answer(tr(_telegram_locale(callback), "receipt_not_found"), show_alert=True)
        return

    async with SessionLocal() as session:
        user = await _ensure_user_from_telegram(session, callback.from_user)
        drafts = ReceiptDraftService(session)
        draft = await drafts.get_pending_draft(draft_id, user.telegram_id)
        if draft:
            await drafts.cancel_draft(draft.id, user.telegram_id)
            await session.commit()
        else:
            await session.rollback()

    await _edit_callback_message(callback, tr(user.locale, "receipt_enter_manually"))
    await callback.message.answer(tr(user.locale, "receipt_enter_manually"))
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


@router.message(Command("admin_stats"))
async def admin_stats(message: Message) -> None:
    if not _is_admin(message):
        return
    async with SessionLocal() as session:
        stats = await AdminService(session).stats()
    await message.answer(
        "Admin stats\n"
        f"Users: {stats['users']}\n"
        f"Categories: {stats['categories']}\n"
        f"Active expenses: {stats['expenses']}\n"
        f"Deleted expenses: {stats['deleted_expenses']}\n"
        f"Total amount: {stats['total_amount']}"
    )


@router.message(Command("admin_users"))
async def admin_users(message: Message) -> None:
    if not _is_admin(message):
        return
    async with SessionLocal() as session:
        users = await AdminService(session).users()
    if not users:
        await message.answer("No users found.")
        return
    lines = ["Admin users"]
    lines.extend(
        f"{user.id}: @{user.username or '-'} | tg={user.telegram_id} | "
        f"{user.currency} | {user.locale}"
        for user in users
    )
    await message.answer("\n".join(lines))


@router.message(Command("admin_logs"))
async def admin_logs(message: Message) -> None:
    if not _is_admin(message):
        return
    await message.answer(
        "Logs are emitted to stdout as structured JSON.\n"
        "On Render: open the service dashboard -> Logs."
    )


@router.message(Command("admin_last_errors"))
async def admin_last_errors(message: Message) -> None:
    if not _is_admin(message):
        return
    errors = get_last_errors()
    if not errors:
        await message.answer("No captured runtime errors.")
        return
    lines = ["Last errors"]
    for error in errors:
        lines.append(
            f"{error['at']} | {error['source']} | {error['type']}: {error['message']}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("admin_db_health"))
async def admin_db_health(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        async with SessionLocal() as session:
            health = await AdminService(session).db_health()
    except Exception as exc:
        await message.answer(f"DB health: failed\n{exc.__class__.__name__}: {exc}")
        return
    await message.answer(f"DB health: {health['status']}\nUsers: {health['users']}")


@router.message(F.text)
async def add_expense(message: Message) -> None:
    try:
        amount, description, kind = parse_expense_text(message.text or "")
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
            kind=kind,
        )
        budget_warnings = []
        if kind == "expense":
            budget_warnings = await BudgetService(session).warnings_for_expense(expense)
        categories = await CategoryService(session).list_categories(user.id)
        await session.commit()
    text = _format_added(expense, user.locale)
    if budget_warnings:
        text = f"{text}\n\n" + "\n\n".join(
            _format_budget_alert(line, user.locale, user.currency) for line in budget_warnings
        )
    reply_markup = expense_actions(expense, categories, user.locale) if kind == "expense" else None
    await message.answer(text, reply_markup=reply_markup)


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
        service = ExpenseService(session)
        summary = await service.summary(user.id, start_at, end_at)
        cashflow = await service.cashflow_summary(user.id, start_at, end_at)

    lines = [
        f"{tr(user.locale, 'period')}: {start_at.date()} - {end_at.date()}",
        f"{tr(user.locale, 'total_expense')}: {Decimal(cashflow['expense']):.2f} {user.currency}",
        f"{tr(user.locale, 'total_income')}: {Decimal(cashflow['income']):.2f} {user.currency}",
        f"{tr(user.locale, 'balance')}: {Decimal(cashflow['balance']):.2f} {user.currency}",
        f"{tr(user.locale, 'operations')}: {cashflow['count']}",
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
    title = "income_added" if expense.kind == "income" else "expense_added"
    lines = [f"{tr(locale, title)}: {expense.amount} {expense.currency}"]
    if expense.kind == "expense":
        lines.append(f"{tr(locale, 'category')}: {category_label(expense.category.name, locale)}")
    lines.append(f"{tr(locale, 'description')}: {expense.description or '-'}")
    return "\n".join(lines)


def _format_expense(expense, locale: str | None) -> str:
    if expense.kind == "income":
        return (
            f"{expense.spent_at:%Y-%m-%d %H:%M} - +{expense.amount} {expense.currency} - "
            f"{expense.description or '-'}"
        )
    return (
        f"{expense.spent_at:%Y-%m-%d %H:%M} - {expense.amount} {expense.currency} - "
        f"{category_label(expense.category.name, locale)} - "
        f"{expense.description or '-'}"
    )


def _format_budget_report(report, locale: str | None, currency: str) -> str:
    month = datetime.now(UTC).strftime("%Y-%m")
    if not report:
        return tr(locale, "budget_report_empty")
    lines = [tr(locale, "budget_report_title", month=month)]
    for line in report:
        name = tr(locale, "total") if line.category_id is None else category_label(
            line.category_name, locale
        )
        lines.append(
            f"{name}: {line.spent:.2f} / {line.amount:.2f} {currency} "
            f"({line.remaining:.2f} {tr(locale, 'remaining')})"
        )
    return "\n".join(lines)


def _format_budget_alert(line, locale: str | None, currency: str) -> str:
    name = tr(locale, "total") if line.category_id is None else category_label(
        line.category_name, locale
    )
    return tr(
        locale,
        "budget_alert",
        name=name,
        percent=line.ratio * Decimal("100"),
        spent=line.spent,
        amount=line.amount,
        remaining=line.remaining,
        currency=currency,
    )


def _format_receipt_failure(
    locale: str | None,
    error: str | None = None,
    max_image_mb: int | None = None,
) -> str:
    lines = [tr(locale, "receipt_amount_not_found")]
    if error:
        lines[0] = _receipt_error_message(error, locale, max_image_mb)
    lines.extend(["", tr(locale, "receipt_manual_hint")])
    return "\n".join(lines)


def _format_receipt_recognized(parsed: ParsedReceipt, locale: str | None) -> str:
    return "\n".join(
        [
            tr(locale, "receipt_recognized_confirm"),
            "",
            f"{tr(locale, 'amount')}: {parsed.amount}",
            f"{tr(locale, 'currency')}: {_receipt_value(parsed.currency, locale)}",
            f"{tr(locale, 'date')}: {_receipt_value(parsed.spent_at, locale)}",
            f"{tr(locale, 'description')}: {_receipt_value(parsed.merchant, locale)}",
        ]
    )


def _receipt_error_message(
    error: str, locale: str | None, max_image_mb: int | None = None
) -> str:
    normalized = error.casefold()
    if error == "image_too_large" or "too large" in normalized:
        return tr(locale, "receipt_image_too_large", max_image_mb=max_image_mb or "?")
    if "disabled" in normalized or "tesseract" in normalized:
        return tr(locale, "receipt_ocr_unavailable")
    if "did not recognize" in normalized:
        return tr(locale, "receipt_empty_text")
    return tr(locale, "receipt_ocr_failed")


def _receipt_value(value, locale: str | None) -> str:
    return str(value) if value else tr(locale, "receipt_not_detected")


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
                KeyboardButton(text=tr(locale, "menu_commands")),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def _receipt_draft_id(callback_data: str | None) -> uuid.UUID | None:
    try:
        _, draft_id = (callback_data or "").split(":", maxsplit=1)
        return uuid.UUID(draft_id)
    except (TypeError, ValueError):
        return None


async def _edit_callback_message(callback: CallbackQuery, text: str) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


def _is_public_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname not in {"localhost", "127.0.0.1", "::1"}


def _is_admin(message: Message) -> bool:
    user_id = message.from_user.id if message.from_user else None
    return bool(user_id and user_id in get_settings().admin_id_set)
