from datetime import date
from decimal import Decimal

import pytest

from app.db.models import RecurringPayment
from app.services.recurring_payments import (
    AMOUNT_SOURCE_PAYMENT,
    AMOUNT_SOURCE_TOTAL,
    calculate_recurring_amounts,
    remaining_months,
)


def test_total_amount_requires_payment_count() -> None:
    with pytest.raises(ValueError, match="Payment count is required"):
        calculate_recurring_amounts(Decimal("1200"), None, None)


def test_cannot_enter_total_amount_and_monthly_payment() -> None:
    with pytest.raises(ValueError, match="either total amount or monthly payment"):
        calculate_recurring_amounts(Decimal("1200"), Decimal("100"), 12)


def test_total_amount_and_count_compute_monthly_payment() -> None:
    amounts = calculate_recurring_amounts(Decimal("1200"), None, 12)

    assert amounts.amount_source == AMOUNT_SOURCE_TOTAL
    assert amounts.total_amount == Decimal("1200.00")
    assert amounts.payment_amount == Decimal("100.00")
    assert amounts.payment_count == 12


def test_payment_and_count_compute_total_amount() -> None:
    amounts = calculate_recurring_amounts(None, Decimal("100"), 12)

    assert amounts.amount_source == AMOUNT_SOURCE_PAYMENT
    assert amounts.total_amount == Decimal("1200.00")
    assert amounts.payment_amount == Decimal("100.00")
    assert amounts.payment_count == 12


def test_payment_without_count_is_infinite() -> None:
    amounts = calculate_recurring_amounts(None, Decimal("49.90"), None)

    assert amounts.amount_source == AMOUNT_SOURCE_PAYMENT
    assert amounts.total_amount is None
    assert amounts.payment_amount == Decimal("49.90")
    assert amounts.payment_count is None


def test_remaining_months_for_finite_payment_includes_current_month() -> None:
    payment = RecurringPayment(
        start_month=date(2026, 1, 1),
        payment_count=12,
    )

    assert remaining_months(payment, date(2026, 1, 1)) == 12
    assert remaining_months(payment, date(2026, 6, 1)) == 7
    assert remaining_months(payment, date(2027, 1, 1)) == 0


def test_remaining_months_for_infinite_payment() -> None:
    payment = RecurringPayment(
        start_month=date(2026, 1, 1),
        payment_count=None,
    )

    assert remaining_months(payment, date(2026, 6, 1)) is None
