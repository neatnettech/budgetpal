from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"  # Like Pillar 3a
    GOAL = "goal"  # Saving for specific purpose
    EXPENSE_POOL = "expense_pool"  # Pre-allocated for future expenses
    CREDIT = "credit"
    CASH = "cash"


class RecurrenceFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Account(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    account_type: AccountType
    balance: Decimal = Decimal("0")
    currency: str = "CHF"  # Default to CHF for Swiss context
    description: Optional[str] = None
    goal_amount: Optional[Decimal] = None  # For goal-based accounts
    goal_date: Optional[date] = None  # Target date for goals
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Account name cannot be empty")
        return v.strip()

    @field_validator("goal_amount")
    @classmethod
    def goal_amount_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Goal amount must be positive")
        return v


class Category(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    color: str = "#808080"
    icon: str = "📁"
    budget_limit: Optional[Decimal] = None
    is_income: bool = False  # To differentiate income/expense categories
    parent_id: Optional[UUID] = None  # For subcategories
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Category name cannot be empty")
        return v.strip()


class Transaction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    amount: Decimal
    description: str
    category_id: Optional[UUID] = None  # Optional for transfers
    transaction_type: TransactionType
    from_account_id: UUID
    to_account_id: Optional[UUID] = None  # For transfers
    transaction_date: date
    is_planned: bool = False  # For future planned expenses
    is_cleared: bool = True  # For pending transactions
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    @field_validator("to_account_id")
    @classmethod
    def validate_transfer_account(cls, v: Optional[UUID], info) -> Optional[UUID]:
        if info.data.get("transaction_type") == TransactionType.TRANSFER and v is None:
            raise ValueError("Transfer transactions require a destination account")
        return v


class RecurringTransaction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    amount: Decimal
    description: str
    category_id: Optional[UUID] = None
    transaction_type: TransactionType
    from_account_id: UUID
    to_account_id: Optional[UUID] = None  # For recurring transfers
    frequency: RecurrenceFrequency
    start_date: date
    end_date: Optional[date] = None
    next_date: date
    is_active: bool = True
    auto_confirm: bool = False  # Whether to auto-create transactions
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: Optional[date], info) -> Optional[date]:
        if v and "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("End date must be after start date")
        return v


class Budget(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    amount: Decimal
    period_start: date
    period_end: date
    category_ids: list[UUID] = Field(default_factory=list)
    account_id: Optional[UUID] = None  # Link budget to specific account
    rollover: bool = False  # Whether unused budget rolls over
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Budget amount must be positive")
        return v

    @field_validator("period_end")
    @classmethod
    def period_end_after_start(cls, v: date, info) -> date:
        if "period_start" in info.data and v <= info.data["period_start"]:
            raise ValueError("Period end must be after period start")
        return v


class TransactionSummary(BaseModel):
    """Summary statistics for reporting"""
    period_start: date
    period_end: date
    total_income: Decimal = Decimal("0")
    total_expenses: Decimal = Decimal("0")
    total_transfers: Decimal = Decimal("0")
    net_flow: Decimal = Decimal("0")
    category_breakdown: dict[UUID, Decimal] = Field(default_factory=dict)
    account_balances: dict[UUID, Decimal] = Field(default_factory=dict)