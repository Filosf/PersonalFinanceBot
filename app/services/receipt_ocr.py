import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from app.core.config import Settings

TOTAL_KEYWORDS = ("total", 'סה"כ', "סהכ", "לתשלום", "סכום", "חיוב")
TAX_KEYWORDS = ("vat", 'מע"מ', "tax")
LOW_CONFIDENCE_THRESHOLD = 0.65

AMOUNT_RE = re.compile(
    r"(?:₪\s*)?(?P<amount>\d{1,6}(?:[.,]\d{2}))(?:\s*₪)?"
)
DATE_RE = re.compile(r"\b(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{2}|\d{4})\b")


@dataclass(slots=True)
class ParsedReceipt:
    amount: Decimal | None
    currency: str | None
    spent_at: date | None
    merchant: str | None
    confidence: float
    raw_text: str
    warnings: list[str]


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


def parse_receipt_text(raw_text: str) -> ParsedReceipt:
    text = raw_text.strip()
    warnings = []
    if not text:
        warnings.append("empty OCR text")

    lines = _meaningful_lines(raw_text)
    amount, currency, amount_near_total = _extract_amount(lines)
    spent_at = _extract_date(raw_text)
    merchant = _extract_merchant(lines)

    confidence = _confidence(amount, amount_near_total, spent_at, merchant)
    if amount is None:
        warnings.append("amount not found")
    if spent_at is None:
        warnings.append("date not found")
    if merchant is None:
        warnings.append("merchant not found")
    if currency is None:
        warnings.append("currency not found")
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append("low confidence")

    return ParsedReceipt(
        amount=amount,
        currency=currency,
        spent_at=spent_at,
        merchant=merchant,
        confidence=confidence,
        raw_text=raw_text,
        warnings=warnings,
    )


def _meaningful_lines(raw_text: str) -> list[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _extract_amount(lines: list[str]) -> tuple[Decimal | None, str | None, bool]:
    candidates = []
    has_total_line = any(_has_total_keyword(line) for line in lines)
    for line_index, line in enumerate(lines):
        for match_index, match in enumerate(AMOUNT_RE.finditer(line)):
            amount = _parse_decimal(match.group("amount"))
            if amount is None:
                continue
            score = amount
            near_total = _has_total_keyword(line)
            tax_line = _has_tax_keyword(line)
            if near_total:
                score += Decimal("1000000")
            if tax_line:
                score -= Decimal("1000000") if has_total_line else Decimal("10")
            currency = _line_currency(line)
            if currency:
                score += Decimal("1")
            # Later values on a receipt line are often the payable total.
            score += Decimal(match_index) / Decimal("100")
            score -= Decimal(line_index) / Decimal("10000")
            candidates.append((score, amount, currency, near_total))

    if not candidates:
        return None, None, False

    _, amount, currency, near_total = max(candidates, key=lambda item: item[0])
    return amount, currency, near_total


def _parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _extract_date(raw_text: str) -> date | None:
    for match in DATE_RE.finditer(raw_text):
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
        if year < 100:
            year += 2000 if year < 70 else 1900
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


def _extract_merchant(lines: list[str]) -> str | None:
    for line in lines:
        if _looks_like_non_merchant(line):
            continue
        return line[:120]
    return None


def _looks_like_non_merchant(line: str) -> bool:
    normalized = line.casefold()
    digit_count = sum(char.isdigit() for char in line)
    return (
        bool(DATE_RE.search(line))
        or bool(AMOUNT_RE.search(line))
        or _has_total_keyword(line)
        or _has_tax_keyword(line)
        or "tel" in normalized
        or "phone" in normalized
        or "tax id" in normalized
        or "invoice" in normalized
        or "עוסק" in line
        or "ח.פ" in line
        or "חפ" in line
        or digit_count >= 7
    )


def _has_total_keyword(line: str) -> bool:
    normalized = line.casefold()
    return any(keyword.casefold() in normalized for keyword in TOTAL_KEYWORDS)


def _has_tax_keyword(line: str) -> bool:
    normalized = line.casefold()
    return any(keyword.casefold() in normalized for keyword in TAX_KEYWORDS)


def _line_currency(line: str) -> str | None:
    normalized = line.casefold()
    if "₪" in line or "ils" in normalized or "nis" in normalized:
        return "ILS"
    return None


def _confidence(
    amount: Decimal | None,
    amount_near_total: bool,
    spent_at: date | None,
    merchant: str | None,
) -> float:
    if amount is None:
        score = 0.2
    elif amount_near_total:
        score = 0.85
    else:
        score = 0.65
    if spent_at is not None:
        score += 0.05
    if merchant:
        score += 0.05
    if amount is None:
        score = min(score, 0.3)
    return min(max(score, 0.0), 1.0)
