"""Transaction CRUD modals using reusable components"""

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

from budgetpal.application.interfaces import AccountFacadeInterface, CategoryFacadeInterface, TransactionFacadeInterface
from budgetpal.domain.models import Transaction, TransactionType
from budgetpal.infrastructure.containers import Container as DIContainer
from budgetpal.infrastructure.logging import get_logger
from budgetpal.presentation.components.dialogs import ErrorDialog
from budgetpal.presentation.components.forms import (
    DateInput,
    FormButtons,
    NumberInput,
    TextInput,
)


class AddTransactionModal(ModalScreen):
    """Reusable modal for adding transactions with pre-selection support"""

    CSS = """
    AddTransactionModal {
        align: center middle;
    }

    #modal-container {
        width: 70;
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
        text-align: center;
    }

    .form-label {
        color: $text;
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

    .disabled {
        opacity: 0.5;
    }
    """

    @inject
    def __init__(
        self,
        preselected_account: UUID,
        account_facade: AccountFacadeInterface = Provide[DIContainer.account_facade],
        category_facade: CategoryFacadeInterface = Provide[DIContainer.category_facade],
        transaction_facade: TransactionFacadeInterface = Provide[DIContainer.transaction_facade],
    ):
        super().__init__()
        self.account_facade = account_facade
        self.category_facade = category_facade
        self.transaction_facade = transaction_facade
        self.preselected_account = preselected_account
        self.accounts = []
        self.categories = []

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Add New Transaction", classes="modal-title")

            # Transaction Type
            yield Label("Transaction Type:", classes="form-label")
            yield Select(
                [(type.value.title(), type) for type in TransactionType],
                id="transaction-type",
                allow_blank=False,
            )

            # Amount
            yield NumberInput(
                label="Amount",
                field_id="amount",
                placeholder="0.00",
                required=True,
            )

            # Description
            yield TextInput(
                label="Description",
                field_id="description",
                placeholder="Transaction description",
                required=True,
            )

            # To Account (only for transfers)
            yield Label("To Account (for transfers):", classes="form-label")
            yield Select([("None", None)], id="to-account", allow_blank=True)

            # Category
            yield Label("Category:", classes="form-label")
            yield Select([("Loading...", None)], id="category", allow_blank=True)

            # Date
            yield DateInput(
                label="Transaction Date",
                field_id="transaction-date",
                initial_value=date.today().isoformat(),
                required=True,
            )

            # Notes
            yield TextInput(
                label="Notes",
                field_id="notes",
                placeholder="Additional notes (optional)",
                required=False,
                help_text="Optional additional information",
            )

            yield FormButtons()

    def on_mount(self) -> None:
        """Load accounts and categories, set up form"""
        self.load_data()
        self.setup_form()

    def load_data(self) -> None:
        """Load accounts and categories using facades"""
        self.accounts = self.account_facade.get_all_accounts()
        self.categories = self.category_facade.get_all_categories()

    def setup_form(self) -> None:
        """Setup form dropdowns with data"""
        # Setup to-account for transfers (exclude the current account)
        to_account_select = self.query_one("#to-account", Select)
        other_accounts = [acc for acc in self.accounts if acc.id != self.preselected_account]
        to_account_options = [("None", None)] + [(acc.name, acc.id) for acc in other_accounts]
        to_account_select.set_options(to_account_options)

        # Setup categories
        category_select = self.query_one("#category", Select)

        if self.categories:
            # Default to expense categories initially
            expense_categories = [(cat.name, cat.id) for cat in self.categories if not cat.is_income]
            if expense_categories:
                category_select.set_options(expense_categories)
            else:
                category_select.set_options([("No expense categories", None)])
        else:
            category_select.set_options([("No categories available", None)])

        # Set initial transaction type
        trans_type_select = self.query_one("#transaction-type", Select)
        trans_type_select.value = TransactionType.EXPENSE

        # Setup initial field states
        self.update_form_for_transaction_type(TransactionType.EXPENSE)

    @on(Select.Changed, "#transaction-type")
    def on_transaction_type_changed(self, event: Select.Changed) -> None:
        """Update form based on transaction type"""
        if event.value:
            self.update_form_for_transaction_type(event.value)

    def update_form_for_transaction_type(self, transaction_type: TransactionType) -> None:
        """Update form fields based on transaction type"""
        to_account_select = self.query_one("#to-account", Select)
        category_select = self.query_one("#category", Select)

        if transaction_type == TransactionType.TRANSFER:
            # For transfers: enable to-account, disable category
            to_account_select.disabled = False
            to_account_select.remove_class("disabled")
            category_select.disabled = True
            category_select.add_class("disabled")
            category_select.clear()
        else:
            # For income/expense: disable to-account, enable category
            to_account_select.disabled = True
            to_account_select.add_class("disabled")
            to_account_select.clear()
            category_select.disabled = False
            category_select.remove_class("disabled")

            # Update category options based on type
            if transaction_type == TransactionType.INCOME:
                income_categories = [(cat.name, cat.id) for cat in self.categories if cat.is_income]
                category_select.set_options(income_categories)
            else:  # EXPENSE
                expense_categories = [(cat.name, cat.id) for cat in self.categories if not cat.is_income]
                category_select.set_options(expense_categories)

    @on(Button.Pressed, "#save-button")
    async def save_transaction(self) -> None:
        try:
            # Get form values
            trans_type = self.query_one("#transaction-type", Select).value
            amount = self.query_one("#amount", Input).value
            description = self.query_one("#description", Input).value
            to_account_id = self.query_one("#to-account", Select).value
            category_id = self.query_one("#category", Select).value
            trans_date = self.query_one("#transaction-date", Input).value
            notes = self.query_one("#notes", Input).value

            # Use the preselected account as the "from" account
            from_account_id = self.preselected_account

            # Validate required fields
            if not all([trans_type, amount, description, trans_date]):
                await self.app.push_screen(ErrorDialog(message="Please fill in all required fields"))
                return

            # Validate transfer specific requirements
            if trans_type == TransactionType.TRANSFER and not to_account_id:
                await self.app.push_screen(ErrorDialog(message="Transfer transactions require a destination account"))
                return

            # Validate category for non-transfer transactions
            if trans_type != TransactionType.TRANSFER and not category_id:
                await self.app.push_screen(ErrorDialog(message="Income and expense transactions require a category"))
                return

            # Prepare transaction data for facade

            transaction_data = {
                "amount": amount,
                "description": description,
                "transaction_type": trans_type,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "category_id": category_id,
                "transaction_date": date.fromisoformat(trans_date),
                "notes": notes if notes else None,
            }

            # Use facade to save transaction
            success = self.transaction_facade.add_transaction(transaction_data)
            if success:
                self.dismiss(True)
            else:
                await self.app.push_screen(ErrorDialog(message="Failed to add transaction"))

        except Exception as e:
            logger = get_logger("budgetpal.modals.transaction")
            logger.error("Failed to add transaction", error=str(e), exc_info=True)
            error_msg = f"Failed to add transaction: {str(e)}"
            await self.app.push_screen(ErrorDialog(message=error_msg))

    @on(Button.Pressed, "#cancel-button")
    def cancel(self) -> None:
        self.dismiss(False)