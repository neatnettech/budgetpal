"""Facade layer providing high-level interfaces for UI components"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from budgetpal.application.interfaces import (
    AccountFacadeInterface,
    CategoryFacadeInterface,
    TransactionFacadeInterface,
)
from budgetpal.domain.models import Account, Category, Transaction, TransactionType
from budgetpal.infrastructure.database import Database
from budgetpal.infrastructure.logging import LoggerMixin
from budgetpal.infrastructure.repositories import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
)


class TransactionFacade(TransactionFacadeInterface, LoggerMixin):
    """Facade for transaction operations, providing a clean interface for UI components"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def get_all_transactions(self, limit: Optional[int] = None) -> List[dict]:
        """Get all transactions with enriched data for display"""
        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            cat_repo = CategoryRepository(session)
            acc_repo = AccountRepository(session)

            transactions = trans_repo.get_all()
            transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            if limit:
                transactions = transactions[:limit]

            enriched_transactions = []
            for trans in transactions:
                # Get category name
                category_name = "-"
                if trans.category_id:
                    category = cat_repo.get_by_id(trans.category_id)
                    if category:
                        category_name = category.name

                # Get account name
                account = acc_repo.get_by_id(trans.from_account_id)
                account_name = account.name if account else "-"

                # Format amount
                amount_str = f"{trans.amount:,.2f}"
                if trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{amount_str}"
                elif trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{amount_str}"

                enriched_transactions.append({
                    "id": trans.id,
                    "date": trans.transaction_date.strftime("%Y-%m-%d"),
                    "description": trans.description,
                    "category_name": category_name,
                    "account_name": account_name,
                    "amount_display": amount_str,
                    "amount": trans.amount,
                    "type": trans.transaction_type.value,
                    "type_enum": trans.transaction_type,
                    "from_account_id": trans.from_account_id,
                    "to_account_id": trans.to_account_id,
                    "category_id": trans.category_id,
                    "notes": trans.notes,
                })

            return enriched_transactions

    def get_transactions_by_account(self, account_id: UUID, limit: Optional[int] = None) -> List[dict]:
        """Get transactions for a specific account with enriched data"""
        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            cat_repo = CategoryRepository(session)

            all_transactions = trans_repo.get_all()
            account_transactions = [
                t for t in all_transactions
                if t.from_account_id == account_id or t.to_account_id == account_id
            ]
            account_transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            if limit:
                account_transactions = account_transactions[:limit]

            enriched_transactions = []
            for trans in account_transactions:
                # Get category name
                category_name = "-"
                if trans.category_id:
                    category = cat_repo.get_by_id(trans.category_id)
                    if category:
                        category_name = category.name

                # Determine amount display for this account
                if trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{trans.amount:,.2f}"
                elif trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{trans.amount:,.2f}"
                elif trans.transaction_type == TransactionType.TRANSFER:
                    if trans.from_account_id == account_id:
                        amount_str = f"-{trans.amount:,.2f}"
                    else:
                        amount_str = f"+{trans.amount:,.2f}"
                else:
                    amount_str = f"{trans.amount:,.2f}"

                enriched_transactions.append({
                    "id": trans.id,
                    "date": trans.transaction_date.strftime("%Y-%m-%d"),
                    "description": trans.description,
                    "category_name": category_name,
                    "amount_display": amount_str,
                    "amount": trans.amount,
                    "type": trans.transaction_type.value,
                    "type_enum": trans.transaction_type,
                })

            return enriched_transactions

    def add_transaction(self, transaction_data: dict) -> bool:
        """Add a new transaction and update account balances"""
        try:
            # Convert string UUIDs to UUID objects if needed
            from_account_id = transaction_data["from_account_id"]
            if isinstance(from_account_id, str):
                from_account_id = UUID(from_account_id)

            to_account_id = transaction_data.get("to_account_id")
            if to_account_id and isinstance(to_account_id, str):
                to_account_id = UUID(to_account_id)

            category_id = transaction_data.get("category_id")
            if category_id and isinstance(category_id, str):
                category_id = UUID(category_id)

            # Create transaction
            transaction = Transaction(
                amount=Decimal(str(transaction_data["amount"])),
                description=transaction_data["description"],
                transaction_type=transaction_data["transaction_type"],
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                category_id=category_id,
                transaction_date=transaction_data["transaction_date"],
                notes=transaction_data.get("notes"),
            )

            with self.db.get_session() as session:
                trans_repo = TransactionRepository(session)
                acc_repo = AccountRepository(session)

                # Add transaction
                trans_repo.add(transaction)

                # Update account balances
                if transaction.transaction_type == TransactionType.EXPENSE:
                    acc_repo.update_balance(transaction.from_account_id, transaction.amount, "subtract")
                elif transaction.transaction_type == TransactionType.INCOME:
                    acc_repo.update_balance(transaction.from_account_id, transaction.amount, "add")
                elif transaction.transaction_type == TransactionType.TRANSFER:
                    acc_repo.update_balance(transaction.from_account_id, transaction.amount, "subtract")
                    if transaction.to_account_id:
                        acc_repo.update_balance(transaction.to_account_id, transaction.amount, "add")

                session.commit()

            return True
        except Exception as e:
            self.logger.error("Failed to add transaction",
                            error=str(e),
                            transaction_data=transaction_data,
                            exc_info=True)
            return False

    def get_recent_transactions(self, days: int = 30, limit: int = 10) -> List[dict]:
        """Get recent transactions for dashboard display"""
        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)

            today = date.today()
            start_date = today - timedelta(days=days)
            transactions = trans_repo.get_by_date_range(start_date, today)

            # Sort by date descending
            transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            recent_transactions = []
            for trans in transactions[:limit]:
                amount_str = f"{trans.amount:,.2f}"
                if trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{amount_str}"
                elif trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{amount_str}"

                recent_transactions.append({
                    "date": trans.transaction_date.strftime("%m/%d"),
                    "description": trans.description[:30],
                    "amount": amount_str,
                    "type": trans.transaction_type.value[:3].upper(),
                })

            return recent_transactions

    def get_monthly_stats(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        """Get monthly transaction statistics"""
        if year is None or month is None:
            today = date.today()
            year = today.year
            month = today.month

        start_of_month = date(year, month, 1)
        today = date.today()

        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            transactions = trans_repo.get_by_date_range(start_of_month, today)

            income = sum(
                t.amount for t in transactions if t.transaction_type == TransactionType.INCOME
            )
            expenses = sum(
                t.amount for t in transactions if t.transaction_type == TransactionType.EXPENSE
            )
            net = income - expenses

            return {
                "income": income,
                "expenses": expenses,
                "net": net,
            }

    def count_transactions_by_account(self, account_id: UUID) -> int:
        """Count transactions related to a specific account"""
        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            all_trans = trans_repo.get_all()
            return sum(
                1 for t in all_trans
                if t.from_account_id == account_id or t.to_account_id == account_id
            )


class AccountFacade(AccountFacadeInterface):
    """Facade for account operations"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_accounts(self) -> List[Account]:
        """Get all active accounts"""
        with self.db.get_session() as session:
            acc_repo = AccountRepository(session)
            return acc_repo.get_active_accounts()

    def get_account_by_id(self, account_id: UUID) -> Optional[Account]:
        """Get account by ID"""
        with self.db.get_session() as session:
            acc_repo = AccountRepository(session)
            return acc_repo.get_by_id(account_id)

    def get_total_balance(self, currency: str = "CHF") -> Decimal:
        """Get total balance across all accounts for given currency"""
        accounts = self.get_all_accounts()
        return sum(acc.balance for acc in accounts if acc.currency == currency)

    def add_account(self, account_data: dict) -> bool:
        """Add a new account"""
        try:
            with self.db.get_session() as session:
                acc_repo = AccountRepository(session)

                account = Account(
                    name=account_data["name"],
                    account_type=account_data["account_type"],
                    balance=account_data["balance"],
                    currency=account_data["currency"],
                    description=account_data.get("description"),
                    goal_amount=account_data.get("goal_amount"),
                    goal_date=account_data.get("goal_date"),
                )

                acc_repo.add(account)
                session.commit()
                return True
        except Exception:
            return False

    def update_account(self, account_id: UUID, updated_data: dict) -> bool:
        """Update an existing account"""
        try:
            with self.db.get_session() as session:
                acc_repo = AccountRepository(session)

                account = acc_repo.get_by_id(account_id)
                if not account:
                    return False

                # Update account fields
                account.name = updated_data["name"]
                account.account_type = updated_data["account_type"]
                account.balance = updated_data["balance"]
                account.currency = updated_data["currency"]
                account.description = updated_data.get("description")
                account.goal_amount = updated_data.get("goal_amount")
                account.goal_date = updated_data.get("goal_date")

                acc_repo.update(account)
                session.commit()
                return True
        except Exception:
            return False

    def delete_account(self, account_id: UUID) -> bool:
        """Delete an account and its related transactions"""
        try:
            with self.db.get_session() as session:
                acc_repo = AccountRepository(session)
                trans_repo = TransactionRepository(session)

                # Delete related transactions first
                all_trans = trans_repo.get_all()
                for trans in all_trans:
                    if trans.from_account_id == account_id or trans.to_account_id == account_id:
                        trans_repo.delete(trans.id)

                # Delete the account
                acc_repo.delete(account_id)
                session.commit()
                return True
        except Exception:
            return False


class CategoryFacade(CategoryFacadeInterface):
    """Facade for category operations"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_categories(self) -> List[Category]:
        """Get all categories"""
        with self.db.get_session() as session:
            cat_repo = CategoryRepository(session)
            return cat_repo.get_all()

    def get_income_categories(self) -> List[Category]:
        """Get income categories"""
        categories = self.get_all_categories()
        return [cat for cat in categories if cat.is_income]

    def get_expense_categories(self) -> List[Category]:
        """Get expense categories"""
        categories = self.get_all_categories()
        return [cat for cat in categories if not cat.is_income]