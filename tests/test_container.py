"""Tests for dependency injection container"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory

from budgetpal.infrastructure.containers import Container
from budgetpal.application.facades import TransactionFacade, AccountFacade, CategoryFacade
from budgetpal.infrastructure.database import Database


class TestContainer:
    """Test suite for dependency injection container"""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path"""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    def container(self, temp_db_path):
        """Create a configured container"""
        container = Container()
        container.config.database.path.from_value(temp_db_path)
        return container

    def test_database_creation(self, container):
        """Test that database is properly configured"""
        database = container.database()

        assert isinstance(database, Database)
        assert database is not None

    def test_facade_creation(self, container):
        """Test that facades are properly created"""
        transaction_facade = container.transaction_facade()
        account_facade = container.account_facade()
        category_facade = container.category_facade()

        assert isinstance(transaction_facade, TransactionFacade)
        assert isinstance(account_facade, AccountFacade)
        assert isinstance(category_facade, CategoryFacade)

    def test_singleton_behavior(self, container):
        """Test that database is singleton"""
        db1 = container.database()
        db2 = container.database()

        assert db1 is db2  # Same instance

    def test_factory_behavior(self, container):
        """Test that facades are factories (new instance each time)"""
        facade1 = container.transaction_facade()
        facade2 = container.transaction_facade()

        # Should be different instances
        assert facade1 is not facade2
        # But should have same database instance
        assert facade1.db is facade2.db

    def test_wiring_configuration(self, container):
        """Test that container can be wired"""
        # This should not raise an exception
        container.wire(packages=["budgetpal.presentation"])

    def test_container_provides_all_services(self, container):
        """Test that container provides all expected services"""
        # Test that we can create all services without error
        services = [
            container.transaction_facade(),
            container.account_facade(),
            container.category_facade(),
            container.budget_service(),
            container.recurring_transaction_service(),
            container.reporting_service(),
        ]

        assert len(services) == 6
        assert all(service is not None for service in services)

    def test_repository_creation(self, container):
        """Test that repositories are properly created"""
        # These are factories, so they return functions that create repos
        account_repo_factory = container.account_repository
        transaction_repo_factory = container.transaction_repository

        assert account_repo_factory is not None
        assert transaction_repo_factory is not None

    def test_config_injection(self, temp_db_path):
        """Test configuration injection"""
        container = Container()

        # Set configuration
        container.config.database.path.from_value(str(temp_db_path))

        # Get database config
        db_config = container.database_config()

        assert db_config.db_path == temp_db_path

    def test_container_reset(self, container):
        """Test container can be reset"""
        # Create some instances
        db1 = container.database()
        facade1 = container.transaction_facade()

        # Reset container
        container.reset_singletons()

        # Get new instances
        db2 = container.database()

        # Database should be different instance after reset
        assert db1 is not db2

    @patch('budgetpal.infrastructure.containers.Database')
    def test_container_with_mock_database(self, mock_database_class, temp_db_path):
        """Test container with mocked database"""
        mock_db = Mock()
        mock_database_class.return_value = mock_db

        container = Container()
        container.config.database.path.from_value(temp_db_path)

        # Override database provider with mock
        container.database.override(mock_db)

        facade = container.transaction_facade()

        assert facade.db is mock_db

    def test_container_dependencies(self, container):
        """Test that dependencies are properly injected"""
        facade = container.transaction_facade()

        # Facade should have access to database
        assert hasattr(facade, 'db')
        assert facade.db is not None

    def test_multiple_containers(self, temp_db_path):
        """Test that multiple containers can be created independently"""
        container1 = Container()
        container2 = Container()

        container1.config.database.path.from_value(temp_db_path)
        container2.config.database.path.from_value(temp_db_path)

        db1 = container1.database()
        db2 = container2.database()

        # Should be different instances from different containers
        assert db1 is not db2

    def test_container_provides_all_repositories(self, container):
        """Test that all repository types are available"""
        repository_factories = [
            container.account_repository,
            container.transaction_repository,
            container.category_repository,
            container.budget_repository,
            container.recurring_transaction_repository,
        ]

        assert all(factory is not None for factory in repository_factories)