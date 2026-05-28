# Receipt OCR production deployment

Receipt OCR is implemented as a free local OCR feature:

- `pytesseract` is only a Python wrapper.
- The real OCR engine is the Tesseract system binary.
- No OpenAI Vision, Google Vision, AWS Textract, Azure OCR, or other paid OCR API is used.
- Receipt photos are processed in memory and are not saved to disk.
- OCR text can be stored in `receipt_drafts.raw_text` until the user confirms/cancels the draft.

## Production Docker image

The production `Dockerfile` uses a slim Python image and installs Tesseract via apt:

```text
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-heb
```

Do not commit Tesseract binaries or `.traineddata` files manually. The Docker build
installs them from Debian packages.

The image should support:

```bash
tesseract --version
tesseract --list-langs
```

Expected languages include:

```text
eng
heb
```

## Render Docker setup

Important Render note: according to Render's Blueprint spec, a service `runtime`
is not safely changed in-place after service creation. The current production service
uses native Python runtime. To move to Docker, use a replacement Docker web service or
follow the current Render Dashboard option if it explicitly supports changing runtime
for your service.

Recommended safe path:

1. Keep the current production service running.
2. Create a new Render Web Service from the same GitHub repo.
3. Set Language / Runtime to `Docker`.
4. Set branch to `main`.
5. Keep auto-deploy enabled for commits to `main`.
6. Use the root `Dockerfile`.
7. Copy the existing production environment variables.
8. Use the same paid Postgres `DATABASE_URL`.
9. Deploy and verify logs.
10. Move the custom domain or bot webhook traffic only after the Docker service is healthy.

The existing `render.yaml` is intentionally left on native Python runtime to avoid
breaking the current service. If creating a new Docker Blueprint service, the service
shape should use:

```yaml
services:
  - type: web
    name: personal-finance-bot
    runtime: docker
    dockerfilePath: ./Dockerfile
    preDeployCommand: python -m alembic upgrade head
    envVars:
      - key: ENABLE_BOT_WEBHOOK
        value: "true"
```

Docker services use `CMD` from the Dockerfile unless `dockerCommand` is set.

## Production environment variables

Set or verify:

```env
BOT_TOKEN=your-production-bot-token
DATABASE_URL=your-render-postgres-internal-url
ENABLE_BOT_WEBHOOK=true
TELEGRAM_WEBHOOK_SECRET=strong-random-secret
APP_SECRET=strong-random-secret
ADMIN_IDS=comma-separated-admin-telegram-ids
DEFAULT_CURRENCY=ILS
DEFAULT_TIMEZONE=Asia/Jerusalem

OCR_ENABLED=true
OCR_LANGUAGES=eng+heb
TESSERACT_CMD=tesseract
OCR_MIN_CONFIDENCE=0.65
OCR_MAX_IMAGE_MB=5
```

Fast rollback switch:

```env
OCR_ENABLED=false
```

With OCR disabled, photo receipts fall back to manual input and no receipt expense is
created automatically.

## Migrations

Before starting the new Docker service, Render should run:

```bash
python -m alembic upgrade head
```

This applies the `receipt_drafts` table migration. Receipt drafts do not create expenses.
Expenses are created only after the user presses the receipt confirmation button.

## Local Windows testing

Install Tesseract for Windows and check:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

For local Windows `.env`:

```env
OCR_ENABLED=true
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_LANGUAGES=eng+heb
```

If your Windows installer only provides `script\Hebrew` and not `heb`, either install
`heb.traineddata` or temporarily use:

```env
OCR_LANGUAGES=eng+script/Hebrew
```

Production Docker should use `eng+heb`.

Run diagnostics:

```powershell
python -m scripts.check_receipt_ocr
```

## Troubleshooting

### `tesseract not found`

Check the production container:

```bash
tesseract --version
```

If it fails, confirm the service is actually using Docker and the Docker build installed
the apt packages.

### Hebrew language missing

Check:

```bash
tesseract --list-langs
```

If `heb` is missing, confirm `tesseract-ocr-heb` is installed during Docker build.

### OCR unavailable in bot

Check:

```env
OCR_ENABLED=true
TESSERACT_CMD=tesseract
OCR_LANGUAGES=eng+heb
```

Then redeploy/restart the service.

### Docker build failure

Check the apt install step in Render build logs. If a package name is unavailable in a
future base image, pin a compatible Debian/Python slim image and retry.

### Blurry receipts

The MVP does not use OpenCV preprocessing. Ask the user to send a clearer, well-lit image
or enter the expense manually.

### Low confidence receipts

If OCR text is available but the amount is not found confidently, the bot shows a short
preview and asks for manual input. No draft or expense is created.

### `OCR_ENABLED=false` fallback

This is expected when OCR is disabled. The bot should respond with a manual input hint.

## Final manual QA checklist

- Normal receipt creates a draft, not an expense.
- Partial receipt with only total amount creates a draft.
- Hebrew receipt recognizes an amount with `eng+heb`.
- Blurry receipt falls back to manual input.
- Oversized image is rejected.
- `OCR_ENABLED=false` fallback works.
- Missing Tesseract fallback works.
- Repeated `Save expense` click does not create a duplicate.
- `Cancel` flow does not create an expense.
- `Enter manually` flow does not create an expense.
- Invalid image does not crash the bot.
- Manual text input such as `250 taxi` still works.
