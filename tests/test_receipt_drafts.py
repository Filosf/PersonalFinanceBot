import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.db.models import ReceiptDraft
from app.services.receipt_drafts import (
    CANCELLED,
    CONFIRMED,
    PENDING,
    ReceiptDraftService,
)


class FakeSession:
    def __init__(self) -> None:
        self.drafts: dict[uuid.UUID, ReceiptDraft] = {}
        self.flush_count = 0

    def add(self, draft: ReceiptDraft) -> None:
        if draft.id is None:
            draft.id = uuid.uuid4()
        self.drafts[draft.id] = draft

    async def flush(self) -> None:
        self.flush_count += 1


class InMemoryReceiptDraftService(ReceiptDraftService):
    session: FakeSession

    async def _get_owned_draft(
        self, draft_id: uuid.UUID, telegram_user_id: int
    ) -> ReceiptDraft | None:
        draft = self.session.drafts.get(draft_id)
        if draft is None or draft.telegram_user_id != telegram_user_id:
            return None
        return draft


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def service(session: FakeSession) -> InMemoryReceiptDraftService:
    return InMemoryReceiptDraftService(session)  # type: ignore[arg-type]


async def _create_draft(
    service: InMemoryReceiptDraftService,
    telegram_user_id: int = 1001,
) -> ReceiptDraft:
    return await service.create_draft(
        telegram_user_id=telegram_user_id,
        amount=Decimal("123.45"),
        currency="ils",
        spent_at=date(2026, 5, 28),
        merchant="Fresh Market",
        raw_text="Fresh Market\nTOTAL 123.45 ILS",
        confidence=0.91,
    )


async def test_create_draft(service: InMemoryReceiptDraftService) -> None:
    draft = await _create_draft(service)

    assert draft.id is not None
    assert draft.telegram_user_id == 1001
    assert draft.amount == Decimal("123.45")
    assert draft.currency == "ILS"
    assert draft.spent_at == date(2026, 5, 28)
    assert draft.merchant == "Fresh Market"
    assert draft.raw_text == "Fresh Market\nTOTAL 123.45 ILS"
    assert draft.confidence == 0.91
    assert draft.status == PENDING


async def test_get_pending_draft_by_owner(service: InMemoryReceiptDraftService) -> None:
    draft = await _create_draft(service)

    found = await service.get_pending_draft(draft.id, 1001)

    assert found == draft


async def test_cannot_get_draft_for_another_telegram_user_id(
    service: InMemoryReceiptDraftService,
) -> None:
    draft = await _create_draft(service)

    found = await service.get_pending_draft(draft.id, 999)

    assert found is None


async def test_confirm_draft_changes_status(service: InMemoryReceiptDraftService) -> None:
    draft = await _create_draft(service)

    confirmed = await service.confirm_draft(draft.id, 1001)

    assert confirmed == draft
    assert draft.status == CONFIRMED
    assert draft.confirmed_at is not None
    assert draft.cancelled_at is None


async def test_cancel_draft_changes_status(service: InMemoryReceiptDraftService) -> None:
    draft = await _create_draft(service)

    cancelled = await service.cancel_draft(draft.id, 1001)

    assert cancelled == draft
    assert draft.status == CANCELLED
    assert draft.cancelled_at is not None
    assert draft.confirmed_at is None


async def test_repeated_confirm_is_safe(
    service: InMemoryReceiptDraftService,
    session: FakeSession,
) -> None:
    draft = await _create_draft(service)
    await service.confirm_draft(draft.id, 1001)
    confirmed_at = draft.confirmed_at
    flush_count = session.flush_count

    confirmed = await service.confirm_draft(draft.id, 1001)

    assert confirmed == draft
    assert draft.status == CONFIRMED
    assert draft.confirmed_at == confirmed_at
    assert session.flush_count == flush_count


async def test_repeated_cancel_is_safe(
    service: InMemoryReceiptDraftService,
    session: FakeSession,
) -> None:
    draft = await _create_draft(service)
    await service.cancel_draft(draft.id, 1001)
    cancelled_at = draft.cancelled_at
    flush_count = session.flush_count

    cancelled = await service.cancel_draft(draft.id, 1001)

    assert cancelled == draft
    assert draft.status == CANCELLED
    assert draft.cancelled_at == cancelled_at
    assert session.flush_count == flush_count


async def test_confirmed_draft_is_not_returned_as_pending(
    service: InMemoryReceiptDraftService,
) -> None:
    draft = await _create_draft(service)
    await service.confirm_draft(draft.id, 1001)

    found = await service.get_pending_draft(draft.id, 1001)

    assert found is None


async def test_cancelled_draft_is_not_returned_as_pending(
    service: InMemoryReceiptDraftService,
) -> None:
    draft = await _create_draft(service)
    await service.cancel_draft(draft.id, 1001)

    found = await service.get_pending_draft(draft.id, 1001)

    assert found is None
