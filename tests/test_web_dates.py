from datetime import UTC, datetime

from app.web.routes import _parse_date


def test_parse_date_uses_user_timezone() -> None:
    parsed = _parse_date("2026-05-26T12:00", "Asia/Jerusalem")

    assert parsed == datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
