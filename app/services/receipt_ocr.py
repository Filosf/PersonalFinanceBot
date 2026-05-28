from app.core.config import Settings


def check_tesseract_available(settings: Settings) -> bool:
    """Return whether the Tesseract binary is reachable without running OCR."""
    try:
        import pytesseract
    except ImportError:
        return False

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        pytesseract.get_tesseract_version()
    except (OSError, RuntimeError, pytesseract.TesseractNotFoundError):
        return False
    return True
