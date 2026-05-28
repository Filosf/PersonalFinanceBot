from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.core.config import Settings
from app.services.receipt_ocr import extract_receipt_from_image


def _png_bytes() -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (8, 8), color="white")
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _ocr_settings(**overrides: object) -> Settings:
    values = {
        "ocr_enabled": True,
        "ocr_max_image_mb": 10,
        "ocr_languages": "eng+heb",
        "ocr_min_confidence": 0.65,
    }
    values.update(overrides)
    return Settings(**values)


def test_extract_receipt_returns_error_when_ocr_disabled() -> None:
    result = extract_receipt_from_image(_png_bytes(), Settings(ocr_enabled=False))

    assert result.success is False
    assert result.parsed is None
    assert result.raw_text == ""
    assert result.error is not None
    assert "disabled" in result.error


def test_extract_receipt_returns_error_when_tesseract_missing() -> None:
    with patch("app.services.receipt_ocr.check_tesseract_available", return_value=False):
        result = extract_receipt_from_image(_png_bytes(), _ocr_settings())

    assert result.success is False
    assert result.parsed is None
    assert result.error is not None
    assert "Tesseract" in result.error


def test_extract_receipt_rejects_oversized_image_before_ocr() -> None:
    settings = _ocr_settings(ocr_max_image_mb=1)
    oversized = b"x" * (1024 * 1024 + 1)

    with patch("app.services.receipt_ocr.check_tesseract_available") as available:
        result = extract_receipt_from_image(oversized, settings)

    assert result.success is False
    assert result.parsed is None
    assert result.error is not None
    assert "too large" in result.error
    available.assert_not_called()


def test_extract_receipt_handles_empty_ocr_text_gracefully() -> None:
    with (
        patch("app.services.receipt_ocr.check_tesseract_available", return_value=True),
        patch("pytesseract.image_to_string", return_value="   "),
    ):
        result = extract_receipt_from_image(_png_bytes(), _ocr_settings())

    assert result.success is False
    assert result.parsed is None
    assert result.raw_text == ""
    assert result.error is not None
    assert "did not recognize" in result.error


def test_extract_receipt_successful_ocr_path_uses_parser() -> None:
    raw_text = "Fresh Market\nTOTAL 123.45 ILS\n12/05/2026"

    with (
        patch("app.services.receipt_ocr.check_tesseract_available", return_value=True),
        patch("pytesseract.image_to_string", return_value=raw_text) as image_to_string,
    ):
        result = extract_receipt_from_image(_png_bytes(), _ocr_settings())

    assert result.success is True
    assert result.raw_text == raw_text
    assert result.parsed is not None
    assert result.parsed.amount is not None
    assert str(result.parsed.amount) == "123.45"
    assert result.parsed.currency == "ILS"
    image_to_string.assert_called_once()
    assert image_to_string.call_args.kwargs["lang"] == "eng+heb"


def test_extract_receipt_parser_integration_can_return_not_success_when_amount_missing() -> None:
    raw_text = "Fresh Market\n12/05/2026"

    with (
        patch("app.services.receipt_ocr.check_tesseract_available", return_value=True),
        patch("pytesseract.image_to_string", return_value=raw_text),
    ):
        result = extract_receipt_from_image(_png_bytes(), _ocr_settings())

    assert result.success is False
    assert result.error is None
    assert result.parsed is not None
    assert result.parsed.amount is None
    assert "amount not found" in result.parsed.warnings


def test_extract_receipt_handles_invalid_image_bytes_without_exception() -> None:
    with patch("app.services.receipt_ocr.check_tesseract_available", return_value=True):
        result = extract_receipt_from_image(b"not an image", _ocr_settings())

    assert result.success is False
    assert result.parsed is None
    assert result.error is not None
    assert "Could not read" in result.error


def test_extract_receipt_does_not_leave_temporary_files(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    with (
        patch("app.services.receipt_ocr.check_tesseract_available", return_value=True),
        patch("pytesseract.image_to_string", return_value="TOTAL 123.45"),
        patch("tempfile.NamedTemporaryFile", side_effect=AssertionError("temp file used")),
    ):
        result = extract_receipt_from_image(_png_bytes(), _ocr_settings())

    assert result.success is True
    assert set(tmp_path.iterdir()) == before
