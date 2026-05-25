# Telegram Bot + Web Dashboard for Personal Finance

MVP expense tracker:

- Telegram bot with aiogram 3: registration, expense creation, categories, `/month`, `/last`, `/delete_last`.
- FastAPI REST API with a shared service layer.
- Web dashboard with FastAPI + Jinja2 + HTMX: login, expense table, filters, editing, deletion.
- PostgreSQL, SQLAlchemy 2.x, Alembic.

## Current local requirements

- Python 3.13.
- PostgreSQL running locally or in Docker.
- Docker is optional. If `docker` is not recognized, install Docker Desktop or install PostgreSQL directly.

## Setup

Create `.env`:

```powershell
Copy-Item .env.example .env
```

If Docker Desktop is installed, start PostgreSQL:

```powershell
docker compose up -d postgres
```

If Docker is not installed, install PostgreSQL locally and update `DATABASE_URL` in `.env`, for example:

```env
DATABASE_URL=postgresql+asyncpg://finance:finance@localhost:5432/finance
```

Quick database check:

```powershell
Test-NetConnection localhost -Port 5432
python scripts/check_db.py
```

If `Test-NetConnection` says `TcpTestSucceeded: False`, PostgreSQL is not running on port 5432.

For local PostgreSQL on Windows, create the database and user with `psql`:

```sql
CREATE USER finance WITH PASSWORD 'finance';
CREATE DATABASE finance OWNER finance;
GRANT ALL PRIVILEGES ON DATABASE finance TO finance;
```

Create and activate virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Upgrade packaging tools. Your current pip 21.1.1 is too old for modern editable installs:

```powershell
python -m pip install --upgrade pip setuptools wheel
```

Install dependencies:

```powershell
pip install -e ".[dev]"
```

Fallback for old pip:

```powershell
pip install -r requirements.txt
pip install pytest pytest-asyncio ruff
```

Apply migrations:

```powershell
python -m alembic upgrade head
```

Run web/API:

```powershell
python -m uvicorn app.main:app --reload
```

Run Telegram bot in another terminal:

```powershell
python -m app.bot.main
```

Dashboard: http://localhost:8000

To sign in to the dashboard as a normal user:

1. Open the bot in Telegram.
2. Send `/web`.
3. Click the dashboard button or paste the access key on the login page.

For MVP, access keys are signed with `APP_SECRET` and expire after `ACCESS_TOKEN_TTL_MINUTES`.
In production, replace or complement this with Telegram Login Widget signature verification.

## Language and analytics

- The bot uses Russian automatically when Telegram sends `language_code=ru`; otherwise it uses English.
- Existing users can change bot language with `/language` or `/язык`.
- The dashboard has an EN/RU switch in the header.
- The dashboard shows quick analytics for 7 days, current month, current year, last 5 years, and a custom period.
- After pulling changes that add `users.locale`, run migrations again:

```powershell
python -m alembic upgrade head
```

## Demo data

Seed two months of demo expenses for `Filosf`, `Telegram ID 122078682`, `ILS`:

```powershell
python -m scripts.seed_filosf_two_months
```

The script creates 1-5 expenses per day and only replaces previous demo rows whose description starts with `[seed]`.

## Render deployment

Use one Render Web Service for both FastAPI dashboard and Telegram webhook.
Do not run `python -m app.bot.main` on Render; polling is for local development only.

Render setup:

1. Push this repository to GitHub.
2. Create a paid Render Postgres database.
3. Create a Render Web Service from the repository.
4. Use:

```text
Build Command: pip install -r requirements.txt
Pre-deploy Command: python -m alembic upgrade head
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```env
BOT_TOKEN=your-telegram-bot-token
DATABASE_URL=your-render-postgres-internal-url
ENABLE_BOT_WEBHOOK=true
TELEGRAM_WEBHOOK_SECRET=random-long-secret
APP_SECRET=random-long-secret
DEFAULT_CURRENCY=ILS
DEFAULT_TIMEZONE=Asia/Jerusalem
```

Render automatically provides `RENDER_EXTERNAL_URL`; the app uses it for Telegram webhook and dashboard login links.

After deploy, open:

```text
https://your-service.onrender.com/
https://your-service.onrender.com/docs
```

Then send `/web` to the Telegram bot.
