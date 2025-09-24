"""Interface definitions for better testability and decoupling"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from budgetpal.domain.models import Account, Category, Transaction


class TransactionFacadeInterface(ABC):
    """Interface for transaction facade operations"""

    @abstractmethod
    def get_all_transactions(self, limit: Optional[int] = None) -> List[dict]:
        """Get all transactions with enriched data for display"""
        pass

    @abstractmethod
    def get_transactions_by_account(self, account_id: UUID, limit: Optional[int] = None) -> List[dict]:
        """Get transactions for a specific account with enriched data"""
        pass

    @abstractmethod
    def add_transaction(self, transaction_data: dict) -> bool:
        """Add a new transaction and update account balances"""
        pass

    @abstractmethod
    def get_recent_transactions(self, days: int = 30, limit: int = 10) -> List[dict]:
        """Get recent transactions for dashboard display"""
        pass

    @abstractmethod
    def get_monthly_stats(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        """Get monthly transaction statistics"""
        pass

    @abstractmethod
    def count_transactions_by_account(self, account_id: UUID) -> int:
        """Count transactions related to a specific account"""
        pass


class TransactionServiceInterface(ABC):
    \"\"\"Interface for transaction business logic service\"\"\"

    @abstractmethod
    def create_transaction(self, transaction_data: dict) -> bool:
        \"\"\"Create a new transaction and update account balances\"\"\"
        pass

    @abstractmethod
    def get_all_transactions(self, limit: Optional[int] = None) -> List[dict]:
        \"\"\"Get all transactions with enriched data\"\"\"
        pass

    @abstractmethod
    def get_transactions_by_account(self, account_id: UUID, limit: Optional[int] = None) -> List[dict]:
        \"\"\"Get transactions for a specific account\"\"\"
        pass

    @abstractmethod
    def get_recent_transactions(self, days: int = 30, limit: int = 10) -> List[dict]:
        \"\"\"Get recent transactions\"\"\"
        pass

    @abstractmethod
    def get_monthly_stats(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        \"\"\"Get monthly statistics\"\"\"
        pass

    @abstractmethod
    def count_transactions_by_account(self, account_id: UUID) -> int:
        \"\"\"Count transactions for an account\"\"\"
        pass


class AccountServiceInterface(ABC):
    \"\"\"Interface for account business logic service\"\"\"

    @abstractmethod
    def create_account(self, account_data: dict) -> bool:
        \"\"\"Create a new account\"\"\"
        pass

    @abstractmethod
    def update_account(self, account_id: UUID, account_data: dict) -> bool:
        \"\"\"Update an existing account\"\"\"
        pass

    @abstractmethod
    def delete_account(self, account_id: UUID) -> bool:
        \"\"\"Delete an account and related transactions\"\"\"
        pass

    @abstractmethod
    def get_all_accounts(self) -> List[Account]:
        \"\"\"Get all accounts\"\"\"
        pass

    @abstractmethod
    def get_account_by_id(self, account_id: UUID) -> Optional[Account]:
        \"\"\"Get account by ID\"\"\"
        pass

    @abstractmethod
    def get_total_balance(self, currency: str = \"CHF\") -> Decimal:
        \"\"\"Get total balance\"\"\"
        pass


class AccountFacadeInterface(ABC):
    """Interface for account facade operations"""

    @abstractmethod
    def get_all_accounts(self) -> List[Account]:
        """Get all active accounts"""
        pass

    @abstractmethod
    def get_account_by_id(self, account_id: UUID) -> Optional[Account]:
        """Get account by ID"""
        pass

    @abstractmethod
    def get_total_balance(self, currency: str = "CHF") -> Decimal:
        """Get total balance across all accounts for given currency"""
        pass

    @abstractmethod
    def add_account(self, account_data: dict) -> bool:
        """Add a new account"""
        pass

    @abstractmethod
    def update_account(self, account_id: UUID, updated_data: dict) -> bool:
        """Update an existing account"""
        pass

    @abstractmethod
    def delete_account(self, account_id: UUID) -> bool:
        """Delete an account and its related transactions"""
        pass


class CategoryFacadeInterface(ABC):
    """Interface for category facade operations"""

    @abstractmethod
    def get_all_categories(self) -> List[Category]:
        """Get all categories"""
        pass

    @abstractmethod
    def get_income_categories(self) -> List[Category]:
        """Get income categories"""
        pass

    @abstractmethod
    def get_expense_categories(self) -> List[Category]:
        """Get expense categories"""
        pass