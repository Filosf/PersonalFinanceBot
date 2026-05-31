from datetime import date
from decimal import Decimal

from app.services.receipt_ocr import parse_receipt_text


def test_english_receipt_with_total_extracts_amount() -> None:
    parsed = parse_receipt_text(
        """
        Fresh Market
        Milk 10.90
        TOTAL 123.45
        12/05/2026
        """
    )

    assert parsed.amount == Decimal("123.45")
    assert parsed.merchant == "Fresh Market"
    assert parsed.confidence >= 0.9


def test_hebrew_receipt_with_total_extracts_amount() -> None:
    parsed = parse_receipt_text(
        """
        מכולת העיר
        לחם 8.90
        סה"כ 123.45 ₪
        12/05/2026
        """
    )

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency == "ILS"
    assert parsed.merchant == "מכולת העיר"


def test_amount_with_comma_decimal_separator() -> None:
    parsed = parse_receipt_text("Shop\nTotal 123,45\n12/05/2026")

    assert parsed.amount == Decimal("123.45")


def test_shekel_symbol_before_amount() -> None:
    parsed = parse_receipt_text("Shop\nTOTAL ₪123.45")

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency == "ILS"


def test_shekel_symbol_after_amount() -> None:
    parsed = parse_receipt_text("Shop\nTOTAL 123.45 ₪")

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency == "ILS"


def test_total_amount_fragment_without_date_or_merchant_is_usable() -> None:
    parsed = parse_receipt_text("TOTAL 123.45")

    assert parsed.amount == Decimal("123.45")
    assert parsed.merchant is None
    assert parsed.spent_at is None
    assert parsed.confidence >= 0.85
    assert "date not found" in parsed.warnings
    assert "merchant not found" in parsed.warnings
    assert "low confidence" not in parsed.warnings


def test_amount_with_shekel_only_is_usable() -> None:
    parsed = parse_receipt_text("₪123.45")

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency == "ILS"
    assert parsed.merchant is None
    assert parsed.spent_at is None
    assert parsed.confidence >= 0.65
    assert "low confidence" not in parsed.warnings


def test_missing_merchant_and_date_do_not_make_strong_amount_low_confidence() -> None:
    parsed = parse_receipt_text("123.45 NIS")

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency == "ILS"
    assert parsed.confidence >= 0.65
    assert "date not found" in parsed.warnings
    assert "merchant not found" in parsed.warnings
    assert "low confidence" not in parsed.warnings


def test_currency_is_ils_when_ils_or_nis_appears() -> None:
    assert parse_receipt_text("TOTAL 123.45 ILS").currency == "ILS"
    assert parse_receipt_text("TOTAL 123.45 NIS").currency == "ILS"


def test_missing_currency_does_not_make_amount_low_confidence() -> None:
    parsed = parse_receipt_text("TOTAL 123.45")

    assert parsed.amount == Decimal("123.45")
    assert parsed.currency is None
    assert parsed.confidence >= 0.85
    assert "currency not found" in parsed.warnings
    assert "low confidence" not in parsed.warnings


def test_vat_is_ignored_when_total_exists() -> None:
    parsed = parse_receipt_text(
        """
        Shop
        VAT 17.00
        TOTAL 123.45
        """
    )

    assert parsed.amount == Decimal("123.45")


def test_hebrew_vat_is_ignored_when_total_exists() -> None:
    parsed = parse_receipt_text(
        """
        חנות
        מע"מ 17.00
        סהכ 123.45
        """
    )

    assert parsed.amount == Decimal("123.45")


def test_date_extraction_full_year() -> None:
    parsed = parse_receipt_text("Shop\nTOTAL 123.45\n12/05/2026")

    assert parsed.spent_at == date(2026, 5, 12)


def test_date_extraction_two_digit_year() -> None:
    parsed = parse_receipt_text("Shop\nTOTAL 123.45\n12/05/26")

    assert parsed.spent_at == date(2026, 5, 12)


def test_future_receipt_date_is_ignored() -> None:
    parsed = parse_receipt_text("Shop\nTOTAL 38.00\n28/05/2028")

    assert parsed.amount == Decimal("38.00")
    assert parsed.spent_at is None
    assert "date not found" in parsed.warnings


def test_merchant_extraction_from_first_meaningful_line() -> None:
    parsed = parse_receipt_text("\n\n123456789\nBest Coffee TLV\nTOTAL 40.00")

    assert parsed.merchant == "Best Coffee TLV"


def test_missing_amount_returns_low_confidence_and_warning() -> None:
    parsed = parse_receipt_text("Shop\n12/05/2026")

    assert parsed.amount is None
    assert parsed.confidence <= 0.3
    assert "amount not found" in parsed.warnings
    assert "low confidence" in parsed.warnings


def test_empty_text_returns_low_confidence_and_warnings() -> None:
    parsed = parse_receipt_text("")

    assert parsed.amount is None
    assert parsed.spent_at is None
    assert parsed.merchant is None
    assert parsed.confidence <= 0.3
    assert "empty OCR text" in parsed.warnings
    assert "amount not found" in parsed.warnings
    assert "date not found" in parsed.warnings
    assert "merchant not found" in parsed.warnings
    assert "low confidence" in parsed.warnings
