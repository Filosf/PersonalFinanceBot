from uuid import uuid4

from app.bot.keyboards import receipt_draft_actions


def test_receipt_draft_keyboard_callback_data() -> None:
    draft_id = str(uuid4())

    keyboard = receipt_draft_actions(draft_id, "en")
    rows = keyboard.inline_keyboard

    assert rows[0][0].callback_data == f"receipt_confirm:{draft_id}"
    assert rows[1][0].callback_data == f"receipt_manual:{draft_id}"
    assert rows[1][1].callback_data == f"receipt_cancel:{draft_id}"
