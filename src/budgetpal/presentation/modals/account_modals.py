"""Account CRUD modals using reusable components"""

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from dependency_injector.wiring import Provide, inject

from budgetpal.application.interfaces import AccountFacadeInterface, TransactionFacadeInterface
from budgetpal.domain.models import Account, AccountType
from budgetpal.infrastructure.containers import Container as DIContainer
from budgetpal.infrastructure.logging import get_logger
from budgetpal.presentation.components.dialogs import ConfirmationDialog, ErrorDialog
from budgetpal.presentation.components.forms import (
    DateInput,
    FormButtons,
    NumberInput,
    TextInput,
)


class BaseAccountModal(ModalScreen):
    """Base modal for account operations"""

    CSS = """
    BaseAccountModal {
        align: center middle;
    }

    #modal-container {
        width: 65;
        height: auto;
        max-height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 2;
        overflow-y: auto;
    }

    .modal-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .form-label {
        margin-top: 1;
        margin-bottom: 0;
    }

    .form-help {
        color: $text-muted;
        margin-bottom: 0;
    }

    #button-container {
        margin-top: 2;
        align: center middle;
    }

    Input, Select {
        margin-bottom: 1;
    }
    """

    @inject
    def __init__(
        self,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__()
        self.account_facade = account_facade


class AddAccountModal(BaseAccountModal):
    """Modal for adding new accounts using reusable components"""

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Add New Account", classes="modal-title")

            yield TextInput(
                label="Account Name",
                field_id="account-name",
                placeholder="e.g., Main Checking",
                required=True,
            )

            yield Label("Account Type:", classes="form-label")
            yield Select(
                [(type.value.replace("_", " ").title(), type) for type in AccountType],
                id="account-type",
                allow_blank=False,
            )

            yield NumberInput(
                label="Initial Balance",
                field_id="account-balance",
                placeholder="0.00",
                initial_value=Decimal("0"),
                min_value=Decimal("0"),
                required=False,
            )

            yield TextInput(
                label="Currency",
                field_id="account-currency",
                initial_value="CHF",
                max_length=3,
                required=True,
            )

            yield TextInput(
                label="Description",
                field_id="account-description",
                placeholder="Optional account description",
                required=False,
                help_text="Brief description of the account purpose",
            )

            yield NumberInput(
                label="Goal Amount",
                field_id="account-goal",
                placeholder="0.00",
                required=False,
                help_text="Target amount for savings goals",
            )

            yield DateInput(
                label="Goal Date",
                field_id="account-goal-date",
                required=False,
                help_text="Target date to reach the goal",
            )

            yield FormButtons()

    @on(Button.Pressed, "#save-button")
    async def save_account(self) -> None:
        try:
            # Get values directly from form fields
            name = self.query_one("#account-name", Input).value
            account_type = self.query_one("#account-type", Select).value
            balance = self.query_one("#account-balance", Input).value
            currency = self.query_one("#account-currency", Input).value
            description = self.query_one("#account-description", Input).value
            goal_amount = self.query_one("#account-goal", Input).value
            goal_date = self.query_one("#account-goal-date", Input).value

            # Validate required fields
            if not name or account_type is None:
                await self.app.push_screen(ErrorDialog(message="Name and account type are required"))
                return

            account_data = {
                "name": name,
                "account_type": account_type,
                "balance": Decimal(balance) if balance else Decimal("0"),
                "currency": currency or "CHF",
                "description": description if description else None,
                "goal_amount": Decimal(goal_amount) if goal_amount else None,
                "goal_date": date.fromisoformat(goal_date) if goal_date else None,
            }

            success = self.account_facade.add_account(account_data)
            if success:
                self.dismiss(True)
            else:
                await self.app.push_screen(ErrorDialog(message="Failed to add account"))
        except Exception as e:
            logger = get_logger("budgetpal.modals.account")
            logger.error("Failed to save account", error=str(e), exc_info=True)
            await self.app.push_screen(ErrorDialog(message=str(e)))

    @on(Button.Pressed, "#cancel-button")
    def cancel(self) -> None:
        self.dismiss(False)


class EditAccountModal(BaseAccountModal):
    """Modal for editing existing accounts"""

    @inject
    def __init__(
        self,
        account: Account,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
    ):
        super().__init__(account_facade=account_facade)
        self.account = account

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Edit Account", classes="modal-title")

            # Pre-populate form with existing account data
            yield TextInput(
                label="Account Name",
                field_id="account-name",
                initial_value=self.account.name,
                required=True,
            )

            yield Label("Account Type:", classes="form-label")
            account_type_select = Select(
                [(type.value.replace("_", " ").title(), type) for type in AccountType],
                id="account-type",
                allow_blank=False,
                value=self.account.account_type,
            )
            yield account_type_select

            yield NumberInput(
                label="Current Balance",
                field_id="account-balance",
                initial_value=self.account.balance,
                required=True,
            )

            yield TextInput(
                label="Currency",
                field_id="account-currency",
                initial_value=self.account.currency,
                max_length=3,
                required=True,
            )

            yield TextInput(
                label="Description",
                field_id="account-description",
                initial_value=self.account.description or "",
                required=False,
                help_text="Brief description of the account purpose",
            )

            yield NumberInput(
                label="Goal Amount",
                field_id="account-goal",
                initial_value=self.account.goal_amount,
                required=False,
                help_text="Target amount for savings goals",
            )

            yield DateInput(
                label="Goal Date",
                field_id="account-goal-date",
                initial_value=self.account.goal_date.isoformat() if self.account.goal_date else None,
                required=False,
                help_text="Target date to reach the goal",
            )

            yield FormButtons(save_label="Update")

    @on(Button.Pressed, "#save-button")
    async def update_account(self) -> None:
        try:
            # Get values directly from form fields
            name = self.query_one("#account-name", Input).value
            account_type = self.query_one("#account-type", Select).value
            balance = self.query_one("#account-balance", Input).value
            currency = self.query_one("#account-currency", Input).value
            description = self.query_one("#account-description", Input).value
            goal_amount = self.query_one("#account-goal", Input).value
            goal_date = self.query_one("#account-goal-date", Input).value

            # Validate required fields
            if not name or account_type is None:
                await self.app.push_screen(ErrorDialog(message="Name and account type are required"))
                return

            # Prepare updated account data
            updated_data = {
                "name": name,
                "account_type": account_type,
                "balance": Decimal(balance) if balance else Decimal("0"),
                "currency": currency or "CHF",
                "description": description if description else None,
                "goal_amount": Decimal(goal_amount) if goal_amount else None,
                "goal_date": date.fromisoformat(goal_date) if goal_date else None,
            }

            success = self.account_facade.update_account(self.account.id, updated_data)
            if success:
                # Update local account object for consistency
                self.account.name = name
                self.account.account_type = account_type
                self.account.balance = Decimal(balance) if balance else Decimal("0")
                self.account.currency = currency or "CHF"
                self.account.description = description if description else None
                self.account.goal_amount = Decimal(goal_amount) if goal_amount else None
                self.account.goal_date = date.fromisoformat(goal_date) if goal_date else None
                self.dismiss(True)
            else:
                await self.app.push_screen(ErrorDialog(message="Failed to update account"))
        except Exception as e:
            logger = get_logger("budgetpal.modals.account")
            logger.error("Failed to update account", error=str(e), exc_info=True)
            # More detailed error message for debugging
            error_msg = f"Failed to update account: {str(e)}"
            if "sqlite3.ProgrammingError" in str(type(e)):
                error_msg = f"Database error: Check date format or field values. {str(e)}"
            await self.app.push_screen(ErrorDialog(message=error_msg))

    @on(Button.Pressed, "#cancel-button")
    def cancel(self) -> None:
        self.dismiss(False)


class DeleteAccountModal(ModalScreen):
    """Modal for deleting accounts with transaction handling"""

    CSS = """
    DeleteAccountModal {
        align: center middle;
    }

    #delete-container {
        width: 60;
        height: auto;
        border: solid $error;
        background: $surface;
        padding: 2;
    }

    .warning-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    .warning-message {
        margin-bottom: 1;
    }

    .account-info {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    #button-container {
        margin-top: 2;
        align: center middle;
    }
    """

    @inject
    def __init__(
        self,
        account: Account,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
    ):
        super().__init__()
        self.account_facade = account_facade
        self.transaction_facade = transaction_facade
        self.account = account
        self.transaction_count = 0

    def compose(self) -> ComposeResult:
        with Container(id="delete-container"):
            yield Label("Delete Account", classes="warning-title")

            # Show account details
            with Container(classes="account-info"):
                yield Label(f"Account: {self.account.name}")
                yield Label(f"Type: {self.account.account_type.value}")
                yield Label(f"Balance: {self.account.balance:,.2f} {self.account.currency}")
                yield Label(f"Transactions: {self.transaction_count}", id="transaction-count")

            yield Label(
                "Warning: This action cannot be undone. All transactions associated with this account will also be deleted.",
                classes="warning-message"
            )

            yield FormButtons(save_label="Delete", cancel_label="Cancel")

    def on_mount(self) -> None:
        # Count related transactions using facade
        self.transaction_count = self.transaction_facade.count_transactions_by_account(self.account.id)
        self.query_one("#transaction-count").update(f"Transactions: {self.transaction_count}")

    @on(Button.Pressed, "#save-button")
    async def confirm_delete(self) -> None:
        # Show confirmation dialog
        result = await self.app.push_screen(
            ConfirmationDialog(
                title="Confirm Deletion",
                message=f"Are you sure you want to delete account '{self.account.name}' and all {self.transaction_count} related transactions?",
                confirm_label="Delete",
                cancel_label="Cancel",
            )
        )

        if result:
            try:
                # Use facade to delete account and related transactions
                success = self.account_facade.delete_account(self.account.id)
                if success:
                    self.dismiss(True)
                else:
                    await self.app.push_screen(ErrorDialog(message="Failed to delete account"))
            except Exception as e:
                logger = get_logger("budgetpal.modals.account")
                logger.error("Failed to delete account", error=str(e), exc_info=True)
                await self.app.push_screen(ErrorDialog(message=f"Failed to delete account: {str(e)}"))

    @on(Button.Pressed, "#cancel-button")
    def cancel(self) -> None:
        self.dismiss(False)