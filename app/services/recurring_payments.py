import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import RecurringPayment
from app.services.categories import CategoryService

AMOUNT_SOURCE_TOTAL = "total"
AMOUNT_SOURCE_PAYMENT = "payment"
SCOPE_CURRENT = "current"
SCOPE_NEXT = "next"
SCOPE_ALL = "all"
START_CURRENT = "current"
START_NEXT = "next"
MONTHLY_SCOPE_VALUES = {SCOPE_CURRENT, SCOPE_NEXT}
SCOPE_VALUES = {SCOPE_CURRENT, SCOPE_NEXT, SCOPE_ALL}


@dataclass(slots=True)
class RecurringPaymentAmounts:
    amount_source: str
    total_amount: Decimal | None
    payment_amount: Decimal
    payment_count: int | None


def calculate_recurring_amounts(
    total_amount: Decimal | str | None,
    payment_amount: Decimal | str | None,
    payment_count: int | str | None,
) -> RecurringPaymentAmounts:
    total = _positive_decimal_or_none(total_amount)
    payment = _positive_decimal_or_none(payment_amount)
    count = _positive_int_or_none(payment_count)

    if total is not None and payment is not None:
        raise ValueError("Enter either total amount or monthly payment, not both")
    if total is None and payment is None:
        raise ValueError("Amount or monthly payment is required")
    if total is not None and count is None:
        raise ValueError("Payment count is required when total amount is entered")

    if total is not None:
        return RecurringPaymentAmounts(
            amount_source=AMOUNT_SOURCE_TOTAL,
            total_amount=total,
            payment_amount=_money(total / Decimal(count)),
            payment_count=count,
        )

    if count is not None:
        total = _money(payment * Decimal(count))
    return RecurringPaymentAmounts(
        amount_source=AMOUNT_SOURCE_PAYMENT,
        total_amount=total,
        payment_amount=payment,
        payment_count=count,
    )


def remaining_months(payment: RecurringPayment, month_start: date | None = None) -> int | None:
    if payment.payment_count is None:
        return None
    month = _month_start(month_start)
    elapsed_before_month = max(_months_between(payment.start_month, month), 0)
    remaining = max(payment.payment_count - elapsed_before_month, 0)
    if payment.end_month:
        remaining = min(remaining, max(_months_between(month, payment.end_month), 0))
    return remaining


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


class RecurringPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        *,
        category_id: int,
        total_amount: Decimal | str | None,
        payment_amount: Decimal | str | None,
        payment_count: int | str | None,
        charge_day: int | str | None,
        description: str,
        start_timing: str = START_CURRENT,
        today: date | None = None,
    ) -> RecurringPayment:
        await self._require_expense_category(user_id, category_id)
        amounts = calculate_recurring_amounts(total_amount, payment_amount, payment_count)
        payment = RecurringPayment(
            series_id=uuid.uuid4(),
            user_id=user_id,
            category_id=category_id,
            amount_source=amounts.amount_source,
            total_amount=amounts.total_amount,
            payment_amount=amounts.payment_amount,
            payment_count=amounts.payment_count,
            charge_day=_charge_day(charge_day),
            description=_description(description),
            start_month=_start_month(start_timing, today),
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def list_active(
        self, user_id: int, month_start: date | None = None
    ) -> list[RecurringPayment]:
        month = _month_start(month_start)
        result = await self.session.execute(
            select(RecurringPayment)
            .options(selectinload(RecurringPayment.category))
            .where(
                RecurringPayment.user_id == user_id,
                RecurringPayment.deleted_at.is_(None),
                RecurringPayment.start_month <= month,
                (RecurringPayment.end_month.is_(None) | (RecurringPayment.end_month > month)),
            )
            .order_by(RecurringPayment.charge_day, RecurringPayment.description)
        )
        return [
            payment
            for payment in result.scalars()
            if _is_within_payment_count(payment, month)
        ]

    async def update(
        self,
        user_id: int,
        series_id: uuid.UUID,
        *,
        scope: str,
        category_id: int,
        total_amount: Decimal | str | None,
        payment_amount: Decimal | str | None,
        payment_count: int | str | None,
        charge_day: int | str | None,
        description: str,
        today: date | None = None,
    ) -> RecurringPayment:
        scope = _scope(scope)
        await self._require_expense_category(user_id, category_id)
        amounts = calculate_recurring_amounts(total_amount, payment_amount, payment_count)
        if scope == SCOPE_ALL:
            versions = await self._series_versions(user_id, series_id)
            if not versions:
                raise PermissionError("Recurring payment not found")
            for payment in versions:
                self._apply_values(payment, category_id, amounts, charge_day, description)
            await self.session.flush()
            return versions[-1]

        month = _scope_month(scope, today)
        current = await self.get_active_version(user_id, series_id, month)
        if not current:
            raise PermissionError("Recurring payment not found")
        if month <= current.start_month:
            self._apply_values(current, category_id, amounts, charge_day, description)
            await self.session.flush()
            return current

        current.end_month = month
        replacement = RecurringPayment(
            series_id=current.series_id,
            user_id=user_id,
            category_id=category_id,
            amount_source=amounts.amount_source,
            total_amount=amounts.total_amount,
            payment_amount=amounts.payment_amount,
            payment_count=amounts.payment_count,
            charge_day=_charge_day(charge_day),
            description=_description(description),
            start_month=month,
        )
        self.session.add(replacement)
        await self.session.flush()
        return replacement

    async def delete(
        self,
        user_id: int,
        series_id: uuid.UUID,
        *,
        scope: str,
        today: date | None = None,
    ) -> None:
        scope = _scope(scope)
        now = datetime.now(UTC)
        if scope == SCOPE_ALL:
            versions = await self._series_versions(user_id, series_id)
            if not versions:
                raise PermissionError("Recurring payment not found")
            for payment in versions:
                payment.deleted_at = now
            await self.session.flush()
            return

        month = _scope_month(scope, today)
        current = await self.get_active_version(user_id, series_id, month)
        if not current:
            raise PermissionError("Recurring payment not found")
        if month <= current.start_month:
            current.deleted_at = now
        else:
            current.end_month = month
        await self.session.flush()

    async def get_active_version(
        self, user_id: int, series_id: uuid.UUID, month_start: date | None = None
    ) -> RecurringPayment | None:
        month = _month_start(month_start)
        result = await self.session.execute(
            select(RecurringPayment)
            .options(selectinload(RecurringPayment.category))
            .where(
                RecurringPayment.user_id == user_id,
                RecurringPayment.series_id == series_id,
                RecurringPayment.deleted_at.is_(None),
                RecurringPayment.start_month <= month,
                (RecurringPayment.end_month.is_(None) | (RecurringPayment.end_month > month)),
            )
            .order_by(RecurringPayment.start_month.desc())
        )
        payment = result.scalars().first()
        if payment and not _is_within_payment_count(payment, month):
            return None
        return payment

    async def _series_versions(
        self, user_id: int, series_id: uuid.UUID
    ) -> list[RecurringPayment]:
        result = await self.session.execute(
            select(RecurringPayment)
            .options(selectinload(RecurringPayment.category))
            .where(
                RecurringPayment.user_id == user_id,
                RecurringPayment.series_id == series_id,
                RecurringPayment.deleted_at.is_(None),
            )
            .order_by(RecurringPayment.start_month)
        )
        return list(result.scalars())

    async def _require_expense_category(self, user_id: int, category_id: int) -> None:
        category = await CategoryService(self.session).require_owned(user_id, category_id)
        if category.name == "Income":
            raise ValueError("Recurring payments cannot use Income category")

    def _apply_values(
        self,
        payment: RecurringPayment,
        category_id: int,
        amounts: RecurringPaymentAmounts,
        charge_day: int | str | None,
        description: str,
    ) -> None:
        payment.category_id = category_id
        payment.amount_source = amounts.amount_source
        payment.total_amount = amounts.total_amount
        payment.payment_amount = amounts.payment_amount
        payment.payment_count = amounts.payment_count
        payment.charge_day = _charge_day(charge_day)
        payment.description = _description(description)


def _month_start(value: date | None = None) -> date:
    today = value or datetime.now(UTC).date()
    return today.replace(day=1)


def _start_month(start_timing: str, today: date | None = None) -> date:
    current = _month_start(today)
    return next_month(current) if start_timing == START_NEXT else current


def _scope_month(scope: str, today: date | None = None) -> date:
    current = _month_start(today)
    return next_month(current) if scope == SCOPE_NEXT else current


def _scope(value: str) -> str:
    if value not in SCOPE_VALUES:
        raise ValueError("Invalid scope")
    return value


def _charge_day(value: int | str | None) -> int:
    if value in (None, ""):
        return 1
    try:
        day = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid charge day") from exc
    if day < 1 or day > 31:
        raise ValueError("Charge day must be between 1 and 31")
    return day


def _description(value: str) -> str:
    description = " ".join((value or "").strip().split())
    if len(description) > 500:
        raise ValueError("Description is too long")
    return description


def _positive_decimal_or_none(value: Decimal | str | None) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Amount must be a valid number") from exc
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")
    return _money(amount)


def _positive_int_or_none(value: int | str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Payment count must be a valid number") from exc
    if count <= 0:
        raise ValueError("Payment count must be greater than zero")
    return count


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month


def _is_within_payment_count(payment: RecurringPayment, month_start: date) -> bool:
    if payment.payment_count is None:
        return True
    return _months_between(payment.start_month, month_start) < payment.payment_count
