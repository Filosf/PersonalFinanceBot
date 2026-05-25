from app.core.i18n import category_label, normalize_locale, tr


def test_normalize_locale_defaults_to_english() -> None:
    assert normalize_locale(None) == "en"
    assert normalize_locale("fr") == "en"


def test_normalize_locale_detects_russian() -> None:
    assert normalize_locale("ru") == "ru"
    assert normalize_locale("ru-RU") == "ru"


def test_translates_known_key() -> None:
    assert tr("ru", "expenses") == "Расходы"


def test_translates_base_category_names() -> None:
    assert category_label("Food", "ru") == "Еда"
    assert category_label("Custom", "ru") == "Custom"
