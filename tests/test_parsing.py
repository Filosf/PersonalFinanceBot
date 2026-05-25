from decimal import Decimal

import pytest

from app.services.parsing import parse_expense_text


def test_parse_amount_and_description() -> None:
    amount, description, kind = parse_expense_text("45.7 coffee")

    assert amount == Decimal("45.70")
    assert description == "coffee"
    assert kind == "expense"


def test_parse_amount_without_description() -> None:
    amount, description, kind = parse_expense_text("70")

    assert amount == Decimal("70.00")
    assert description == ""
    assert kind == "expense"


def test_parse_income() -> None:
    amount, description, kind = parse_expense_text("+15000 salary")

    assert amount == Decimal("15000.00")
    assert description == "salary"
    assert kind == "income"


def test_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError):
        parse_expense_text("0 taxi")
