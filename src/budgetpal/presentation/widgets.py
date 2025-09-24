from datetime import date, timedelta
from decimal import Decimal

from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import DataTable, Label, ProgressBar, Static

from budgetpal.domain.models import Account, TransactionType
from budgetpal.infrastructure.database import Database
from budgetpal.infrastructure.repositories import AccountRepository, TransactionRepository


class QuickStats(Static):
    """Display quick financial statistics"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

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
        with self.db.get_session() as session:
            acc_repo = AccountRepository(session)
            trans_repo = TransactionRepository(session)

            # Calculate total balance
            accounts = acc_repo.get_active_accounts()
            total_balance = sum(acc.balance for acc in accounts)
            self.query_one("#total-balance").update(f"{total_balance:,.2f} CHF")

            # Calculate monthly stats
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

            self.query_one("#monthly-income").update(f"Income: {income:,.2f}")
            self.query_one("#monthly-expenses").update(f"Expenses: {expenses:,.2f}")
            self.query_one("#monthly-net").update(f"Net: {net:+,.2f}")


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

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def compose(self) -> ComposeResult:
        yield Label("Accounts", classes="section-title")
        yield Container(id="accounts-list")

    def on_mount(self) -> None:
        self.update_accounts()

    def update_accounts(self) -> None:
        container = self.query_one("#accounts-list", Container)
        container.remove_children()

        with self.db.get_session() as session:
            repo = AccountRepository(session)
            accounts = repo.get_active_accounts()

            for account in accounts[:5]:  # Show top 5 accounts
                account_info = Horizontal(
                    Label(f"{account.name}:", classes="account-item-name"),
                    Label(f"{account.balance:,.2f} {account.currency}", classes="account-item-balance"),
                    classes="account-item",
                )
                container.mount(account_info)


class RecentTransactions(Static):
    """Display recent transactions"""

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.table = DataTable()

    def compose(self) -> ComposeResult:
        yield Label("Recent Transactions", classes="section-title")
        yield self.table

    def on_mount(self) -> None:
        self.table.add_columns("Date", "Description", "Amount", "Type")
        self.update_transactions()

    def update_transactions(self) -> None:
        self.table.clear()

        with self.db.get_session() as session:
            repo = TransactionRepository(session)
            today = date.today()
            start_date = today - timedelta(days=30)
            transactions = repo.get_by_date_range(start_date, today)

            # Sort by date descending
            transactions.sort(key=lambda t: t.transaction_date, reverse=True)

            for trans in transactions[:10]:  # Show last 10 transactions
                amount_str = f"{trans.amount:,.2f}"
                if trans.transaction_type == TransactionType.EXPENSE:
                    amount_str = f"-{amount_str}"
                elif trans.transaction_type == TransactionType.INCOME:
                    amount_str = f"+{amount_str}"

                self.table.add_row(
                    trans.transaction_date.strftime("%m/%d"),
                    trans.description[:30],
                    amount_str,
                    trans.transaction_type.value[:3].upper(),
                )