"""Reusable form components following composition pattern"""

from decimal import Decimal
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.validation import Number, ValidationResult, Validator
from textual.widgets import Button, Input, Label, Static


class DateValidator(Validator):
    """Validates date in YYYY-MM-DD format"""

    def validate(self, value: str) -> ValidationResult:
        if not value:
            return self.failure("Date is required")

        try:
            from datetime import date
            date.fromisoformat(value)
            return self.success()
        except ValueError:
            return self.failure("Invalid date format (use YYYY-MM-DD)")


class FormField(Static):
    """Base form field component"""

    def __init__(
        self,
        label: str,
        field_id: str,
        required: bool = True,
        help_text: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.label = label
        self.field_id = field_id
        self.required = required
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        label_text = f"{self.label}:" if not self.required else f"{self.label}:*"
        yield Label(label_text, classes="form-label")
        if self.help_text:
            yield Label(self.help_text, classes="form-help")


class TextInput(FormField):
    """Text input field component"""

    def __init__(
        self,
        label: str,
        field_id: str,
        placeholder: str = "",
        initial_value: str = "",
        max_length: Optional[int] = None,
        validators: Optional[list] = None,
        **kwargs
    ):
        super().__init__(label, field_id, **kwargs)
        self.placeholder = placeholder
        self.initial_value = initial_value
        self.max_length = max_length
        self.validators = validators or []

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Input(
            value=self.initial_value,
            placeholder=self.placeholder,
            id=self.field_id,
            validators=self.validators,
            max_length=self.max_length,
        )


class NumberInput(FormField):
    """Number input field component"""

    def __init__(
        self,
        label: str,
        field_id: str,
        placeholder: str = "0.00",
        initial_value: Optional[Decimal] = None,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
        **kwargs
    ):
        super().__init__(label, field_id, **kwargs)
        self.placeholder = placeholder
        self.initial_value = str(initial_value) if initial_value else ""
        self.min_value = min_value
        self.max_value = max_value

    def compose(self) -> ComposeResult:
        yield from super().compose()
        validators = [Number()]
        yield Input(
            value=self.initial_value,
            placeholder=self.placeholder,
            id=self.field_id,
            validators=validators,
        )




class DateInput(FormField):
    """Date input field component"""

    def __init__(
        self,
        label: str,
        field_id: str,
        initial_value: Optional[str] = None,
        **kwargs
    ):
        super().__init__(label, field_id, **kwargs)
        from datetime import date
        self.initial_value = initial_value or date.today().isoformat()

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Input(
            value=self.initial_value,
            placeholder="YYYY-MM-DD",
            id=self.field_id,
            validators=[DateValidator()],
        )


class FormButtons(Static):
    """Reusable form button component"""

    def __init__(
        self,
        save_label: str = "Save",
        cancel_label: str = "Cancel",
        save_id: str = "save-button",
        cancel_id: str = "cancel-button",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.save_label = save_label
        self.cancel_label = cancel_label
        self.save_id = save_id
        self.cancel_id = cancel_id

    def compose(self) -> ComposeResult:
        with Horizontal(id="button-container"):
            yield Button(self.save_label, variant="primary", id=self.save_id)
            yield Button(self.cancel_label, variant="default", id=self.cancel_id)


