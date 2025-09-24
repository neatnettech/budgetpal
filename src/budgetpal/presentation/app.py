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
from budgetpal.infrastructure.repositories import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
)
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

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
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
            yield RecentTransactions(self.db)
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
        """Load quick statistics"""
        stats_container = self.query_one("#stats-container", Container)
        stats_container.remove_children()

        with self.db.get_session() as session:
            acc_repo = AccountRepository(session)
            trans_repo = TransactionRepository(session)

            # Calculate statistics
            accounts = acc_repo.get_active_accounts()
            total_balance = sum(acc.balance for acc in accounts if acc.currency == "CHF")

            # Monthly stats
            from datetime import date
            today = date.today()
            start_of_month = date(today.year, today.month, 1)
            transactions = trans_repo.get_by_date_range(start_of_month, today)

            income = sum(
                t.amount for t in transactions if t.transaction_type == TransactionType.INCOME
            )
            expenses = sum(
                t.amount for t in transactions if t.transaction_type == TransactionType.EXPENSE
            )
            net = income - expenses

            # Create stats cards
            overview_stats = {
                "Total Balance": f"CHF {total_balance:,.2f}",
                "Active Accounts": str(len(accounts)),
            }

            monthly_stats = {
                "Income": f"+CHF {income:,.2f}",
                "Expenses": f"-CHF {expenses:,.2f}",
                "Net Flow": f"{'+' if net >= 0 else ''}CHF {net:,.2f}",
            }

            # Create horizontal layout for stats
            overview_card = QuickStatsCard("Overview", overview_stats)
            monthly_card = QuickStatsCard("This Month", monthly_stats)
            stats_container.mount(overview_card)
            stats_container.mount(monthly_card)

    def load_account_cards(self) -> None:
        """Load account cards in grid layout"""
        accounts_container = self.query_one("#accounts-container", Container)
        accounts_container.remove_children()

        with self.db.get_session() as session:
            repo = AccountRepository(session)
            accounts = repo.get_active_accounts()

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
            AccountDetailScreen(self.db, event.account),
            callback=self.on_screen_return
        )

    def on_screen_return(self, result: bool) -> None:
        """Refresh dashboard when returning from account detail"""
        self.load_dashboard_data()

    def action_add_account(self) -> None:
        """Add new account from dashboard"""
        from budgetpal.presentation.modals.account_modals import AddAccountModal
        self.app.push_screen(AddAccountModal(self.db), callback=self.on_account_added)

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

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
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
        total_balance = Decimal("0")

        with self.db.get_session() as session:
            repo = AccountRepository(session)
            accounts = repo.get_active_accounts()

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

                # Add to total if same currency (CHF)
                if account.currency == "CHF":
                    total_balance += account.balance

            # Update summary
            self.query_one("#total-balance").update(f"Total Balance: CHF {total_balance:,.2f}")
            self.query_one("#account-count").update(f"Active Accounts: {len(accounts)}")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Store selected account when row is clicked"""
        if event.row_key:
            with self.db.get_session() as session:
                repo = AccountRepository(session)
                from uuid import UUID
                self.selected_account = repo.get_by_id(UUID(str(event.row_key.value)))

    def action_add_account(self) -> None:
        from budgetpal.presentation.modals.account_modals import AddAccountModal
        self.app.push_screen(AddAccountModal(self.db), callback=self.on_account_modified)

    def action_edit_account(self) -> None:
        if self.selected_account:
            from budgetpal.presentation.modals.account_modals import EditAccountModal
            self.app.push_screen(
                EditAccountModal(self.db, self.selected_account),
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
                DeleteAccountModal(self.db, self.selected_account),
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
            self.app.push_screen(AccountDetailScreen(self.db, self.selected_account))
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

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
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

        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            cat_repo = CategoryRepository(session)
            acc_repo = AccountRepository(session)

            transactions = trans_repo.get_all()
            transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            for trans in transactions[:100]:  # Show last 100 transactions
                category_name = "-"
                if trans.category_id:
                    category = cat_repo.get_by_id(trans.category_id)
                    if category:
                        category_name = category.name

                account = acc_repo.get_by_id(trans.from_account_id)
                account_name = account.name if account else "-"

                amount_str = f"{trans.amount:,.2f}"
                if trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{amount_str}"
                elif trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{amount_str}"

                self.transactions_table.add_row(
                    trans.transaction_date.strftime("%Y-%m-%d"),
                    trans.description[:40],
                    category_name,
                    account_name,
                    amount_str,
                    trans.transaction_type.value,
                )

    def action_add_transaction(self) -> None:
        # For transactions screen, we need to pick a default account or show account selector
        with self.db.get_session() as session:
            from budgetpal.infrastructure.repositories import AccountRepository
            repo = AccountRepository(session)
            accounts = repo.get_active_accounts()

            if accounts:
                # Use the first account as default for transactions screen
                from budgetpal.presentation.modals.transaction_modals import AddTransactionModal
                self.app.push_screen(AddTransactionModal(self.db, accounts[0].id), callback=self.on_transaction_added)
            else:
                from budgetpal.presentation.components.dialogs import InfoDialog
                self.app.push_screen(InfoDialog(
                    title="No Accounts",
                    message="Please create an account first before adding transactions."
                ))

    def on_transaction_added(self, result: bool) -> None:
        if result:
            self.load_transactions()


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
        config = DatabaseConfig(db_path)
        self.db = Database(config)
        self.db.create_tables()
        self._initialize_default_data()

    def _initialize_default_data(self) -> None:
        """Create default categories and accounts if none exist"""
        with self.db.get_session() as session:
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
        self.push_screen(DashboardScreen(self.db))

    def action_switch_dashboard(self) -> None:
        self.switch_screen(DashboardScreen(self.db))

    def action_switch_accounts(self) -> None:
        self.switch_screen(AccountsScreen(self.db))

    def action_switch_transactions(self) -> None:
        self.switch_screen(TransactionsScreen(self.db))

    def action_quit(self) -> None:
        self.exit()