from unittest.mock import patch

from app.core.config import Settings
from app.services.receipt_ocr import check_tesseract_available


def test_ocr_is_disabled_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.ocr_enabled is False
    assert settings.ocr_languages == "eng+heb"
    assert settings.ocr_min_confidence == 0.65
    assert settings.ocr_max_image_mb == 10


def test_check_tesseract_available_returns_false_when_binary_missing() -> None:
    settings = Settings(_env_file=None, tesseract_cmd="missing-tesseract")

    with patch("pytesseract.get_tesseract_version", side_effect=RuntimeError("missing")):
        assert check_tesseract_available(settings) is False


def test_check_tesseract_available_returns_true_when_version_is_available() -> None:
    settings = Settings(_env_file=None)

    with patch("pytesseract.get_tesseract_version", return_value="5.3.0"):
        assert check_tesseract_available(settings) is True
