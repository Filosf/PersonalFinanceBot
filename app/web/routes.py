from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import labels, normalize_locale
from app.db.models import User
from app.db.session import get_session
from app.services.access_tokens import AccessTokenError, verify_access_token
from app.services.budgets import BudgetService, month_bounds, month_start_from_iso
from app.services.categories import CategoryService, is_default_category
from app.services.defaults import DEFAULT_CATEGORIES
from app.services.expenses import ExpenseFilters, ExpenseService
from app.services.users import UserService

router = APIRouter()


async def web_user(request: Request, session: AsyncSession = Depends(get_session)) -> User | None:
    telegram_id = request.cookies.get("telegram_id")
    if not telegram_id:
        return None
    return await UserService(session).get_by_telegram_id(int(telegram_id))


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        return request.app.state.templates.TemplateResponse(
            request, "login.html", {"request": request, "t": labels("en")}
        )

    categories = await CategoryService(session).list_categories(user.id)
    expenses = await ExpenseService(session).list_expenses(user.id)
    analytics = await _analytics_context(user, session, period="month")
    budgets = await _budgets_context(user, session)
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "custom_categories": _custom_categories(categories),
            "default_categories": DEFAULT_CATEGORIES,
            "expenses": expenses,
            "analytics": analytics,
            "budgets": budgets,
        },
    )


@router.post("/login")
async def login(
    telegram_id: int = Form(),
    username: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
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
async def logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("telegram_id")
    return response


@router.post("/language")
async def language(
    locale: str = Form(),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not user:
        raise HTTPException(status_code=401)
    await UserService(session).set_locale(user.id, normalize_locale(locale))
    await session.commit()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


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
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to, end_of_day=True),
        category_id=category_id or None,
        min_amount=_parse_decimal(min_amount),
        max_amount=_parse_decimal(max_amount),
        text=text or None,
    )
    expenses = await ExpenseService(session).list_expenses(user.id, filters)
    categories = [
        category
        for category in await CategoryService(session).list_categories(user.id)
        if category.name != "Income"
    ]
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/expenses_table.html",
        {
            "request": request,
            "t": labels(user.locale),
            "user": user,
            "expenses": expenses,
            "categories": categories,
        },
    )


@router.post("/expenses", response_class=HTMLResponse)
async def create_expense(
    request: Request,
    amount: Decimal = Form(),
    description: str = Form(default=""),
    category_id: int = Form(),
    spent_at: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    category = await CategoryService(session).require_owned(user.id, category_id)
    await ExpenseService(session).add_expense(
        user.id,
        amount,
        description,
        category_name=category.name,
        spent_at=_parse_date(spent_at) or datetime.now(UTC),
        currency=user.currency,
        kind="income" if category.name == "Income" else "expense",
    )
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.post("/budgets", response_class=HTMLResponse)
async def save_budgets(
    request: Request,
    month: str = Form(),
    total_budget: str = Form(default=""),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)

    form = await request.form()
    month_start = month_start_from_iso(month)
    service = BudgetService(session)
    await service.set_month_budget(
        user.id, month_start, _parse_decimal(total_budget), category_id=None
    )
    categories = await CategoryService(session).list_categories(user.id)
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
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    await ExpenseService(session).update_expense(
        user.id,
        expense_id,
        amount=amount,
        description=description,
        category_id=category_id,
        spent_at=_parse_date(spent_at),
    )
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.delete("/expenses/{expense_id}", response_class=HTMLResponse)
async def delete_expense(
    request: Request,
    expense_id: int,
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    await ExpenseService(session).delete_expense(user.id, expense_id)
    await session.commit()
    return await expenses_table(request, user=user, session=session)


@router.post("/categories", response_class=HTMLResponse)
async def create_category(
    request: Request,
    name: str = Form(),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
    await CategoryService(session).get_or_create(user.id, name)
    await session.commit()
    return await _categories_panel_response(
        request, user, session, labels(user.locale)["category_created"]
    )


@router.post("/categories/{category_id}", response_class=HTMLResponse)
async def rename_category(
    request: Request,
    category_id: int,
    name: str = Form(),
    user: User | None = Depends(web_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    if not user:
        raise HTTPException(status_code=401)
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


async def _categories_panel_response(
    request: Request,
    user: User,
    session: AsyncSession,
    message: str | None = None,
) -> HTMLResponse:
    categories = await CategoryService(session).list_categories(user.id)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/categories_panel.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "custom_categories": _custom_categories(categories),
            "default_categories": DEFAULT_CATEGORIES,
            "category_message": message,
            "refresh_selects": True,
        },
    )


def _custom_categories(categories: list) -> list:
    return [category for category in categories if not is_default_category(category.name)]


def _parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value).replace(tzinfo=UTC)
    if end_of_day and "T" not in value:
        return parsed + timedelta(days=1)
    return parsed


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _login_response(telegram_id: int) -> RedirectResponse:
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("telegram_id", str(telegram_id), httponly=True, samesite="lax")
    return response


async def _analytics_context(
    user: User,
    session: AsyncSession,
    period: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    start_at, end_at, granularity = _period_range(period, date_from, date_to)
    service = ExpenseService(session)
    summary = await service.summary(user.id, start_at, end_at)
    cashflow = await service.cashflow_summary(user.id, start_at, end_at)
    series = await service.cashflow_time_series(user.id, start_at, end_at, granularity)
    month_start = datetime.now(UTC).date().replace(day=1)
    month_start_at, month_end_at = month_bounds(month_start)
    month_summary = await service.summary(user.id, month_start_at, month_end_at)
    month_cashflow = await service.cashflow_summary(user.id, month_start_at, month_end_at)
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
        "month_pie": _pie_segments(
            _category_summary_with_income(month_summary["categories"], month_cashflow["income"])
        ),
        "category_summary": _category_summary_with_income(
            summary["categories"], cashflow["income"]
        ),
        "series": series,
        "max_total": max_total,
    }


def _period_range(
    period: str, date_from: str | None = None, date_to: str | None = None
) -> tuple[datetime, datetime, str]:
    today = datetime.now(UTC).date()
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
        start = datetime.fromisoformat(date_from).date()
        end = datetime.fromisoformat(date_to).date() + timedelta(days=1)
        days = (end - start).days
        granularity = "day" if days <= 62 else "month" if days <= 730 else "year"
    else:
        start = today.replace(day=1)
        end = today + timedelta(days=1)
        granularity = "day"
        period = "month"
    return (
        datetime.combine(start, datetime.min.time(), tzinfo=UTC),
        datetime.combine(end, datetime.min.time(), tzinfo=UTC),
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
    for index, item in enumerate(categories):
        amount = Decimal(item["total"])
        percent = (amount / total) * Decimal("100")
        start = cursor
        cursor += percent
        segments.append(
            {
                "category": item["category"],
                "total": amount,
                "percent": percent,
                "start": start,
                "end": cursor,
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


def _category_summary_with_income(categories: list[dict], income: Decimal) -> list[dict]:
    rows = list(categories)
    if income > 0:
        rows.append({"category": "Income", "total": income, "count": 0})
    return rows
