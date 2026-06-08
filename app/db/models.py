import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jerusalem")
    currency: Mapped[str] = mapped_column(String(8), default="ILS")
    locale: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="user")
    recurring_payments: Mapped[list["RecurringPayment"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")
    budgets: Mapped[list["MonthlyBudget"]] = relationship(back_populates="category")
    recurring_payments: Mapped[list["RecurringPayment"]] = relationship(back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="ILS")
    kind: Mapped[str] = mapped_column(String(16), default="expense")
    description: Mapped[str] = mapped_column(String(500), default="")
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="expenses")
    category: Mapped[Category] = relationship(back_populates="expenses")
    recurring_occurrence: Mapped["RecurringPaymentOccurrence | None"] = relationship(
        back_populates="expense"
    )


class MonthlyBudget(Base):
    __tablename__ = "monthly_budgets"
    __table_args__ = (
        Index(
            "uq_monthly_budgets_user_month_total",
            "user_id",
            "month_start",
            unique=True,
            postgresql_where=text("category_id IS NULL"),
        ),
        Index(
            "uq_monthly_budgets_user_month_category",
            "user_id",
            "month_start",
            "category_id",
            unique=True,
            postgresql_where=text("category_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    month_start: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship()
    category: Mapped[Category | None] = relationship(back_populates="budgets")


class ReceiptDraft(Base):
    __tablename__ = "receipt_drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    spent_at: Mapped[date | None] = mapped_column(Date)
    merchant: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecurringPayment(Base):
    __tablename__ = "recurring_payments"
    __table_args__ = (
        Index("ix_recurring_payments_user_series", "user_id", "series_id"),
        Index("ix_recurring_payments_user_period", "user_id", "start_month", "end_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    amount_source: Mapped[str] = mapped_column(String(16))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_count: Mapped[int | None] = mapped_column(Integer)
    charge_day: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    start_month: Mapped[date] = mapped_column(Date, index=True)
    end_month: Mapped[date | None] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="recurring_payments")
    category: Mapped[Category] = relationship(back_populates="recurring_payments")
    occurrences: Mapped[list["RecurringPaymentOccurrence"]] = relationship(
        back_populates="recurring_payment"
    )


class RecurringPaymentOccurrence(Base):
    __tablename__ = "recurring_payment_occurrences"
    __table_args__ = (
        UniqueConstraint("user_id", "series_id", "month_start", name="uq_recurring_series_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recurring_payment_id: Mapped[int] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="CASCADE"), index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    month_start: Mapped[date] = mapped_column(Date, index=True)
    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recurring_payment: Mapped[RecurringPayment] = relationship(back_populates="occurrences")
    expense: Mapped[Expense] = relationship(back_populates="recurring_occurrence")
