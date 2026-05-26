from app.services.categories import is_default_category, is_protected_category


def test_default_category_detection() -> None:
    assert is_default_category("Food")
    assert is_default_category("Income")
    assert not is_default_category("Groceries")


def test_only_general_and_income_are_protected() -> None:
    assert is_protected_category("General")
    assert is_protected_category("Income")
    assert not is_protected_category("Food")
