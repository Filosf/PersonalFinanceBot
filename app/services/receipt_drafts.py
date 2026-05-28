import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReceiptDraft

PENDING = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"


class ReceiptDraftService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_draft(
        self,
        telegram_user_id: int,
        amount: Decimal,
        currency: str | None = None,
        spent_at: date | None = None,
        merchant: str | None = None,
        raw_text: str | None = None,
        confidence: float = 0.0,
    ) -> ReceiptDraft:
        draft = ReceiptDraft(
            telegram_user_id=telegram_user_id,
            amount=_validate_amount(amount),
            currency=_validate_currency(currency),
            spent_at=spent_at,
            merchant=_validate_optional_text(merchant, 255),
            raw_text=raw_text,
            confidence=_clamp_confidence(confidence),
            status=PENDING,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def get_pending_draft(
        self, draft_id: uuid.UUID, telegram_user_id: int
    ) -> ReceiptDraft | None:
        draft = await self._get_owned_draft(draft_id, telegram_user_id)
        if draft is None or draft.status != PENDING:
            return None
        return draft

    async def confirm_draft(
        self, draft_id: uuid.UUID, telegram_user_id: int
    ) -> ReceiptDraft | None:
        draft = await self._get_owned_draft(draft_id, telegram_user_id)
        if draft is None:
            return None
        if draft.status == PENDING:
            draft.status = CONFIRMED
            draft.confirmed_at = datetime.now(UTC)
            await self.session.flush()
        return draft

    async def cancel_draft(
        self, draft_id: uuid.UUID, telegram_user_id: int
    ) -> ReceiptDraft | None:
        draft = await self._get_owned_draft(draft_id, telegram_user_id)
        if draft is None:
            return None
        if draft.status == PENDING:
            draft.status = CANCELLED
            draft.cancelled_at = datetime.now(UTC)
            await self.session.flush()
        return draft

    async def _get_owned_draft(
        self, draft_id: uuid.UUID, telegram_user_id: int
    ) -> ReceiptDraft | None:
        result = await self.session.execute(
            select(ReceiptDraft).where(
                ReceiptDraft.id == draft_id,
                ReceiptDraft.telegram_user_id == telegram_user_id,
            )
        )
        return result.scalar_one_or_none()


def _validate_amount(amount: Decimal) -> Decimal:
    value = Decimal(amount).quantize(Decimal("0.01"))
    if value <= 0:
        raise ValueError("Amount must be greater than zero")
    return value


def _validate_currency(currency: str | None) -> str | None:
    if currency is None:
        return None
    value = currency.strip().upper()
    if not value:
        return None
    if len(value) > 8:
        raise ValueError("Currency is too long")
    return value


def _validate_optional_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise ValueError("Text is too long")
    return cleaned


def _clamp_confidence(confidence: float) -> float:
    return min(max(float(confidence), 0.0), 1.0)
