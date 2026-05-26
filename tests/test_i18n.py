from app.core.i18n import category_label, normalize_locale, tr


def test_normalize_locale_defaults_to_english() -> None:
    assert normalize_locale(None) == "en"
    assert normalize_locale("fr") == "en"


def test_commands_and_help_are_separate() -> None:
    assert tr("en", "menu_commands") == "Commands"
    assert "/commands" in tr("en", "commands")
    assert "How to use" in tr("en", "help")


def test_normalize_locale_detects_russian() -> None:
    assert normalize_locale("ru") == "ru"
    assert normalize_locale("ru-RU") == "ru"


def test_translates_known_key() -> None:
    assert tr("ru", "expenses") == "Расходы"
    assert tr("ru", "total_expense") == "Всего расходов"
    assert tr("ru", "total_income") == "Всего доходов"
    assert tr("ru", "balance") == "Прирост / убыток"
    assert tr("ru", "income_added") == "Доход добавлен"
    assert tr("ru", "usage_add_category") == "Использование: /add_category Продукты"
    assert "перейдите на сайт" in tr("ru", "budget_report_empty")


def test_translates_base_category_names() -> None:
    assert category_label("Food", "ru") == "Еда"
    assert category_label("Income", "ru") == "Доход"
    assert category_label("Custom", "ru") == "Custom"
