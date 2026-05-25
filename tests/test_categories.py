from app.services.categories import is_default_category


def test_default_category_detection() -> None:
    assert is_default_category("Food")
    assert is_default_category("Income")
    assert not is_default_category("Groceries")
