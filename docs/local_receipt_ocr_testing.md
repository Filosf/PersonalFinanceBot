# Local receipt OCR testing

This guide is for local testing of the free Tesseract-based receipt OCR bot flow.
It does not deploy anything to Render and does not change production settings.

## 1. Switch to the OCR branch

```powershell
git checkout feature/free-receipt-ocr
```

## 2. Update Python dependencies

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install or refresh dependencies:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

Fallback:

```powershell
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff
```

## 3. Install Tesseract OCR on Windows

Install Tesseract OCR for Windows, then check it:

```powershell
tesseract --version
```

If PowerShell cannot find `tesseract`, set `TESSERACT_CMD` in `.env` to the full
path, for example:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

For Hebrew OCR, make sure Hebrew language data is installed. The local OCR config
uses `eng+heb` by default.

## 4. Local `.env`

Use local polling, not Render webhook mode:

```env
ENABLE_BOT_WEBHOOK=false
RENDER_EXTERNAL_URL=
BOT_TOKEN=your-local-or-test-bot-token
DATABASE_URL=postgresql+asyncpg://finance:finance@localhost:5432/finance

OCR_ENABLED=true
OCR_LANGUAGES=eng+heb
OCR_MIN_CONFIDENCE=0.65
OCR_MAX_IMAGE_MB=10
TESSERACT_CMD=
```

`TESSERACT_CMD` is optional if `tesseract --version` works from the same terminal.

## 5. Check OCR diagnostics

This command does not start the bot and does not need a receipt image:

```powershell
python -m scripts.check_receipt_ocr
```

Expected successful output includes:

```text
OCR_ENABLED=true
OCR_LANGUAGES=eng+heb
TESSERACT_AVAILABLE=true
```

If `TESSERACT_AVAILABLE=false`, fix the Tesseract installation or `TESSERACT_CMD`.

## 6. Apply migrations

Make sure PostgreSQL is running, then run:

```powershell
python -m alembic upgrade head
```

This branch adds the `receipt_drafts` table. Drafts are temporary confirmation
records and do not create expenses by themselves.

## 7. Run local bot polling

Run the Telegram bot locally:

```powershell
python -m app.bot.main
```

Do not use webhook mode for this local check. Keep:

```env
ENABLE_BOT_WEBHOOK=false
```

The web dashboard can be started separately if needed:

```powershell
python -m uvicorn app.main:app --reload
```

## 8. Test receipt photo flow

1. Send `/start` to the bot.
2. Send a clear receipt photo.
3. The bot should show recognized amount, optional merchant/date/currency, and buttons:
   - Save expense
   - Enter manually
   - Cancel
4. Check that no expense is created before pressing `Save expense`.
5. Press `Save expense`.
6. Use `/last` to confirm the expense was created.
7. Press `Save expense` again on the same draft message if Telegram lets you. It should
   not create a duplicate expense.

## 9. Test fallback/manual input

1. Send a non-receipt image or a blurry/partial receipt where no amount is visible.
2. The bot should say it could not confidently find the amount.
3. If OCR returned text, the bot may show a short preview, capped at 300 characters.
4. Enter the expense manually in the existing format:

```text
250 taxi
120 food
70
```

Manual input must continue to work exactly as before.
