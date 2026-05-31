from datetime import date
from decimal import Decimal

from app.bot.handlers import (
    _format_receipt_failure,
    _format_receipt_recognized,
)
from app.services.receipt_ocr import ParsedReceipt


def test_format_receipt_recognized_message_includes_detected_fields() -> None:
    parsed = ParsedReceipt(
        amount=Decimal("123.45"),
        currency="ILS",
        spent_at=date(2026, 5, 28),
        merchant="Fresh Market",
        confidence=0.91,
        raw_text="Fresh Market\nTOTAL 123.45 ILS",
        warnings=[],
    )

    text = _format_receipt_recognized(parsed, "en")

    assert "123.45" in text
    assert "ILS" in text
    assert "2026-05-28" in text
    assert "Fresh Market" in text
    assert "91%" not in text
    assert "Confidence" not in text


def test_format_receipt_recognized_message_marks_missing_fields() -> None:
    parsed = ParsedReceipt(
        amount=Decimal("123.45"),
        currency=None,
        spent_at=None,
        merchant=None,
        confidence=0.65,
        raw_text="TOTAL 123.45",
        warnings=[],
    )

    text = _format_receipt_recognized(parsed, "ru")

    assert "123.45" in text
    assert "не найдено" in text


def test_format_receipt_failure_includes_manual_hint_without_raw_preview() -> None:
    text = _format_receipt_failure("en")

    assert "could not confidently" in text
    assert "Please enter" in text
    assert "Recognized text preview" not in text


def test_format_receipt_failure_uses_unavailable_title_for_tesseract_errors() -> None:
    text = _format_receipt_failure("en", "Tesseract OCR is not available")

    assert "currently unavailable" in text
    assert "Tesseract OCR is not available" not in text


def test_format_receipt_failure_translates_oversized_image() -> None:
    text = _format_receipt_failure("ru", "image_too_large", max_image_mb=5)

    assert "Фото слишком большое" in text
    assert "5 МБ" in text
