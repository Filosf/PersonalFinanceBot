from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.i18n import category_label, tr
from app.db.models import Category, Expense


def expense_actions(
    expense: Expense, categories: list[Category], locale: str | None = None
) -> InlineKeyboardMarkup:
    category_buttons = [
        InlineKeyboardButton(
            text=category_label(category.name, locale),
            callback_data=f"cat:{expense.id}:{category.id}",
        )
        for category in categories[:6]
    ]
    rows = [category_buttons[i : i + 3] for i in range(0, len(category_buttons), 3)]
    rows.append(
        [
            InlineKeyboardButton(text=tr(locale, "delete"), callback_data=f"del:{expense.id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
