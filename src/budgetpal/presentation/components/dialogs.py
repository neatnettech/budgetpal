"""Reusable dialog components"""

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmationDialog(ModalScreen):
    """Reusable confirmation dialog"""

    CSS = """
    ConfirmationDialog {
        align: center middle;
    }

    #confirmation-container {
        width: 50;
        height: auto;
        min-height: 12;
        border: solid $error;
        background: $surface;
        padding: 2;
    }

    .dialog-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    .dialog-message {
        margin-bottom: 2;
    }

    #button-container {
        align: center middle;
        margin-top: 2;
    }
    """

    def __init__(
        self,
        title: str = "Confirm Action",
        message: str = "Are you sure you want to proceed?",
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        confirm_variant: str = "error",
    ):
        super().__init__()
        self.title = title
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.confirm_variant = confirm_variant

    def compose(self) -> ComposeResult:
        with Container(id="confirmation-container"):
            yield Label(self.title, classes="dialog-title")
            yield Label(self.message, classes="dialog-message")
            with Horizontal(id="button-container"):
                yield Button(
                    self.confirm_label,
                    variant=self.confirm_variant,
                    id="confirm-button"
                )
                yield Button(
                    self.cancel_label,
                    variant="default",
                    id="cancel-button"
                )

    @on(Button.Pressed, "#confirm-button")
    def confirm_action(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-button")
    def cancel_action(self) -> None:
        self.dismiss(False)


class InfoDialog(ModalScreen):
    """Reusable information dialog"""

    CSS = """
    InfoDialog {
        align: center middle;
    }

    #info-container {
        width: 60;
        height: auto;
        min-height: 10;
        border: solid $primary;
        background: $surface;
        padding: 2;
    }

    .info-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .info-message {
        margin-bottom: 2;
    }

    #button-container {
        align: center middle;
        margin-top: 2;
    }
    """

    def __init__(
        self,
        title: str = "Information",
        message: str = "",
        button_label: str = "OK",
    ):
        super().__init__()
        self.title = title
        self.message = message
        self.button_label = button_label

    def compose(self) -> ComposeResult:
        with Container(id="info-container"):
            yield Label(self.title, classes="info-title")
            yield Label(self.message, classes="info-message")
            with Horizontal(id="button-container"):
                yield Button(
                    self.button_label,
                    variant="primary",
                    id="ok-button"
                )

    @on(Button.Pressed, "#ok-button")
    def close_dialog(self) -> None:
        self.dismiss(True)


class ErrorDialog(InfoDialog):
    """Error dialog inheriting from InfoDialog"""

    CSS = """
    ErrorDialog {
        align: center middle;
    }

    #info-container {
        width: 60;
        height: auto;
        min-height: 10;
        border: solid $error;
        background: $surface;
        padding: 2;
    }

    .info-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    .info-message {
        margin-bottom: 2;
        color: $text;
    }

    #button-container {
        align: center middle;
        margin-top: 2;
    }
    """

    def __init__(
        self,
        title: str = "Error",
        message: str = "An error occurred",
        button_label: str = "OK",
    ):
        super().__init__(title, message, button_label)