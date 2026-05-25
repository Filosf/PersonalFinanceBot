from decimal import Decimal, InvalidOperation


def parse_expense_text(text: str) -> tuple[Decimal, str]:
    parts = text.strip().split(maxsplit=1)
    if not parts:
        raise ValueError("Send amount and optional description, for example: 250 taxi")

    raw_amount = parts[0].replace(",", ".")
    try:
        amount = Decimal(raw_amount).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("Could not recognize the amount") from exc

    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    return amount, parts[1].strip() if len(parts) > 1 else ""
