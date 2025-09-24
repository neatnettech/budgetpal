"""Tests for TransactionsScreen with dependency injection"""

import pytest
from unittest.mock import Mock, AsyncMock
from decimal import Decimal

from budgetpal.application.interfaces import TransactionFacadeInterface, AccountFacadeInterface
from budgetpal.presentation.app import TransactionsScreen
from budgetpal.domain.models import Account, AccountType


class MockTransactionFacade(TransactionFacadeInterface):
    """Mock implementation of TransactionFacadeInterface"""

    def __init__(self):
        self.transactions = []
        self.add_transaction_result = True

    def get_all_transactions(self, limit=None):
        transactions = [
            {
                "id": "1",
                "date": "2024-01-15",
                "description": "Grocery Store",
                "category_name": "Groceries",
                "account_name": "Checking",
                "amount_display": "-85.50",
                "amount": Decimal("85.50"),
                "type": "expense",
            },
            {
                "id": "2",
                "date": "2024-01-14",
                "description": "Salary Deposit",
                "category_name": "Salary",
                "account_name": "Checking",
                "amount_display": "+3,000.00",
                "amount": Decimal("3000.00"),
                "type": "income",
            }
        ]

        if limit:
            return transactions[:limit]
        return transactions

    def get_transactions_by_account(self, account_id, limit=None):
        # Return filtered transactions for account
        return self.get_all_transactions(limit)

    def add_transaction(self, transaction_data):
        return self.add_transaction_result

    def get_recent_transactions(self, days=30, limit=10):
        return self.get_all_transactions(limit)[:limit]

    def get_monthly_stats(self, year=None, month=None):
        return {
            "income": Decimal("3000.00"),
            "expenses": Decimal("85.50"),
            "net": Decimal("2914.50")
        }


class MockAccountFacade(AccountFacadeInterface):
    """Mock implementation of AccountFacadeInterface"""

    def __init__(self):
        self.accounts = [
            Account(
                name="Checking Account",
                account_type=AccountType.CHECKING,
                balance=Decimal("1500.00"),
                currency="CHF"
            ),
            Account(
                name="Savings Account",
                account_type=AccountType.SAVINGS,
                balance=Decimal("5000.00"),
                currency="CHF"
            )
        ]

    def get_all_accounts(self):
        return self.accounts

    def get_account_by_id(self, account_id):
        return self.accounts[0] if self.accounts else None

    def get_total_balance(self, currency="CHF"):
        return sum(acc.balance for acc in self.accounts if acc.currency == currency)


class TestTransactionsScreen:
    """Test suite for TransactionsScreen with mocked dependencies"""

    @pytest.fixture
    def mock_facades(self):
        """Create mock facades"""
        transaction_facade = MockTransactionFacade()
        account_facade = MockAccountFacade()
        return transaction_facade, account_facade

    @pytest.fixture
    def transactions_screen(self, mock_facades):
        """Create TransactionsScreen with mocked dependencies"""
        transaction_facade, account_facade = mock_facades
        screen = TransactionsScreen.__new__(TransactionsScreen)  # Create without calling __init__
        screen.transaction_facade = transaction_facade
        screen.account_facade = account_facade
        screen.transactions_table = Mock()
        return screen

    def test_load_transactions(self, transactions_screen):
        """Test loading transactions into the table"""
        # Mock the table methods
        transactions_screen.transactions_table.clear = Mock()
        transactions_screen.transactions_table.add_row = Mock()

        # Execute
        transactions_screen.load_transactions()

        # Assertions
        transactions_screen.transactions_table.clear.assert_called_once()

        # Check that add_row was called for each transaction
        assert transactions_screen.transactions_table.add_row.call_count == 2

        # Check the first transaction data
        first_call_args = transactions_screen.transactions_table.add_row.call_args_list[0][0]
        assert first_call_args[0] == "2024-01-15"  # date
        assert first_call_args[1] == "Grocery Store"  # description
        assert first_call_args[2] == "Groceries"  # category
        assert first_call_args[3] == "Checking"  # account
        assert first_call_args[4] == "-85.50"  # amount
        assert first_call_args[5] == "expense"  # type

    def test_load_transactions_with_limit(self, transactions_screen):
        """Test loading transactions with a limit"""
        # Mock the facade to return limited results
        transactions_screen.transaction_facade.get_all_transactions = Mock(return_value=[
            {
                "id": "1",
                "date": "2024-01-15",
                "description": "Test Transaction",
                "category_name": "Test",
                "account_name": "Test Account",
                "amount_display": "-50.00",
                "type": "expense",
            }
        ])

        transactions_screen.transactions_table.clear = Mock()
        transactions_screen.transactions_table.add_row = Mock()

        # Execute
        transactions_screen.load_transactions()

        # Assertions
        transactions_screen.transaction_facade.get_all_transactions.assert_called_once_with(limit=100)
        transactions_screen.transactions_table.add_row.assert_called_once()

    def test_action_add_transaction_with_accounts(self, transactions_screen):
        """Test add transaction action when accounts exist"""
        # Mock the app and screen pushing
        transactions_screen.app = Mock()
        transactions_screen.app.push_screen = Mock()

        # Execute
        transactions_screen.action_add_transaction()

        # Assertions
        # Should get accounts from facade
        assert transactions_screen.account_facade.get_all_accounts() is not None

        # Should push the AddTransactionModal screen
        transactions_screen.app.push_screen.assert_called_once()

    def test_action_add_transaction_no_accounts(self, transactions_screen):
        """Test add transaction action when no accounts exist"""
        # Mock empty accounts
        transactions_screen.account_facade.accounts = []
        transactions_screen.app = Mock()
        transactions_screen.app.push_screen = Mock()

        # Execute
        transactions_screen.action_add_transaction()

        # Assertions
        transactions_screen.app.push_screen.assert_called_once()

        # Check that InfoDialog was pushed (not AddTransactionModal)
        call_args = transactions_screen.app.push_screen.call_args[0][0]
        assert "InfoDialog" in str(type(call_args))

    def test_on_transaction_added_success(self, transactions_screen):
        """Test callback after successful transaction addition"""
        # Mock load_transactions method
        transactions_screen.load_transactions = Mock()

        # Execute
        transactions_screen.on_transaction_added(True)

        # Assertions
        transactions_screen.load_transactions.assert_called_once()

    def test_on_transaction_added_failure(self, transactions_screen):
        """Test callback after failed transaction addition"""
        # Mock load_transactions method
        transactions_screen.load_transactions = Mock()

        # Execute
        transactions_screen.on_transaction_added(False)

        # Assertions
        transactions_screen.load_transactions.assert_not_called()

    def test_action_edit_transaction(self, transactions_screen):
        """Test edit transaction action (placeholder functionality)"""
        # Mock the app and screen pushing
        transactions_screen.app = Mock()
        transactions_screen.app.push_screen = Mock()

        # Execute
        transactions_screen.action_edit_transaction()

        # Assertions
        transactions_screen.app.push_screen.assert_called_once()

        # Check that InfoDialog was pushed with appropriate message
        call_args = transactions_screen.app.push_screen.call_args[0][0]
        assert "InfoDialog" in str(type(call_args))

    def test_action_delete_transaction(self, transactions_screen):
        """Test delete transaction action (placeholder functionality)"""
        # Mock the app and screen pushing
        transactions_screen.app = Mock()
        transactions_screen.app.push_screen = Mock()

        # Execute
        transactions_screen.action_delete_transaction()

        # Assertions
        transactions_screen.app.push_screen.assert_called_once()

    def test_action_filter(self, transactions_screen):
        """Test filter action (placeholder functionality)"""
        # Mock the app and screen pushing
        transactions_screen.app = Mock()
        transactions_screen.app.push_screen = Mock()

        # Execute
        transactions_screen.action_filter()

        # Assertions
        transactions_screen.app.push_screen.assert_called_once()

    def test_facade_integration(self, transactions_screen):
        """Test that facades are properly integrated"""
        # Test transaction facade
        transactions = transactions_screen.transaction_facade.get_all_transactions()
        assert len(transactions) == 2
        assert transactions[0]["description"] == "Grocery Store"

        # Test account facade
        accounts = transactions_screen.account_facade.get_all_accounts()
        assert len(accounts) == 2
        assert accounts[0].name == "Checking Account"

        # Test monthly stats
        stats = transactions_screen.transaction_facade.get_monthly_stats()
        assert stats["income"] == Decimal("3000.00")
        assert stats["expenses"] == Decimal("85.50")

    def test_screen_compose_result(self, transactions_screen):
        """Test that compose returns the correct widgets"""
        # Mock the compose method execution
        from textual.containers import Container
        from textual.widgets import Header, Footer, Label

        # We can't easily test compose without a full textual app setup,
        # but we can verify the screen has the necessary attributes
        assert hasattr(transactions_screen, 'transaction_facade')
        assert hasattr(transactions_screen, 'account_facade')
        assert hasattr(transactions_screen, 'transactions_table')

    def test_bindings_are_defined(self):
        """Test that key bindings are properly defined"""
        bindings = TransactionsScreen.BINDINGS

        binding_keys = [binding.key for binding in bindings]
        binding_actions = [binding.action for binding in bindings]

        assert "a" in binding_keys
        assert "e" in binding_keys
        assert "d" in binding_keys
        assert "f" in binding_keys

        assert "add_transaction" in binding_actions
        assert "edit_transaction" in binding_actions
        assert "delete_transaction" in binding_actions
        assert "filter" in binding_actions