from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, TabbedContent, TabPane

from budgetpal.domain.models import AccountType, TransactionType
from budgetpal.infrastructure.database import Database, DatabaseConfig
from budgetpal.infrastructure.logging import get_logger
from dependency_injector.wiring import Provide, inject

from budgetpal.application.interfaces import AccountFacadeInterface, TransactionFacadeInterface
from budgetpal.infrastructure.containers import Container as DIContainer
from budgetpal.presentation.components.cards import (
    AccountCardClicked,
    AccountGrid,
    QuickStatsCard,
)
from budgetpal.presentation.widgets import RecentTransactions


class DashboardScreen(Screen):
    """Main dashboard screen with card-based account view"""

    BINDINGS = [
        Binding("a", "add_account", "Add Account"),
        Binding("r", "refresh", "Refresh"),
    ]

    @inject
    def __init__(
        self,
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__()
        self.transaction_facade = transaction_facade
        self.account_facade = account_facade
        self.account_grid = None
        self.stats_card = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="dashboard-container"):
            # Quick stats section
            yield Label("Financial Overview", id="overview-title")
            yield Container(id="stats-container")

            # Accounts section
            yield Label("Your Accounts", id="accounts-title")
            yield Container(id="accounts-container")

            # Recent transactions section
            yield Label("Recent Transactions", id="transactions-title")
            yield RecentTransactions()
        yield Footer()

    def on_mount(self) -> None:
        self.load_dashboard_data()

    def on_screen_resume(self) -> None:
        """Refresh dashboard when returning from other screens"""
        self.load_dashboard_data()

    def load_dashboard_data(self) -> None:
        """Load all dashboard components"""
        self.load_quick_stats()
        self.load_account_cards()

    def load_quick_stats(self) -> None:
        """Load quick statistics using facades"""
        stats_container = self.query_one("#stats-container", Container)
        stats_container.remove_children()

        # Use facades instead of direct repository access
        accounts = self.account_facade.get_all_accounts()
        total_balance = self.account_facade.get_total_balance("CHF")

        # Get monthly stats from transaction facade
        monthly_stats_data = self.transaction_facade.get_monthly_stats()

        # Create stats cards
        overview_stats = {
            "Total Balance": f"CHF {total_balance:,.2f}",
            "Active Accounts": str(len(accounts)),
        }

        monthly_stats = {
            "Income": f"+CHF {monthly_stats_data['income']:,.2f}",
            "Expenses": f"-CHF {monthly_stats_data['expenses']:,.2f}",
            "Net Flow": f"{'+' if monthly_stats_data['net'] >= 0 else ''}CHF {monthly_stats_data['net']:,.2f}",
        }

        # Create horizontal layout for stats
        overview_card = QuickStatsCard("Overview", overview_stats)
        monthly_card = QuickStatsCard("This Month", monthly_stats)
        stats_container.mount(overview_card)
        stats_container.mount(monthly_card)

    def load_account_cards(self) -> None:
        """Load account cards in grid layout using facades"""
        accounts_container = self.query_one("#accounts-container", Container)
        accounts_container.remove_children()

        # Use facade instead of direct repository access
        accounts = self.account_facade.get_all_accounts()

        if accounts:
            self.account_grid = AccountGrid(accounts)
            accounts_container.mount(self.account_grid)
        else:
            accounts_container.mount(Label("No accounts found. Press 'a' to add your first account."))

    @on(AccountCardClicked)
    def on_account_card_clicked(self, event: AccountCardClicked) -> None:
        """Handle account card clicks - navigate directly to account detail"""
        from budgetpal.presentation.screens.account_detail import AccountDetailScreen
        self.app.push_screen(
            AccountDetailScreen(event.account),
            callback=self.on_screen_return
        )

    def on_screen_return(self, result: bool) -> None:
        """Refresh dashboard when returning from account detail"""
        self.load_dashboard_data()

    def action_add_account(self) -> None:
        """Add new account from dashboard"""
        from budgetpal.presentation.modals.account_modals import AddAccountModal
        self.app.push_screen(AddAccountModal(), callback=self.on_account_added)

    def action_refresh(self) -> None:
        """Refresh dashboard data"""
        self.load_dashboard_data()
        # Also refresh recent transactions
        try:
            recent_trans = self.query_one(RecentTransactions)
            recent_trans.update_transactions()
        except:
            pass

    def on_account_added(self, result: bool) -> None:
        """Handle account addition from dashboard"""
        if result:
            self.action_refresh()


class AccountsScreen(Screen):
    """Accounts management screen"""

    BINDINGS = [
        Binding("a", "add_account", "Add Account"),
        Binding("e", "edit_account", "Edit Account"),
        Binding("d", "delete_account", "Delete Account"),
        Binding("v", "view_account", "View Details"),
        Binding("r", "refresh", "Refresh"),
    ]

    @inject
    def __init__(
        self,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__()
        self.account_facade = account_facade
        self.selected_account = None
        self.accounts_table = DataTable()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="accounts-container"):
            yield Label("Accounts Overview", id="accounts-title")
            with Container(id="accounts-summary"):
                yield Static("Total Balance: Loading...", id="total-balance")
                yield Static("Active Accounts: 0", id="account-count")
            yield self.accounts_table
        yield Footer()

    def on_mount(self) -> None:
        # Set up the accounts table
        self.accounts_table.add_columns(
            "Name", "Type", "Balance", "Currency", "Goal", "Progress"
        )
        self.accounts_table.cursor_type = "row"
        self.load_accounts()

    def load_accounts(self) -> None:
        self.accounts_table.clear()

        # Use facade instead of direct repository access
        accounts = self.account_facade.get_all_accounts()
        total_balance = self.account_facade.get_total_balance("CHF")

        for account in accounts:
            # Calculate goal progress
            progress = ""
            if account.goal_amount:
                pct = min(100, int((account.balance / account.goal_amount) * 100))
                progress = f"{pct}%"

            # Add row to table
            self.accounts_table.add_row(
                account.name,
                account.account_type.value.replace("_", " ").title(),
                f"{account.balance:,.2f}",
                account.currency,
                f"{account.goal_amount:,.2f}" if account.goal_amount else "-",
                progress,
                key=str(account.id),
            )

        # Update summary
        self.query_one("#total-balance").update(f"Total Balance: CHF {total_balance:,.2f}")
        self.query_one("#account-count").update(f"Active Accounts: {len(accounts)}")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Store selected account when row is clicked"""
        if event.row_key:
            from uuid import UUID
            self.selected_account = self.account_facade.get_account_by_id(UUID(str(event.row_key.value)))

    def action_add_account(self) -> None:
        from budgetpal.presentation.modals.account_modals import AddAccountModal
        self.app.push_screen(AddAccountModal(), callback=self.on_account_modified)

    def action_edit_account(self) -> None:
        if self.selected_account:
            from budgetpal.presentation.modals.account_modals import EditAccountModal
            self.app.push_screen(
                EditAccountModal(self.selected_account),
                callback=self.on_account_modified
            )
        else:
            from budgetpal.presentation.components.dialogs import InfoDialog
            self.app.push_screen(
                InfoDialog(
                    title="No Account Selected",
                    message="Please select an account from the table first."
                )
            )

    def action_delete_account(self) -> None:
        if self.selected_account:
            from budgetpal.presentation.modals.account_modals import DeleteAccountModal
            self.app.push_screen(
                DeleteAccountModal(self.selected_account),
                callback=self.on_account_modified
            )
        else:
            from budgetpal.presentation.components.dialogs import InfoDialog
            self.app.push_screen(
                InfoDialog(
                    title="No Account Selected",
                    message="Please select an account from the table first."
                )
            )

    def action_view_account(self) -> None:
        if self.selected_account:
            from budgetpal.presentation.screens.account_detail import AccountDetailScreen
            self.app.push_screen(AccountDetailScreen(self.selected_account))
        else:
            from budgetpal.presentation.components.dialogs import InfoDialog
            self.app.push_screen(
                InfoDialog(
                    title="No Account Selected",
                    message="Please select an account from the table first."
                )
            )

    def action_refresh(self) -> None:
        self.load_accounts()

    def on_account_modified(self, result: bool) -> None:
        if result:
            self.selected_account = None
            self.load_accounts()


class TransactionsScreen(Screen):
    """Transactions management screen"""

    BINDINGS = [
        Binding("a", "add_transaction", "Add Transaction"),
        Binding("e", "edit_transaction", "Edit"),
        Binding("d", "delete_transaction", "Delete"),
        Binding("f", "filter", "Filter"),
    ]

    @inject
    def __init__(
        self,
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__()
        self.transaction_facade = transaction_facade
        self.account_facade = account_facade
        self.transactions_table = DataTable()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="transactions-container"):
            yield Label("Transactions", id="transactions-title")
            yield self.transactions_table
        yield Footer()

    def on_mount(self) -> None:
        table = self.transactions_table
        table.add_columns("Date", "Description", "Category", "Account", "Amount", "Type")
        self.load_transactions()

    def load_transactions(self) -> None:
        self.transactions_table.clear()

        # Use facade instead of direct repository access
        transactions = self.transaction_facade.get_all_transactions(limit=100)

        for trans in transactions:
            self.transactions_table.add_row(
                trans["date"],
                trans["description"][:40],
                trans["category_name"],
                trans["account_name"],
                trans["amount_display"],
                trans["type"],
            )

    def action_add_transaction(self) -> None:
        # Use facade instead of direct repository access
        accounts = self.account_facade.get_all_accounts()

        if accounts:
            # Use the first account as default for transactions screen
            from budgetpal.presentation.modals.transaction_modals import AddTransactionModal
            # Note: We'll need to refactor AddTransactionModal to use facades too
            self.app.push_screen(AddTransactionModal(accounts[0].id), callback=self.on_transaction_added)
        else:
            from budgetpal.presentation.components.dialogs import InfoDialog
            self.app.push_screen(InfoDialog(
                title="No Accounts",
                message="Please create an account first before adding transactions."
            ))

    def on_transaction_added(self, result: bool) -> None:
        if result:
            self.load_transactions()

    def action_edit_transaction(self) -> None:
        """Edit selected transaction"""
        # TODO: Implement transaction editing functionality
        from budgetpal.presentation.components.dialogs import InfoDialog
        self.app.push_screen(InfoDialog(
            title="Feature Coming Soon",
            message="Transaction editing will be implemented soon."
        ))

    def action_delete_transaction(self) -> None:
        """Delete selected transaction"""
        # TODO: Implement transaction deletion functionality
        from budgetpal.presentation.components.dialogs import InfoDialog
        self.app.push_screen(InfoDialog(
            title="Feature Coming Soon",
            message="Transaction deletion will be implemented soon."
        ))

    def action_filter(self) -> None:
        """Filter transactions"""
        # TODO: Implement transaction filtering functionality
        from budgetpal.presentation.components.dialogs import InfoDialog
        self.app.push_screen(InfoDialog(
            title="Feature Coming Soon",
            message="Transaction filtering will be implemented soon."
        ))



class BudgetPalApp(App):
    """Main BudgetPal TUI Application"""

    CSS = """
    /* Dashboard Layout */
    #dashboard-container {
        layout: vertical;
        padding: 1;
    }

    #overview-title, #accounts-title, #transactions-title {
        text-style: bold;
        color: $primary;
        padding: 1 0;
        margin-top: 1;
    }

    #stats-container {
        layout: horizontal;
        height: 10;
        margin-bottom: 2;
    }

    QuickStatsCard {
        width: 1fr;
        height: 8;
        margin: 0 1;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    #accounts-container {
        margin-bottom: 2;
        min-height: 15;
    }

    AccountGrid {
        layout: grid;
        grid-size: 3;
        grid-gutter: 1;
        height: auto;
        min-height: 12;
    }

    /* Accounts Management Screen */
    #accounts-summary {
        layout: horizontal;
        margin: 1 0;
        height: 3;
        border: solid $primary;
        padding: 1;
    }

    #total-balance, #account-count {
        text-style: bold;
        color: $success;
        margin: 0 2;
    }

    #transactions-container {
        padding: 1;
    }


    /* Widgets */
    RecentTransactions {
        height: 20;
        margin-top: 1;
    }

    DataTable {
        height: 1fr;
        margin-top: 1;
    }

    /* Form styling */
    .form-label {
        color: $text;
        margin-top: 1;
        margin-bottom: 0;
    }

    .form-help {
        color: $text-muted;
        margin-bottom: 0;
    }

    .modal-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        text-align: center;
    }

    #button-container {
        margin-top: 2;
        align: center middle;
    }

    Input, Select {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("d", "switch_dashboard", "Dashboard"),
        Binding("a", "switch_accounts", "Accounts"),
        Binding("t", "switch_transactions", "Transactions"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, db_path: Path | None = None):
        super().__init__()
        self.logger = get_logger("budgetpal.app")

        self.logger.info("Initializing BudgetPal application", db_path=str(db_path) if db_path else "default")

        try:
            # Set up dependency injection
            self.container = DIContainer()
            self.container.config.database.path.from_value(db_path)
            self.container.wire(packages=["budgetpal.presentation"])
            self.logger.debug("Dependency injection container configured")

            # Initialize database and default data
            db = self.container.database()
            db.create_tables()
            self.logger.info("Database initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize application", error=str(e), exc_info=True)
            raise
        self._initialize_default_data(db)

    def _initialize_default_data(self, db: Database) -> None:
        """Create default categories and accounts if none exist"""
        from budgetpal.infrastructure.repositories import AccountRepository, CategoryRepository

        with db.get_session() as session:
            cat_repo = CategoryRepository(session)
            acc_repo = AccountRepository(session)

            # Check if we have categories
            if not cat_repo.get_all():
                from budgetpal.domain.models import Category

                default_categories = [
                    Category(name="Salary", icon="💰", color="#00FF00", is_income=True),
                    Category(name="Groceries", icon="🛒", color="#FFA500"),
                    Category(name="Transport", icon="🚗", color="#0080FF"),
                    Category(name="Utilities", icon="⚡", color="#FFD700"),
                    Category(name="Entertainment", icon="🎮", color="#FF69B4"),
                    Category(name="Healthcare", icon="🏥", color="#FF0000"),
                    Category(name="Education", icon="📚", color="#800080"),
                    Category(name="Savings", icon="🏦", color="#008000"),
                ]

                for category in default_categories:
                    cat_repo.add(category)

            # Check if we have accounts
            if not acc_repo.get_all():
                from budgetpal.domain.models import Account

                default_accounts = [
                    Account(
                        name="Main Checking",
                        account_type=AccountType.CHECKING,
                        balance=Decimal("5000"),
                        currency="CHF",
                    ),
                    Account(
                        name="Emergency Fund",
                        account_type=AccountType.SAVINGS,
                        balance=Decimal("10000"),
                        currency="CHF",
                        goal_amount=Decimal("20000"),
                    ),
                    Account(
                        name="Pillar 3a",
                        account_type=AccountType.RETIREMENT,
                        balance=Decimal("15000"),
                        currency="CHF",
                        description="Retirement savings account",
                    ),
                ]

                for account in default_accounts:
                    acc_repo.add(account)

            session.commit()

    def on_mount(self) -> None:
        # All screens now use dependency injection
        self.push_screen(DashboardScreen())

    def action_switch_dashboard(self) -> None:
        self.switch_screen(DashboardScreen())

    def action_switch_accounts(self) -> None:
        self.switch_screen(AccountsScreen())

    def action_switch_transactions(self) -> None:
        self.switch_screen(TransactionsScreen())

    def action_quit(self) -> None:
        self.exit()