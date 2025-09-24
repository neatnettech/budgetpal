"""Tests for TransactionFacade with proper mocking and dependency injection"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from budgetpal.application.facades import TransactionFacade
from budgetpal.domain.models import Transaction, TransactionType, Account, Category


class TestTransactionFacade:
    """Test suite for TransactionFacade"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        mock_db = Mock()
        mock_session = Mock()

        # Create a proper context manager mock
        context_manager = Mock()
        context_manager.__enter__ = Mock(return_value=mock_session)
        context_manager.__exit__ = Mock(return_value=None)
        mock_db.get_session.return_value = context_manager

        return mock_db, mock_session

    @pytest.fixture
    def transaction_facade(self, mock_db):
        """Create TransactionFacade with mocked database"""
        mock_database, _ = mock_db
        return TransactionFacade(mock_database)

    @pytest.fixture
    def sample_transactions(self):
        """Create sample transactions for testing"""
        account_id = uuid4()
        category_id = uuid4()

        return [
            Transaction(
                id=uuid4(),
                amount=Decimal("100.00"),
                description="Grocery shopping",
                transaction_type=TransactionType.EXPENSE,
                from_account_id=account_id,
                category_id=category_id,
                transaction_date=date.today(),
            ),
            Transaction(
                id=uuid4(),
                amount=Decimal("2000.00"),
                description="Salary",
                transaction_type=TransactionType.INCOME,
                from_account_id=account_id,
                category_id=category_id,
                transaction_date=date.today(),
            ),
            Transaction(
                id=uuid4(),
                amount=Decimal("500.00"),
                description="Transfer to savings",
                transaction_type=TransactionType.TRANSFER,
                from_account_id=account_id,
                to_account_id=uuid4(),
                transaction_date=date.today(),
            )
        ]

    @pytest.fixture
    def sample_account(self):
        """Create sample account"""
        from budgetpal.domain.models import AccountType
        return Account(
            id=uuid4(),
            name="Test Account",
            account_type=AccountType.CHECKING,
            balance=Decimal("1000.00"),
            currency="CHF"
        )

    @pytest.fixture
    def sample_category(self):
        """Create sample category"""
        return Category(
            id=uuid4(),
            name="Test Category",
            is_income=False
        )

    def test_get_all_transactions(self, transaction_facade, mock_db, sample_transactions, sample_account, sample_category):
        """Test retrieving all transactions with enriched data"""
        _, mock_session = mock_db

        # Mock repository behavior
        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.CategoryRepository') as mock_cat_repo, \
             patch('budgetpal.application.facades.AccountRepository') as mock_acc_repo:

            # Setup mock repository instances
            mock_trans_repo_instance = Mock()
            mock_cat_repo_instance = Mock()
            mock_acc_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_cat_repo.return_value = mock_cat_repo_instance
            mock_acc_repo.return_value = mock_acc_repo_instance

            # Configure mock returns
            mock_trans_repo_instance.get_all.return_value = sample_transactions
            mock_cat_repo_instance.get_by_id.return_value = sample_category
            mock_acc_repo_instance.get_by_id.return_value = sample_account

            # Execute
            result = transaction_facade.get_all_transactions(limit=10)

            # Assertions
            assert len(result) == 3
            assert result[0]["description"] == "Grocery shopping"
            assert result[0]["amount_display"] == "-100.00"
            assert result[0]["type"] == "expense"
            assert result[0]["category_name"] == "Test Category"
            assert result[0]["account_name"] == "Test Account"

            assert result[1]["description"] == "Salary"
            assert result[1]["amount_display"] == "+2,000.00"
            assert result[1]["type"] == "income"

            assert result[2]["description"] == "Transfer to savings"
            assert result[2]["amount_display"] == "500.00"
            assert result[2]["type"] == "transfer"

    def test_get_transactions_by_account(self, transaction_facade, mock_db, sample_transactions, sample_category):
        """Test retrieving transactions for a specific account"""
        _, mock_session = mock_db
        account_id = sample_transactions[0].from_account_id

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.CategoryRepository') as mock_cat_repo:

            mock_trans_repo_instance = Mock()
            mock_cat_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_cat_repo.return_value = mock_cat_repo_instance

            # Filter transactions for the specific account
            account_transactions = [t for t in sample_transactions if t.from_account_id == account_id or t.to_account_id == account_id]
            mock_trans_repo_instance.get_all.return_value = account_transactions
            mock_cat_repo_instance.get_by_id.return_value = sample_category

            # Execute
            result = transaction_facade.get_transactions_by_account(account_id, limit=10)

            # Assertions
            assert len(result) >= 1
            for trans in result:
                assert "amount_display" in trans
                assert "type" in trans

    def test_add_transaction_success(self, transaction_facade, mock_db):
        """Test successful transaction addition"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.AccountRepository') as mock_acc_repo:

            mock_trans_repo_instance = Mock()
            mock_acc_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_acc_repo.return_value = mock_acc_repo_instance

            transaction_data = {
                "amount": "100.50",
                "description": "Test transaction",
                "transaction_type": TransactionType.EXPENSE,
                "from_account_id": uuid4(),
                "category_id": uuid4(),
                "transaction_date": date.today(),
                "notes": "Test notes"
            }

            # Execute
            result = transaction_facade.add_transaction(transaction_data)

            # Assertions
            assert result is True
            mock_trans_repo_instance.add.assert_called_once()
            mock_acc_repo_instance.update_balance.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_add_transaction_transfer(self, transaction_facade, mock_db):
        """Test adding a transfer transaction updates both accounts"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.AccountRepository') as mock_acc_repo:

            mock_trans_repo_instance = Mock()
            mock_acc_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_acc_repo.return_value = mock_acc_repo_instance

            from_account_id = uuid4()
            to_account_id = uuid4()

            transaction_data = {
                "amount": "500.00",
                "description": "Transfer",
                "transaction_type": TransactionType.TRANSFER,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "transaction_date": date.today(),
            }

            # Execute
            result = transaction_facade.add_transaction(transaction_data)

            # Assertions
            assert result is True
            mock_trans_repo_instance.add.assert_called_once()
            assert mock_acc_repo_instance.update_balance.call_count == 2

            # Check both accounts are updated
            calls = mock_acc_repo_instance.update_balance.call_args_list
            assert any(call[0][0] == from_account_id and call[0][2] == "subtract" for call in calls)
            assert any(call[0][0] == to_account_id and call[0][2] == "add" for call in calls)

    def test_add_transaction_failure(self, transaction_facade, mock_db):
        """Test transaction addition failure handling"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo:
            mock_trans_repo_instance = Mock()
            mock_trans_repo.return_value = mock_trans_repo_instance

            # Simulate database error
            mock_trans_repo_instance.add.side_effect = Exception("Database error")

            transaction_data = {
                "amount": "100.50",
                "description": "Test transaction",
                "transaction_type": TransactionType.EXPENSE,
                "from_account_id": uuid4(),
                "category_id": uuid4(),
                "transaction_date": date.today(),
            }

            # Execute
            result = transaction_facade.add_transaction(transaction_data)

            # Assertions
            assert result is False

    def test_get_recent_transactions(self, transaction_facade, mock_db, sample_transactions):
        """Test retrieving recent transactions"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo:
            mock_trans_repo_instance = Mock()
            mock_trans_repo.return_value = mock_trans_repo_instance

            # Set transaction dates to be within the recent period
            for trans in sample_transactions:
                trans.transaction_date = date.today() - timedelta(days=5)

            mock_trans_repo_instance.get_by_date_range.return_value = sample_transactions

            # Execute
            result = transaction_facade.get_recent_transactions(days=30, limit=5)

            # Assertions
            assert len(result) == 3
            assert all("date" in trans and "description" in trans for trans in result)
            assert result[0]["date"] is not None
            assert result[0]["amount"] is not None
            assert result[0]["type"] is not None

    def test_get_monthly_stats(self, transaction_facade, mock_db, sample_transactions):
        """Test retrieving monthly statistics"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo:
            mock_trans_repo_instance = Mock()
            mock_trans_repo.return_value = mock_trans_repo_instance

            mock_trans_repo_instance.get_by_date_range.return_value = sample_transactions

            # Execute
            result = transaction_facade.get_monthly_stats()

            # Assertions
            assert "income" in result
            assert "expenses" in result
            assert "net" in result
            assert result["income"] == Decimal("2000.00")  # From salary transaction
            assert result["expenses"] == Decimal("100.00")  # From grocery transaction
            assert result["net"] == Decimal("1900.00")  # income - expenses

    def test_get_monthly_stats_specific_month(self, transaction_facade, mock_db, sample_transactions):
        """Test retrieving statistics for a specific month"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo:
            mock_trans_repo_instance = Mock()
            mock_trans_repo.return_value = mock_trans_repo_instance

            mock_trans_repo_instance.get_by_date_range.return_value = sample_transactions

            # Execute
            result = transaction_facade.get_monthly_stats(year=2024, month=6)

            # Assertions
            assert "income" in result
            assert "expenses" in result
            assert "net" in result
            # Check that get_by_date_range was called with correct date range
            mock_trans_repo_instance.get_by_date_range.assert_called_once()

    def test_empty_transactions_list(self, transaction_facade, mock_db):
        """Test handling of empty transactions list"""
        _, mock_session = mock_db

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.CategoryRepository') as mock_cat_repo, \
             patch('budgetpal.application.facades.AccountRepository') as mock_acc_repo:

            mock_trans_repo_instance = Mock()
            mock_cat_repo_instance = Mock()
            mock_acc_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_cat_repo.return_value = mock_cat_repo_instance
            mock_acc_repo.return_value = mock_acc_repo_instance

            mock_trans_repo_instance.get_all.return_value = []

            # Execute
            result = transaction_facade.get_all_transactions()

            # Assertions
            assert result == []

    def test_transaction_without_category(self, transaction_facade, mock_db, sample_account):
        """Test handling transaction without category"""
        _, mock_session = mock_db

        # Create transaction without category
        transaction_without_category = Transaction(
            id=uuid4(),
            amount=Decimal("50.00"),
            description="Cash payment",
            transaction_type=TransactionType.EXPENSE,
            from_account_id=uuid4(),
            category_id=None,
            transaction_date=date.today(),
        )

        with patch('budgetpal.application.facades.TransactionRepository') as mock_trans_repo, \
             patch('budgetpal.application.facades.CategoryRepository') as mock_cat_repo, \
             patch('budgetpal.application.facades.AccountRepository') as mock_acc_repo:

            mock_trans_repo_instance = Mock()
            mock_cat_repo_instance = Mock()
            mock_acc_repo_instance = Mock()

            mock_trans_repo.return_value = mock_trans_repo_instance
            mock_cat_repo.return_value = mock_cat_repo_instance
            mock_acc_repo.return_value = mock_acc_repo_instance

            mock_trans_repo_instance.get_all.return_value = [transaction_without_category]
            mock_acc_repo_instance.get_by_id.return_value = sample_account

            # Execute
            result = transaction_facade.get_all_transactions()

            # Assertions
            assert len(result) == 1
            assert result[0]["category_name"] == "-"  # Default for no category