import pytest

from app.services.categories import (
    _validate_category_name,
    is_default_category,
    is_protected_category,
)


def test_default_category_detection() -> None:
    assert is_default_category("Food")
    assert is_default_category("Income")
    assert not is_default_category("Groceries")


def test_only_general_and_income_are_protected() -> None:
    assert is_protected_category("General")
    assert is_protected_category("Income")
    assert not is_protected_category("Food")


def test_category_name_validation_normalizes_whitespace() -> None:
    assert _validate_category_name("  Home   stuff  ") == "Home stuff"


def test_category_name_validation_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _validate_category_name("   ")
