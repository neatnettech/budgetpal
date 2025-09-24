"""Dependency injection containers using dependency-injector"""

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from budgetpal.application.facades import AccountFacade, CategoryFacade, TransactionFacade
from budgetpal.application.services import (
    AccountService,
    BudgetService,
    RecurringTransactionService,
    ReportingService,
    TransactionService,
)
from budgetpal.infrastructure.database import Database, DatabaseConfig
from budgetpal.infrastructure.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    RecurringTransactionRepository,
    TransactionRepository,
)


class Container(containers.DeclarativeContainer):
    """Main DI container for the application"""

    # Configuration
    config = providers.Configuration()

    # Database
    database_config = providers.Factory(
        DatabaseConfig,
        db_path=config.database.path,
    )

    database = providers.Singleton(
        Database,
        config=database_config,
    )

    # Repositories - injected with database for session management
    transaction_repository = providers.Factory(
        TransactionRepository,
        db=database,
    )

    account_repository = providers.Factory(
        AccountRepository,
        db=database,
    )

    category_repository = providers.Factory(
        CategoryRepository,
        db=database,
    )

    budget_repository = providers.Factory(
        BudgetRepository,
        db=database,
    )

    recurring_transaction_repository = providers.Factory(
        RecurringTransactionRepository,
        db=database,
    )

    # Services - injected with repositories only
    transaction_service = providers.Factory(
        TransactionService,
        transaction_repo=transaction_repository,
        account_repo=account_repository,
        category_repo=category_repository,
    )

    account_service = providers.Factory(
        AccountService,
        account_repo=account_repository,
        transaction_repo=transaction_repository,
    )

    # Facades (Business Logic Layer)
    transaction_facade = providers.Factory(
        TransactionFacade,
        db=database,
    )

    account_facade = providers.Factory(
        AccountFacade,
        db=database,
    )

    category_facade = providers.Factory(
        CategoryFacade,
        db=database,
    )

    # Services (Application Layer)
    budget_service = providers.Factory(
        BudgetService,
        db=database,
    )

    recurring_transaction_service = providers.Factory(
        RecurringTransactionService,
        db=database,
    )

    reporting_service = providers.Factory(
        ReportingService,
        db=database,
    )

    # Wiring configuration
    wiring_config = containers.WiringConfiguration(packages=["budgetpal"])


class ApplicationContainer(containers.DeclarativeContainer):
    """Container for application-level dependencies"""

    container = providers.DependenciesContainer()

    # Main application components
    transaction_facade = providers.Factory(
        TransactionFacade,
        db=container.database,
    )

    account_facade = providers.Factory(
        AccountFacade,
        db=container.database,
    )

    category_facade = providers.Factory(
        CategoryFacade,
        db=container.database,
    )


# Dependency injection decorators for convenience
def inject_transaction_facade(facade: TransactionFacade = Provide[Container.transaction_facade]):
    """Decorator to inject TransactionFacade"""
    return inject(facade)


def inject_account_facade(facade: AccountFacade = Provide[Container.account_facade]):
    """Decorator to inject AccountFacade"""
    return inject(facade)


def inject_category_facade(facade: CategoryFacade = Provide[Container.category_facade]):
    """Decorator to inject CategoryFacade"""
    return inject(facade)


def inject_database(db: Database = Provide[Container.database]):
    """Decorator to inject Database"""
    return inject(db)