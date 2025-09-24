"""Account detail view screen"""

from datetime import date, timedelta
from decimal import Decimal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar, Static

from dependency_injector.wiring import Provide, inject

from budgetpal.application.interfaces import AccountFacadeInterface, TransactionFacadeInterface
from budgetpal.domain.models import Account, TransactionType
from budgetpal.infrastructure.containers import Container as DIContainer


class AccountDetailScreen(Screen):
    """Detailed view of a single account with transactions and statistics"""

    CSS = """
    AccountDetailScreen {
        background: $surface;
    }

    #account-header {
        height: 8;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }

    .account-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .account-balance {
        text-style: bold;
        color: $success;
    }

    #statistics-container {
        height: 12;
        layout: horizontal;
        margin: 1;
    }

    .stat-card {
        border: solid $primary;
        padding: 1;
        margin: 0 1;
        width: 1fr;
    }

    .stat-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    .stat-value {
        text-style: bold;
        color: $primary;
    }

    #transactions-container {
        margin: 1;
    }

    .section-title {
        text-style: bold;
        color: $primary;
        margin: 1 0;
    }


    ProgressBar {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("e", "edit_account", "Edit Account"),
        Binding("t", "add_transaction", "Add Transaction"),
        Binding("b", "back", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    @inject
    def __init__(
        self,
        account: Account,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
    ):
        super().__init__()
        self.account = account
        self.account_facade = account_facade
        self.transaction_facade = transaction_facade
        self.transactions_table = DataTable()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with ScrollableContainer():
            # Account Header
            with Container(id="account-header"):
                yield Label(f"{self.account.name}", classes="account-title")
                yield Label(
                    f"Type: {self.account.account_type.value.replace('_', ' ').title()}",
                    classes="account-info"
                )
                yield Label(
                    f"Balance: {self.account.balance:,.2f} {self.account.currency}",
                    classes="account-balance"
                )

                if self.account.goal_amount:
                    progress = min(1.0, float(self.account.balance / self.account.goal_amount))
                    yield ProgressBar(total=1.0, show_percentage=True, id="goal-progress")
                    yield Label(
                        f"Goal: {self.account.goal_amount:,.2f} {self.account.currency}",
                        classes="account-info"
                    )

            # Statistics
            with Container(id="statistics-container"):
                with Container(classes="stat-card"):
                    yield Label("This Month Income", classes="stat-label")
                    yield Label("0.00", id="monthly-income", classes="stat-value")

                with Container(classes="stat-card"):
                    yield Label("This Month Expenses", classes="stat-label")
                    yield Label("0.00", id="monthly-expenses", classes="stat-value")

                with Container(classes="stat-card"):
                    yield Label("Average Monthly", classes="stat-label")
                    yield Label("0.00", id="monthly-average", classes="stat-value")

            # Recent Transactions
            with Container(id="transactions-container"):
                yield Label("Recent Transactions", classes="section-title")
                yield self.transactions_table


        yield Footer()

    def on_mount(self) -> None:
        # Set up transactions table
        self.transactions_table.add_columns(
            "Date", "Description", "Category", "Amount", "Type", "Balance"
        )
        self.load_data()

        # Update goal progress if present
        if self.account.goal_amount:
            progress_bar = self.query_one("#goal-progress", ProgressBar)
            progress_bar.update(progress=float(self.account.balance / self.account.goal_amount))

    def load_data(self) -> None:
        """Load account transactions and statistics"""
        self.update_account_header()
        self.load_transactions()
        self.load_statistics()

    def update_account_header(self) -> None:
        """Update the account header with current information"""
        try:
            # Update balance display
            balance_label = self.query_one(".account-balance", Label)
            balance_label.update(f"Balance: {self.account.balance:,.2f} {self.account.currency}")

            # Update goal progress if present
            if self.account.goal_amount:
                progress_bar = self.query_one("#goal-progress", ProgressBar)
                progress = min(1.0, float(self.account.balance / self.account.goal_amount))
                progress_bar.update(progress=progress)
        except:
            pass  # Elements might not exist yet

    def load_transactions(self) -> None:
        """Load recent transactions for this account using facades"""
        self.transactions_table.clear()

        # Use facade instead of direct repository access
        account_transactions = self.transaction_facade.get_transactions_by_account(
            self.account.id, limit=50
        )

        running_balance = self.account.balance
        for trans in account_transactions:
            self.transactions_table.add_row(
                trans["date"],
                trans["description"][:40],
                trans["category_name"],
                trans["amount_display"],
                trans["type"],
                f"{running_balance:,.2f}",
            )

            # Update running balance (going backwards in time)
            if trans["type_enum"] == TransactionType.INCOME:
                running_balance -= trans["amount"]
            elif trans["type_enum"] == TransactionType.EXPENSE:
                running_balance += trans["amount"]
            elif trans["type_enum"] == TransactionType.TRANSFER:
                # This logic would need the facade to provide more context
                # For now, just use the amount as-is
                if "-" in trans["amount_display"]:
                    running_balance += trans["amount"]
                else:
                    running_balance -= trans["amount"]

    def load_statistics(self) -> None:
        """Calculate and display account statistics using facades"""
        # Get monthly stats from transaction facade
        monthly_stats = self.transaction_facade.get_monthly_stats()

        # For now, use general stats (this could be enhanced to be account-specific)
        self.query_one("#monthly-income").update(f"{monthly_stats['income']:,.2f}")
        self.query_one("#monthly-expenses").update(f"{monthly_stats['expenses']:,.2f}")

        # Calculate a simple average (this is simplified)
        average = monthly_stats['expenses'] / 6 if monthly_stats['expenses'] else 0
        self.query_one("#monthly-average").update(f"{average:,.2f}")




    def action_edit_account(self) -> None:
        from budgetpal.presentation.modals.account_modals import EditAccountModal
        self.app.push_screen(
            EditAccountModal(self.account),
            callback=self.on_account_modified
        )

    def action_add_transaction(self) -> None:
        from budgetpal.presentation.modals.transaction_modals import AddTransactionModal
        # Pre-select this account in the modal
        self.app.push_screen(
            AddTransactionModal(self.account.id),
            callback=self.on_transaction_added
        )

    def action_back(self) -> None:
        self.go_back()

    def go_back(self) -> None:
        """Return to previous screen and signal refresh needed"""
        self.dismiss(True)

    def action_refresh(self) -> None:
        # Refresh account data using facade
        updated_account = self.account_facade.get_account_by_id(self.account.id)
        if updated_account:
            self.account = updated_account
        self.load_data()

    def on_account_modified(self, result: bool) -> None:
        if result:
            # Refresh account data using facade
            updated_account = self.account_facade.get_account_by_id(self.account.id)
            if updated_account:
                self.account = updated_account
            # Refresh the display
            self.action_refresh()

    def on_transaction_added(self, result: bool) -> None:
        if result:
            self.action_refresh()