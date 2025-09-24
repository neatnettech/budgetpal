"""Reusable card components for accounts and other entities"""

from decimal import Decimal

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ProgressBar, Static

from budgetpal.domain.models import Account, AccountType


class AccountCard(Static):
    """Reusable account card component with balance, goal, and styling"""

    DEFAULT_CSS = """
    AccountCard {
        width: 1fr;
        height: 12;
        border: solid $primary;
        background: $surface;
        padding: 1;
        margin: 0;
        content-align: left top;
    }

    AccountCard:hover {
        border: solid $accent;
        background: $panel;
    }

    .card-header {
        layout: horizontal;
        height: 1;
        margin-bottom: 1;
    }

    .account-icon {
        color: $accent;
        text-style: bold;
        width: 3;
    }

    .account-name {
        text-style: bold;
        color: $primary;
        width: 1fr;
    }

    .account-type {
        color: $text-muted;
        text-align: right;
        width: auto;
    }

    .balance-section {
        height: 2;
        margin-bottom: 1;
    }

    .balance-amount {
        text-style: bold;
        color: $success;
        text-align: center;
    }

    .balance-currency {
        color: $text-muted;
        text-align: center;
    }

    .goal-section {
        height: 3;
    }

    .goal-label {
        color: $text-muted;
        margin-bottom: 0;
        text-align: center;
    }

    .goal-amount {
        color: $warning;
        text-align: center;
        margin-bottom: 1;
    }

    ProgressBar {
        margin-bottom: 0;
    }
    """

    # Reactive attribute for selection state
    selected = reactive(False)

    def __init__(self, account: Account, clickable: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.account = account
        self.clickable = clickable
        self.icon = self._get_account_icon(account.account_type)

    def _get_account_icon(self, account_type: AccountType) -> str:
        """Get icon for account type"""
        icons = {
            AccountType.CHECKING: "💳",
            AccountType.SAVINGS: "🏦",
            AccountType.INVESTMENT: "📈",
            AccountType.RETIREMENT: "🏛️",
            AccountType.GOAL: "🎯",
            AccountType.EXPENSE_POOL: "💰",
            AccountType.CREDIT: "💸",
            AccountType.CASH: "💵",
        }
        return icons.get(account_type, "💳")

    def compose(self) -> ComposeResult:
        with Container():
            # Header with icon, name, and type
            with Container(classes="card-header"):
                yield Label(self.icon, classes="account-icon")
                yield Label(self.account.name, classes="account-name")
                yield Label(
                    self.account.account_type.value.replace("_", " ").title(),
                    classes="account-type"
                )

            # Balance section
            with Container(classes="balance-section"):
                yield Label(
                    f"{self.account.balance:,.2f}",
                    classes="balance-amount"
                )
                yield Label(self.account.currency, classes="balance-currency")

            # Goal section (if applicable)
            if self.account.goal_amount:
                with Container(classes="goal-section"):
                    yield Label("Goal", classes="goal-label")
                    yield Label(
                        f"{self.account.goal_amount:,.2f} {self.account.currency}",
                        classes="goal-amount"
                    )

                    # Progress bar
                    progress = min(1.0, float(self.account.balance / self.account.goal_amount))
                    yield ProgressBar(
                        total=1.0,
                        show_percentage=True,
                        id="goal-progress"
                    )

    def on_mount(self) -> None:
        """Update progress bar after mounting"""
        if self.account.goal_amount:
            try:
                progress_bar = self.query_one("#goal-progress", ProgressBar)
                progress = min(1.0, float(self.account.balance / self.account.goal_amount))
                progress_bar.update(progress=progress)
            except:
                pass  # Progress bar might not exist

    def on_click(self, event: Click) -> None:
        """Handle card click events - navigate to account detail"""
        if self.clickable:
            # Post a custom message that parent can handle
            self.post_message(AccountCardClicked(self.account, self))

    def select(self) -> None:
        """Programmatically select this card"""
        self.selected = True
        self.add_class("selected")

    def deselect(self) -> None:
        """Programmatically deselect this card"""
        self.selected = False
        self.remove_class("selected")


class AccountCardClicked(Message):
    """Custom message when account card is clicked"""

    def __init__(self, account: Account, card: AccountCard):
        super().__init__()
        self.account = account
        self.card = card


class AccountGrid(Static):
    """Grid container for account cards with responsive layout"""

    DEFAULT_CSS = """
    AccountGrid {
        layout: grid;
        grid-size: 3;
        grid-gutter: 1;
        grid-rows: auto;
        padding: 1;
        height: auto;
    }

    /* Responsive grid */
    AccountGrid.small {
        grid-size: 1;
    }

    AccountGrid.medium {
        grid-size: 2;
    }

    AccountGrid.large {
        grid-size: 3;
    }

    AccountGrid.xlarge {
        grid-size: 4;
    }
    """

    def __init__(self, accounts: list[Account], **kwargs):
        super().__init__(**kwargs)
        self.accounts = accounts
        self.cards = []

    def compose(self) -> ComposeResult:
        """Create account cards in grid layout"""
        for account in self.accounts:
            card = AccountCard(account)
            self.cards.append(card)
            yield card

    def refresh_accounts(self, accounts: list[Account]) -> None:
        """Update grid with new account data"""
        self.remove_children()
        self.accounts = accounts
        self.cards.clear()

        for account in accounts:
            card = AccountCard(account)
            self.cards.append(card)
            self.mount(card)

    def deselect_all(self) -> None:
        """Deselect all cards"""
        for card in self.cards:
            card.deselect()

    def get_selected_account(self) -> Account | None:
        """Get the currently selected account"""
        for card in self.cards:
            if card.selected:
                return card.account
        return None


class QuickStatsCard(Static):
    """Quick statistics card for the dashboard"""

    DEFAULT_CSS = """
    .stats-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    .stat-row {
        layout: horizontal;
        height: 1;
        margin-bottom: 0;
    }

    .stat-label {
        color: $text-muted;
        width: 1fr;
    }

    .stat-value {
        color: $accent;
        text-style: bold;
        text-align: right;
        width: auto;
    }

    .stat-value.positive {
        color: $success;
    }

    .stat-value.negative {
        color: $error;
    }
    """

    def __init__(self, title: str, stats: dict[str, str], **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.stats = stats

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="stats-title")

        for label, value in self.stats.items():
            with Container(classes="stat-row"):
                yield Label(label, classes="stat-label")
                # Determine value class based on content
                value_class = "stat-value"
                if value.startswith("+"):
                    value_class += " positive"
                elif value.startswith("-"):
                    value_class += " negative"
                yield Label(value, classes=value_class)

    def update_stats(self, stats: dict[str, str]) -> None:
        """Update the statistics displayed"""
        self.stats = stats
        # Remove existing content and rebuild
        self.remove_children()
        for label, value in self.stats.items():
            with Container(classes="stat-row"):
                self.mount(Label(label, classes="stat-label"))
                value_class = "stat-value"
                if value.startswith("+"):
                    value_class += " positive"
                elif value.startswith("-"):
                    value_class += " negative"
                self.mount(Label(value, classes=value_class))