from datetime import UTC, datetime, timedelta
from datetime import timezone as fixed_timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.i18n import labels, normalize_locale
from app.db.models import User
from app.db.session import get_session
from app.services.access_tokens import (
    AccessTokenError,
    create_csrf_token,
    create_session_token,
    verify_access_token,
    verify_csrf_token,
    verify_session_token,
)
from app.services.budgets import BudgetService, month_bounds, month_start_from_iso
from app.services.categories import CategoryService, is_protected_category
from app.services.defaults import DEFAULT_CATEGORIES
from app.services.expenses import ExpenseFilters, ExpenseService
from app.services.users import UserService

router = APIRouter()


async def web_user(request: Request, session: AsyncSession = Depends(get_session)) -> User | None:
    session_token = request.cookies.get("session")
    if not session_token:
        return None
    try:
        telegram_id = verify_session_token(session_token)
    except AccessTokenError:
        return None
    return await UserService(session).get_by_telegram_id(int(telegram_id))


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    tab: str = "analytics",
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "t": labels("en"),
                "allow_developer_login": get_settings().allow_developer_login,
            },
        )

    categories = await CategoryService(session).list_categories(user.id)
    expense_counts = {
        category.id: await CategoryService(session).expense_count(user.id, category.id)
        for category in categories
    }
    expenses = await ExpenseService(session).list_expenses(user.id)
    analytics = await _analytics_context(user, session, period="month")
    budgets = await _budgets_context(user, session)
    csrf_token = _csrf_token(request)
    response = request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "editable_categories": _editable_categories(categories),
            "default_categories": DEFAULT_CATEGORIES,
            "expense_counts": expense_counts,
            "expenses": expenses,
            "analytics": analytics,
            "budgets": budgets,
            "active_tab": _normalize_tab(tab),
            "csrf_token": csrf_token,
        },
    )
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/login")
async def login(
    telegram_id: int = Form(),
    username: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not get_settings().allow_developer_login:
        raise HTTPException(status_code=404)
    await UserService(session).get_or_create_user(telegram_id=telegram_id, username=username)
    await session.commit()
    return _login_response(telegram_id)


@router.post("/login/key")
async def login_with_key(
    access_key: str = Form(),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    try:
        telegram_id = verify_access_token(access_key.strip())
    except AccessTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await UserService(session).get_or_create_user(telegram_id=telegram_id)
    await session.commit()
    return _login_response(telegram_id)


@router.get("/login/token")
async def login_with_token(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    try:
        telegram_id = verify_access_token(token.strip())
    except AccessTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await UserService(session).get_or_create_user(telegram_id=telegram_id)
    await session.commit()
    return _login_response(telegram_id)


@router.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(default=""),
) -> RedirectResponse:
    _require_csrf(request, csrf_token)
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("telegram_id")
    response.delete_cookie("session")
    response.delete_cookie("csrf_token")
    return response


@router.post("/language")
async def language(
    request: Request,
    locale: str = Form(),
    tab: str = Form(default="analytics"),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    await UserService(session).set_locale(user.id, normalize_locale(locale))
    await session.commit()
    return RedirectResponse(
        f"/?tab={_normalize_tab(tab)}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    period: str = "month",
    date_from: str | None = None,
    date_to: str | None = None,
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    context = await _analytics_context(user, session, period, date_from, date_to)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/analytics.html",
        {"request": request, "user": user, "t": labels(user.locale), "analytics": context},
    )


@router.get("/expenses/table", response_class=HTMLResponse)
async def expenses_table(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    text: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)

    filters = ExpenseFilters(
        date_from=_parse_date(date_from, user.timezone),
        date_to=_parse_date(date_to, user.timezone, end_of_day=True),
        category_id=category_id or None,
        min_amount=_parse_decimal(min_amount),
        max_amount=_parse_decimal(max_amount),
        text=text or None,
    )
    expenses = await ExpenseService(session).list_expenses(user.id, filters)
    categories = await CategoryService(session).list_categories(user.id)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/expenses_table.html",
        {
            "request": request,
            "t": labels(user.locale),
            "user": user,
            "expenses": expenses,
            "categories": categories,
            "csrf_token": _csrf_token(request),
        },
    )


@router.post("/expenses", response_class=HTMLResponse)
async def create_expense(
    request: Request,
    amount: Decimal = Form(),
    description: str = Form(default=""),
    category_id: int = Form(),
    spent_at: str = Form(default=""),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    category = await CategoryService(session).require_owned(user.id, category_id)
    try:
        await ExpenseService(session).add_expense(
            user.id,
            amount,
            description,
            category_name=category.name,
            spent_at=_parse_date(spent_at, user.timezone) or datetime.now(UTC),
            currency=user.currency,
            kind="income" if category.name == "Income" else "expense",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.post("/budgets", response_class=HTMLResponse)
async def save_budgets(
    request: Request,
    month: str = Form(),
    total_budget: str = Form(default=""),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)

    form = await request.form()
    try:
        month_start = month_start_from_iso(month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid month") from exc
    service = BudgetService(session)
    await service.set_month_budget(
        user.id, month_start, _parse_decimal(total_budget), category_id=None
    )
    categories = [
        category
        for category in await CategoryService(session).list_categories(user.id)
        if category.name != "Income"
    ]
    for category in categories:
        await service.set_month_budget(
            user.id,
            month_start,
            _parse_decimal(str(form.get(f"category_budget_{category.id}", ""))),
            category_id=category.id,
        )
    await session.commit()
    budgets = await _budgets_context(user, session, month_start.isoformat())
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/budgets_panel.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "budgets": budgets,
            "budget_message": labels(user.locale)["budgets_saved"],
            "csrf_token": _csrf_token(request),
        },
    )


@router.post("/expenses/{expense_id}", response_class=HTMLResponse)
async def update_expense(
    request: Request,
    expense_id: int,
    amount: Decimal = Form(),
    description: str = Form(default=""),
    category_id: int = Form(),
    spent_at: str = Form(),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    try:
        await ExpenseService(session).update_expense(
            user.id,
            expense_id,
            amount=amount,
            description=description,
            category_id=category_id,
            spent_at=_parse_date(spent_at, user.timezone),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.delete("/expenses/{expense_id}", response_class=HTMLResponse)
async def delete_expense(
    request: Request,
    expense_id: int,
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    await ExpenseService(session).delete_expense(user.id, expense_id)
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.post("/categories", response_class=HTMLResponse)
async def create_category(
    request: Request,
    name: str = Form(),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    try:
        await CategoryService(session).get_or_create(user.id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return await _categories_panel_response(
        request, user, session, labels(user.locale)["category_created"]
    )


@router.post("/categories/{category_id}", response_class=HTMLResponse)
async def rename_category(
    request: Request,
    category_id: int,
    name: str = Form(),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    try:
        await CategoryService(session).rename(user.id, category_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return await _categories_panel_response(
        request, user, session, labels(user.locale)["category_renamed"]
    )


@router.post("/categories/{category_id}/delete", response_class=HTMLResponse)
async def delete_category(
    request: Request,
    category_id: int,
    merge_category_id: int | None = Form(default=None),
    csrf_token: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    _require_csrf(request, csrf_token)
    try:
        await CategoryService(session).delete_or_merge(user.id, category_id, merge_category_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return await _categories_panel_response(
        request, user, session, labels(user.locale)["category_deleted_web"]
    )


async def _categories_panel_response(
    request: Request,
    user: User,
    session: AsyncSession,
    message: str | None = None,
) -> HTMLResponse:
    categories = await CategoryService(session).list_categories(user.id)
    expense_counts = {
        category.id: await CategoryService(session).expense_count(user.id, category.id)
        for category in categories
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/categories_panel.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "editable_categories": _editable_categories(categories),
            "default_categories": DEFAULT_CATEGORIES,
            "expense_counts": expense_counts,
            "category_message": message,
            "refresh_selects": True,
            "csrf_token": _csrf_token(request),
        },
    )


def _editable_categories(categories: list) -> list:
    return [category for category in categories if not is_protected_category(category.name)]


def _normalize_tab(tab: str | None) -> str:
    return tab if tab in {"analytics", "transactions", "budgets", "categories"} else "analytics"


def _parse_date(
    value: str | None, timezone: str | None = None, end_of_day: bool = False
) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date") from exc
    if end_of_day and "T" not in value:
        parsed = parsed + timedelta(days=1)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_timezone(timezone))
    return parsed.astimezone(UTC)


def _timezone(timezone: str | None):
    try:
        return ZoneInfo(timezone or "UTC")
    except ZoneInfoNotFoundError:
        if timezone == "Asia/Jerusalem":
            return fixed_timezone(timedelta(hours=3))
        return UTC


def _local_month_bounds(month_start, timezone: str) -> tuple[datetime, datetime]:
    start_at, end_at = month_bounds(month_start)
    tz = _timezone(timezone)
    return (
        start_at.replace(tzinfo=tz).astimezone(UTC),
        end_at.replace(tzinfo=tz).astimezone(UTC),
    )


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _csrf_token(request: Request) -> str:
    token = request.cookies.get("csrf_token")
    if token:
        try:
            verify_csrf_token(token)
            return token
        except AccessTokenError:
            pass
    return create_csrf_token()


def _require_csrf(request: Request, form_token: str) -> None:
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not form_token or cookie_token != form_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    try:
        verify_csrf_token(form_token)
    except AccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token"
        ) from exc


def _set_csrf_cookie(response: RedirectResponse | HTMLResponse, csrf_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
    )


def _login_response(telegram_id: int) -> RedirectResponse:
    settings = get_settings()
    csrf_token = create_csrf_token()
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        "session",
        create_session_token(telegram_id),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
    )
    _set_csrf_cookie(response, csrf_token)
    return response


async def _analytics_context(
    user: User,
    session: AsyncSession,
    period: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    start_at, end_at, granularity = _period_range(user.timezone, period, date_from, date_to)
    service = ExpenseService(session)
    summary = await service.summary(user.id, start_at, end_at)
    cashflow = await service.cashflow_summary(user.id, start_at, end_at)
    series = await service.cashflow_time_series(user.id, start_at, end_at, granularity)
    user_now = datetime.now(_timezone(user.timezone))
    month_start = user_now.date().replace(day=1)
    month_start_at, month_end_at = _local_month_bounds(month_start, user.timezone)
    month_summary = await service.summary(user.id, month_start_at, month_end_at)
    max_total = max(
        (
            max(Decimal(item["income"]), Decimal(item["expense"]))
            for item in series
        ),
        default=Decimal("0"),
    )
    return {
        "period": period,
        "date_from": start_at.date().isoformat(),
        "date_to": (end_at - timedelta(days=1)).date().isoformat(),
        "granularity": granularity,
        "summary": summary,
        "cashflow": cashflow,
        "month_summary": month_summary,
        "month_pie": _pie_segments(month_summary["categories"]),
        "category_summary": summary["categories"],
        "insights": _analytics_insights(series, summary, cashflow, start_at, end_at),
        "series": series,
        "max_total": max_total,
    }


def _period_range(
    timezone: str, period: str, date_from: str | None = None, date_to: str | None = None
) -> tuple[datetime, datetime, str]:
    tz = _timezone(timezone)
    today = datetime.now(tz).date()
    if period == "week":
        start = today - timedelta(days=6)
        end = today + timedelta(days=1)
        granularity = "day"
    elif period == "year":
        start = today.replace(month=1, day=1)
        end = today + timedelta(days=1)
        granularity = "month"
    elif period == "years":
        start = today.replace(year=today.year - 4, month=1, day=1)
        end = today + timedelta(days=1)
        granularity = "year"
    elif period == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from).date()
            end = datetime.fromisoformat(date_to).date() + timedelta(days=1)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date range") from exc
        days = (end - start).days
        granularity = "day" if days <= 62 else "month" if days <= 730 else "year"
    else:
        start = today.replace(day=1)
        end = today + timedelta(days=1)
        granularity = "day"
        period = "month"
    return (
        datetime.combine(start, datetime.min.time(), tzinfo=tz).astimezone(UTC),
        datetime.combine(end, datetime.min.time(), tzinfo=tz).astimezone(UTC),
        granularity,
    )


async def _budgets_context(
    user: User, session: AsyncSession, month: str | None = None
) -> dict:
    month_start = month_start_from_iso(month)
    categories = [
        category
        for category in await CategoryService(session).list_categories(user.id)
        if category.name != "Income"
    ]
    budget_rows = await BudgetService(session).report(user.id, month_start)
    by_category = {row.category_id: row for row in budget_rows}
    total = by_category.get(None)
    return {
        "month": month_start.isoformat(),
        "total": total,
        "category_rows": [
            {
                "category": category,
                "budget": by_category.get(category.id),
            }
            for category in categories
        ],
    }


def _pie_segments(categories: list[dict]) -> list[dict]:
    total = sum((Decimal(item["total"]) for item in categories), Decimal("0"))
    if total <= 0:
        return []
    gap = Decimal("0.32")
    half_gap = gap / Decimal("2")
    colors = (
        "#2563eb",
        "#dc2626",
        "#7c3aed",
        "#facc15",
        "#64748b",
        "#db2777",
        "#06b6d4",
        "#f97316",
        "#a855f7",
        "#94a3b8",
    )
    cursor = Decimal("0")
    segments = []
    last_index = len(categories) - 1
    for index, item in enumerate(categories):
        amount = Decimal(item["total"])
        percent = (amount / total) * Decimal("100")
        start = cursor
        cursor += percent
        gap_start = start + half_gap
        gap_end = cursor - half_gap
        if index == 0:
            gap_start = start
        if index == last_index:
            gap_end = cursor
        if gap_end <= gap_start:
            gap_start = start
            gap_end = cursor
        segments.append(
            {
                "category": item["category"],
                "total": amount,
                "percent": percent,
                "start": start,
                "end": cursor,
                "gap_start": gap_start,
                "gap_end": gap_end,
                "color": _category_chart_color(item["category"], index, colors),
            }
        )
    return segments


def _category_chart_color(category: str, index: int, fallback_colors: tuple[str, ...]) -> str:
    if category == "Income":
        return "#15803d"
    if category == "General":
        return "#b42318"
    return fallback_colors[index % len(fallback_colors)]


def _analytics_insights(
    series: list[dict],
    summary: dict,
    cashflow: dict,
    start_at: datetime,
    end_at: datetime,
) -> dict:
    days = max((end_at.date() - start_at.date()).days, 1)
    expense = Decimal(cashflow["expense"])
    top_period = max(series, key=lambda item: Decimal(item["expense"]), default=None)
    if top_period and Decimal(top_period["expense"]) <= 0:
        top_period = None
    categories = summary["categories"]
    top_category = max(categories, key=lambda item: Decimal(item["total"]), default=None)
    return {
        "average_daily_expense": expense / Decimal(days),
        "active_expense_days": sum(1 for item in series if Decimal(item["expense"]) > 0),
        "top_period": top_period,
        "top_category": top_category,
    }
