"""Account detail view screen"""

from datetime import date, timedelta
from decimal import Decimal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, ProgressBar, Static

from budgetpal.domain.models import Account, TransactionType
from budgetpal.infrastructure.database import Database
from budgetpal.infrastructure.repositories import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
)


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

    #action-buttons {
        margin: 1;
        align: center middle;
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

    def __init__(self, db: Database, account: Account):
        super().__init__()
        self.db = db
        self.account = account
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

            # Action Buttons
            with Horizontal(id="action-buttons"):
                yield Button("Edit Account", variant="primary", id="edit-button")
                yield Button("Add Transaction", variant="success", id="add-trans-button")
                yield Button("Back", variant="default", id="back-button")

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
        """Load recent transactions for this account"""
        self.transactions_table.clear()

        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            cat_repo = CategoryRepository(session)

            # Get all transactions for this account
            all_transactions = trans_repo.get_all()
            account_transactions = [
                t for t in all_transactions
                if t.from_account_id == self.account.id or t.to_account_id == self.account.id
            ]

            # Sort by date descending
            account_transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            running_balance = self.account.balance
            for trans in account_transactions[:50]:  # Show last 50 transactions
                # Get category name
                category_name = "-"
                if trans.category_id:
                    category = cat_repo.get_by_id(trans.category_id)
                    if category:
                        category_name = category.name

                # Determine amount display
                if trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{trans.amount:,.2f}"
                elif trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{trans.amount:,.2f}"
                elif trans.transaction_type == TransactionType.TRANSFER:
                    if trans.from_account_id == self.account.id:
                        amount_str = f"-{trans.amount:,.2f}"
                    else:
                        amount_str = f"+{trans.amount:,.2f}"
                else:
                    amount_str = f"{trans.amount:,.2f}"

                self.transactions_table.add_row(
                    trans.transaction_date.strftime("%Y-%m-%d"),
                    trans.description[:40],
                    category_name,
                    amount_str,
                    trans.transaction_type.value,
                    f"{running_balance:,.2f}",
                )

                # Update running balance (going backwards in time)
                if trans.transaction_type == TransactionType.INCOME:
                    running_balance -= trans.amount
                elif trans.transaction_type == TransactionType.EXPENSE:
                    running_balance += trans.amount
                elif trans.transaction_type == TransactionType.TRANSFER:
                    if trans.from_account_id == self.account.id:
                        running_balance += trans.amount
                    else:
                        running_balance -= trans.amount

    def load_statistics(self) -> None:
        """Calculate and display account statistics"""
        today = date.today()
        start_of_month = date(today.year, today.month, 1)

        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)

            # Get this month's transactions
            month_transactions = trans_repo.get_by_date_range(start_of_month, today)
            account_month_trans = [
                t for t in month_transactions
                if t.from_account_id == self.account.id or t.to_account_id == self.account.id
            ]

            # Calculate monthly income and expenses
            monthly_income = Decimal("0")
            monthly_expenses = Decimal("0")

            for trans in account_month_trans:
                if trans.transaction_type == TransactionType.INCOME:
                    monthly_income += trans.amount
                elif trans.transaction_type == TransactionType.EXPENSE:
                    monthly_expenses += trans.amount
                elif trans.transaction_type == TransactionType.TRANSFER:
                    if trans.to_account_id == self.account.id:
                        monthly_income += trans.amount
                    elif trans.from_account_id == self.account.id:
                        monthly_expenses += trans.amount

            # Calculate 6-month average
            six_months_ago = today - timedelta(days=180)
            six_month_trans = trans_repo.get_by_date_range(six_months_ago, today)
            account_six_month = [
                t for t in six_month_trans
                if t.from_account_id == self.account.id and t.transaction_type == TransactionType.EXPENSE
            ]

            total_six_month = sum(t.amount for t in account_six_month)
            monthly_average = total_six_month / 6 if total_six_month else Decimal("0")

            # Update display
            self.query_one("#monthly-income").update(f"{monthly_income:,.2f}")
            self.query_one("#monthly-expenses").update(f"{monthly_expenses:,.2f}")
            self.query_one("#monthly-average").update(f"{monthly_average:,.2f}")

    @on(Button.Pressed, "#edit-button")
    def edit_account(self) -> None:
        from budgetpal.presentation.modals.account_modals import EditAccountModal
        self.app.push_screen(
            EditAccountModal(self.db, self.account),
            callback=self.on_account_modified
        )

    @on(Button.Pressed, "#add-trans-button")
    def add_transaction(self) -> None:
        from budgetpal.presentation.modals.transaction_modals import AddTransactionModal
        # Pre-select this account in the modal
        self.app.push_screen(
            AddTransactionModal(self.db, preselected_account=self.account.id),
            callback=self.on_transaction_added
        )

    @on(Button.Pressed, "#back-button")
    def handle_back_button(self) -> None:
        self.go_back()

    def action_edit_account(self) -> None:
        self.edit_account()

    def action_add_transaction(self) -> None:
        self.add_transaction()

    def action_back(self) -> None:
        self.go_back()

    def go_back(self) -> None:
        """Return to previous screen and signal refresh needed"""
        self.dismiss(True)

    def action_refresh(self) -> None:
        # Refresh account data
        with self.db.get_session() as session:
            repo = AccountRepository(session)
            self.account = repo.get_by_id(self.account.id)
        self.load_data()

    def on_account_modified(self, result: bool) -> None:
        if result:
            # Refresh account data from database
            with self.db.get_session() as session:
                repo = AccountRepository(session)
                updated_account = repo.get_by_id(self.account.id)
                if updated_account:
                    self.account = updated_account
            # Refresh the display
            self.action_refresh()

    def on_transaction_added(self, result: bool) -> None:
        if result:
            self.action_refresh()