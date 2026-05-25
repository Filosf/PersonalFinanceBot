from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    SummaryOut,
)
from app.db.models import User
from app.db.session import get_session
from app.services.categories import CategoryService
from app.services.expenses import ExpenseFilters, ExpenseService

router = APIRouter(prefix="/api")


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await CategoryService(session).list_categories(user.id)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    category = await CategoryService(session).get_or_create(user.id, payload.name)
    await session.commit()
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        category = await CategoryService(session).rename(user.id, category_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await CategoryService(session).delete(user.id, category_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/expenses", response_model=list[ExpenseOut])
async def list_expenses(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: int | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    text: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    filters = ExpenseFilters(date_from, date_to, category_id, min_amount, max_amount, text)
    return await ExpenseService(session).list_expenses(user.id, filters, limit, offset)


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    expense = await ExpenseService(session).add_expense(
        user_id=user.id,
        amount=payload.amount,
        description=payload.description,
        category_name=payload.category_name,
        spent_at=payload.spent_at,
        currency=user.currency,
    )
    await session.commit()
    return expense


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        expense = await ExpenseService(session).update_expense(
            user.id,
            expense_id,
            amount=payload.amount,
            category_id=payload.category_id,
            description=payload.description,
            spent_at=payload.spent_at,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return expense


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await ExpenseService(session).delete_expense(user.id, expense_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/summary", response_model=SummaryOut)
async def summary(
    date_from: datetime,
    date_to: datetime | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ExpenseService(session).summary(user.id, date_from, date_to or datetime.now(UTC))
