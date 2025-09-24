from datetime import date, timedelta
from decimal import Decimal

from dependency_injector.wiring import Provide, inject
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import DataTable, Label, ProgressBar, Static

from budgetpal.application.interfaces import AccountFacadeInterface, TransactionFacadeInterface
from budgetpal.domain.models import Account, TransactionType
from budgetpal.infrastructure.containers import Container as DIContainer


class QuickStats(Static):
    """Display quick financial statistics"""

    @inject
    def __init__(
        self,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
    ):
        super().__init__()
        self.account_facade = account_facade
        self.transaction_facade = transaction_facade

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Container(
                Label("This Month", classes="stat-label"),
                Label("Income: 0.00", id="monthly-income"),
                Label("Expenses: 0.00", id="monthly-expenses"),
                Label("Net: 0.00", id="monthly-net"),
                classes="stat-box",
            )
            yield Container(
                Label("Total Balance", classes="stat-label"),
                Label("0.00 CHF", id="total-balance"),
                classes="stat-box",
            )

    def on_mount(self) -> None:
        self.update_stats()

    def update_stats(self) -> None:
        # Use facades instead of direct repository access
        total_balance = self.account_facade.get_total_balance("CHF")
        self.query_one("#total-balance").update(f"{total_balance:,.2f} CHF")

        # Get monthly stats from transaction facade
        monthly_stats = self.transaction_facade.get_monthly_stats()

        self.query_one("#monthly-income").update(f"Income: {monthly_stats['income']:,.2f}")
        self.query_one("#monthly-expenses").update(f"Expenses: {monthly_stats['expenses']:,.2f}")
        self.query_one("#monthly-net").update(f"Net: {monthly_stats['net']:+,.2f}")


class AccountCard(Static):
    """Display individual account information"""

    def __init__(self, account: Account):
        super().__init__()
        self.account = account

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"{self.account.icon if hasattr(self.account, 'icon') else '💳'} {self.account.name}", classes="account-name")
            yield Label(f"{self.account.account_type.value}", classes="account-type")
            yield Label(f"{self.account.balance:,.2f} {self.account.currency}", classes="account-balance")

            if self.account.goal_amount:
                progress = min(float(self.account.balance / self.account.goal_amount), 1.0)
                yield ProgressBar(total=1.0, show_percentage=True)
                yield Label(f"Goal: {self.account.goal_amount:,.2f}", classes="account-goal")


class AccountsOverview(Static):
    """Display overview of all accounts"""

    @inject
    def __init__(
        self,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__()
        self.account_facade = account_facade

    def compose(self) -> ComposeResult:
        yield Label("Accounts", classes="section-title")
        yield Container(id="accounts-list")

    def on_mount(self) -> None:
        self.update_accounts()

    def update_accounts(self) -> None:
        container = self.query_one("#accounts-list", Container)
        container.remove_children()

        # Use facade instead of direct repository access
        accounts = self.account_facade.get_all_accounts()

        for account in accounts[:5]:  # Show top 5 accounts
            account_info = Horizontal(
                Label(f"{account.name}:", classes="account-item-name"),
                Label(f"{account.balance:,.2f} {account.currency}", classes="account-item-balance"),
                classes="account-item",
            )
            container.mount(account_info)


class RecentTransactions(Static):
    """Display recent transactions"""

    @inject
    def __init__(
        self,
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
    ):
        super().__init__()
        self.transaction_facade = transaction_facade
        self.table = DataTable()

    def compose(self) -> ComposeResult:
        yield Label("Recent Transactions", classes="section-title")
        yield self.table

    def on_mount(self) -> None:
        self.table.add_columns("Date", "Description", "Amount", "Type")
        self.update_transactions()

    def update_transactions(self) -> None:
        self.table.clear()

        # Use facade instead of direct repository access
        recent_transactions = self.transaction_facade.get_recent_transactions(days=30, limit=10)

        for trans in recent_transactions:
            self.table.add_row(
                trans["date"],
                trans["description"],
                trans["amount"],
                trans["type"],
            )