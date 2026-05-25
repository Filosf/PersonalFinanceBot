from datetime import date

from app.services.budgets import month_start_from_iso


def test_month_start_accepts_month_input() -> None:
    assert month_start_from_iso("2026-05") == date(2026, 5, 1)


def test_month_start_accepts_full_date() -> None:
    assert month_start_from_iso("2026-05-25") == date(2026, 5, 1)
