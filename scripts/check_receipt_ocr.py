from app.core.config import get_settings
from app.services.receipt_ocr import check_tesseract_available


def main() -> None:
    settings = get_settings()
    print(f"OCR_ENABLED={str(settings.ocr_enabled).lower()}")
    print(f"OCR_LANGUAGES={settings.ocr_languages}")
    print(f"OCR_MIN_CONFIDENCE={settings.ocr_min_confidence}")
    print(f"OCR_MAX_IMAGE_MB={settings.ocr_max_image_mb}")
    print(f"TESSERACT_CMD={settings.tesseract_cmd or ''}")
    print(f"TESSERACT_AVAILABLE={str(check_tesseract_available(settings)).lower()}")


if __name__ == "__main__":
    main()
