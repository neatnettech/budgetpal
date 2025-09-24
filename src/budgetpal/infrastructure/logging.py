"""Structured logging configuration for BudgetPal"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.types import Processor


def configure_logging(log_level: str = "INFO", log_file: str = None) -> None:
    """Configure structured logging with both console and file output"""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Define processors for structured logging
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            parameters=[structlog.processors.CallsiteParameter.FUNC_NAME]
        ),
    ]

    # Configure file logging if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # File handler with JSON formatting
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, log_level.upper()))

        # Add file-specific processors
        file_processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

        # Configure file logger
        file_logger = logging.getLogger("budgetpal.file")
        file_logger.addHandler(file_handler)
        file_logger.setLevel(getattr(logging, log_level.upper()))

    # Configure console output
    if sys.stderr.isatty():
        # Pretty console output for development
        console_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        console_processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=console_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger for the given name"""
    return structlog.get_logger(name)


def add_context(**kwargs: Any) -> None:
    """Add context variables to all subsequent log messages"""
    for key, value in kwargs.items():
        structlog.contextvars.bind_contextvars(**{key: value})


def clear_context() -> None:
    """Clear all context variables"""
    structlog.contextvars.clear_contextvars()


class LoggerMixin:
    """Mixin class to add structured logging to any class"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._logger = get_logger(f"{cls.__module__}.{cls.__qualname__}")

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get the logger for this class"""
        return self._logger