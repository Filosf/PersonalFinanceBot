from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ExpenseOut(BaseModel):
    id: int
    amount: Decimal
    currency: str
    description: str
    spent_at: datetime
    category: CategoryOut

    model_config = ConfigDict(from_attributes=True)


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    description: str = ""
    category_name: str | None = None
    spent_at: datetime | None = None


class ExpenseUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    description: str | None = None
    category_id: int | None = None
    spent_at: datetime | None = None


class SummaryCategory(BaseModel):
    category: str
    total: Decimal
    count: int


class SummaryOut(BaseModel):
    total: Decimal
    count: int
    categories: list[SummaryCategory]
