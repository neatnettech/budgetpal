from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Generic, Optional, TypeVar
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from budgetpal.domain.models import (
    Account,
    Budget,
    Category,
    RecurringTransaction,
    Transaction,
    TransactionType,
)
from budgetpal.infrastructure.entities import (
    AccountEntity,
    BudgetEntity,
    CategoryEntity,
    RecurringTransactionEntity,
    TransactionEntity,
)

T = TypeVar("T")
E = TypeVar("E")


class BaseRepository(ABC, Generic[T, E]):
    def __init__(self, session: Session, model_class: type[T], entity_class: type[E]):
        self.session = session
        self.model_class = model_class
        self.entity_class = entity_class

    @abstractmethod
    def _to_entity(self, model: T) -> E:
        pass

    @abstractmethod
    def _to_model(self, entity: E) -> T:
        pass

    def add(self, model: T) -> T:
        entity = self._to_entity(model)
        self.session.add(entity)
        self.session.flush()
        return self._to_model(entity)

    def get_by_id(self, id: UUID) -> Optional[T]:
        entity = self.session.get(self.entity_class, str(id))
        return self._to_model(entity) if entity else None

    def get_all(self) -> list[T]:
        stmt = select(self.entity_class)
        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]

    def update(self, model: T) -> T:
        entity = self.session.get(self.entity_class, str(model.id))
        if not entity:
            raise ValueError(f"Entity with id {model.id} not found")

        # Convert model to dict, excluding computed fields
        data = model.model_dump(exclude={"id", "created_at"})

        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        self.session.flush()
        return self._to_model(entity)

    def delete(self, id: UUID) -> None:
        entity = self.session.get(self.entity_class, str(id))
        if entity:
            self.session.delete(entity)
            self.session.flush()


class AccountRepository(BaseRepository[Account, AccountEntity]):
    def __init__(self, session: Session):
        super().__init__(session, Account, AccountEntity)

    def _to_entity(self, model: Account) -> AccountEntity:
        return AccountEntity(
            id=str(model.id),
            name=model.name,
            account_type=model.account_type,
            balance=model.balance,
            currency=model.currency,
            description=model.description,
            goal_amount=model.goal_amount,
            goal_date=model.goal_date,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: AccountEntity) -> Account:
        return Account(
            id=UUID(entity.id),
            name=entity.name,
            account_type=entity.account_type,
            balance=entity.balance,
            currency=entity.currency,
            description=entity.description,
            goal_amount=entity.goal_amount,
            goal_date=entity.goal_date,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get_active_accounts(self) -> list[Account]:
        stmt = select(AccountEntity).where(AccountEntity.is_active == True)
        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]

    def update(self, model: Account) -> Account:
        """Custom update method for accounts to handle date fields properly"""
        entity = self.session.get(AccountEntity, str(model.id))
        if not entity:
            raise ValueError(f"Account with id {model.id} not found")

        # Update fields manually to ensure proper type conversion
        entity.name = model.name
        entity.account_type = model.account_type
        entity.balance = model.balance
        entity.currency = model.currency
        entity.description = model.description
        entity.goal_amount = model.goal_amount
        entity.goal_date = model.goal_date
        entity.is_active = model.is_active
        # Don't update created_at, but update updated_at
        from datetime import datetime
        entity.updated_at = datetime.now()

        self.session.flush()
        return self._to_model(entity)

    def update_balance(self, account_id: UUID, amount: Decimal, operation: str = "add") -> Account:
        entity = self.session.get(AccountEntity, str(account_id))
        if not entity:
            raise ValueError(f"Account with id {account_id} not found")

        if operation == "add":
            entity.balance += amount
        elif operation == "subtract":
            entity.balance -= amount
        else:
            entity.balance = amount

        self.session.flush()
        return self._to_model(entity)


class CategoryRepository(BaseRepository[Category, CategoryEntity]):
    def __init__(self, session: Session):
        super().__init__(session, Category, CategoryEntity)

    def _to_entity(self, model: Category) -> CategoryEntity:
        return CategoryEntity(
            id=str(model.id),
            name=model.name,
            color=model.color,
            icon=model.icon,
            budget_limit=model.budget_limit,
            is_income=model.is_income,
            parent_id=str(model.parent_id) if model.parent_id else None,
            created_at=model.created_at,
        )

    def _to_model(self, entity: CategoryEntity) -> Category:
        return Category(
            id=UUID(entity.id),
            name=entity.name,
            color=entity.color,
            icon=entity.icon,
            budget_limit=entity.budget_limit,
            is_income=entity.is_income,
            parent_id=UUID(entity.parent_id) if entity.parent_id else None,
            created_at=entity.created_at,
        )


class TransactionRepository(BaseRepository[Transaction, TransactionEntity]):
    def __init__(self, session: Session):
        super().__init__(session, Transaction, TransactionEntity)

    def _to_entity(self, model: Transaction) -> TransactionEntity:
        return TransactionEntity(
            id=str(model.id),
            amount=model.amount,
            description=model.description,
            category_id=str(model.category_id) if model.category_id else None,
            transaction_type=model.transaction_type,
            from_account_id=str(model.from_account_id),
            to_account_id=str(model.to_account_id) if model.to_account_id else None,
            transaction_date=model.transaction_date,
            is_planned=model.is_planned,
            is_cleared=model.is_cleared,
            tags=model.tags,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: TransactionEntity) -> Transaction:
        return Transaction(
            id=UUID(entity.id),
            amount=entity.amount,
            description=entity.description,
            category_id=UUID(entity.category_id) if entity.category_id else None,
            transaction_type=entity.transaction_type,
            from_account_id=UUID(entity.from_account_id),
            to_account_id=UUID(entity.to_account_id) if entity.to_account_id else None,
            transaction_date=entity.transaction_date,
            is_planned=entity.is_planned,
            is_cleared=entity.is_cleared,
            tags=entity.tags,
            notes=entity.notes,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get_by_date_range(self, start_date: date, end_date: date, account_id: Optional[UUID] = None) -> list[Transaction]:
        stmt = select(TransactionEntity).where(
            and_(
                TransactionEntity.transaction_date >= start_date,
                TransactionEntity.transaction_date <= end_date,
            )
        )

        if account_id:
            stmt = stmt.where(
                (TransactionEntity.from_account_id == str(account_id))
                | (TransactionEntity.to_account_id == str(account_id))
            )

        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]

    def get_by_category(self, category_id: UUID) -> list[Transaction]:
        stmt = select(TransactionEntity).where(TransactionEntity.category_id == str(category_id))
        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]


class RecurringTransactionRepository(BaseRepository[RecurringTransaction, RecurringTransactionEntity]):
    def __init__(self, session: Session):
        super().__init__(session, RecurringTransaction, RecurringTransactionEntity)

    def _to_entity(self, model: RecurringTransaction) -> RecurringTransactionEntity:
        return RecurringTransactionEntity(
            id=str(model.id),
            amount=model.amount,
            description=model.description,
            category_id=str(model.category_id) if model.category_id else None,
            transaction_type=model.transaction_type,
            from_account_id=str(model.from_account_id),
            to_account_id=str(model.to_account_id) if model.to_account_id else None,
            frequency=model.frequency,
            start_date=model.start_date,
            end_date=model.end_date,
            next_date=model.next_date,
            is_active=model.is_active,
            auto_confirm=model.auto_confirm,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: RecurringTransactionEntity) -> RecurringTransaction:
        return RecurringTransaction(
            id=UUID(entity.id),
            amount=entity.amount,
            description=entity.description,
            category_id=UUID(entity.category_id) if entity.category_id else None,
            transaction_type=entity.transaction_type,
            from_account_id=UUID(entity.from_account_id),
            to_account_id=UUID(entity.to_account_id) if entity.to_account_id else None,
            frequency=entity.frequency,
            start_date=entity.start_date,
            end_date=entity.end_date,
            next_date=entity.next_date,
            is_active=entity.is_active,
            auto_confirm=entity.auto_confirm,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get_due_transactions(self, as_of_date: date) -> list[RecurringTransaction]:
        stmt = select(RecurringTransactionEntity).where(
            and_(
                RecurringTransactionEntity.is_active == True,
                RecurringTransactionEntity.next_date <= as_of_date,
            )
        )
        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]


class BudgetRepository(BaseRepository[Budget, BudgetEntity]):
    def __init__(self, session: Session):
        super().__init__(session, Budget, BudgetEntity)

    def _to_entity(self, model: Budget) -> BudgetEntity:
        return BudgetEntity(
            id=str(model.id),
            name=model.name,
            amount=model.amount,
            period_start=model.period_start,
            period_end=model.period_end,
            category_ids=[str(cat_id) for cat_id in model.category_ids],
            account_id=str(model.account_id) if model.account_id else None,
            rollover=model.rollover,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: BudgetEntity) -> Budget:
        return Budget(
            id=UUID(entity.id),
            name=entity.name,
            amount=entity.amount,
            period_start=entity.period_start,
            period_end=entity.period_end,
            category_ids=[UUID(cat_id) for cat_id in entity.category_ids],
            account_id=UUID(entity.account_id) if entity.account_id else None,
            rollover=entity.rollover,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get_active_budgets(self, as_of_date: date) -> list[Budget]:
        stmt = select(BudgetEntity).where(
            and_(
                BudgetEntity.period_start <= as_of_date,
                BudgetEntity.period_end >= as_of_date,
            )
        )
        entities = self.session.execute(stmt).scalars().all()
        return [self._to_model(entity) for entity in entities]