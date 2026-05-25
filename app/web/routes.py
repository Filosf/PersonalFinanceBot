from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import labels, normalize_locale
from app.db.models import User
from app.db.session import get_session
from app.services.access_tokens import AccessTokenError, verify_access_token
from app.services.categories import CategoryService
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
    return request.app.state.templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "t": labels(user.locale),
            "categories": categories,
            "expenses": expenses,
            "analytics": analytics,
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
    )
    await session.commit()
    return await expenses_table(request, user=user, session=session)


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
    categories = await CategoryService(session).list_categories(user.id)
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/category_options.html",
        {"request": request, "user": user, "categories": categories},
    )


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
    series = await service.time_series(user.id, start_at, end_at, granularity)
    max_total = max((Decimal(item["total"]) for item in series), default=Decimal("0"))
    return {
        "period": period,
        "date_from": start_at.date().isoformat(),
        "date_to": (end_at - timedelta(days=1)).date().isoformat(),
        "granularity": granularity,
        "summary": summary,
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
