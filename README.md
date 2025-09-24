# BudgetPal

A modern, efficient CLI budget planner with a beautiful terminal UI built with Python, Textual, and SQLAlchemy.

## Features

- **Multiple Account Management**: Track checking, savings, investment, retirement accounts (like Pillar 3a), and goal-based savings
- **Transaction Tracking**: Record income, expenses, and transfers between accounts
- **Recurring Transactions**: Automate regular expenses and income
- **Budget Management**: Set and track budgets by category with alerts
- **Beautiful TUI**: Interactive terminal interface with dashboard, charts, and tables
- **Reports**: Generate monthly financial summaries and category trends
- **Clean Architecture**: Domain-driven design with repository pattern
- **Type Safety**: Full Pydantic validation and type hints

## Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
cd budgetpal

# Install dependencies with Poetry
poetry install

# Run the app
poetry run budgetpal app
```

### Using pip

```bash
# Clone the repository
cd budgetpal

# Install in development mode
pip install -e ".[dev]"
```

## Usage

### Launch the Interactive TUI

```bash
# With Poetry
poetry run budgetpal app

# Or if installed globally
budgetpal app
```

Navigate with keyboard shortcuts:
- `d` - Dashboard
- `a` - Accounts
- `t` - Transactions
- `q` - Quit

### CLI Commands

```bash
# Initialize database
poetry run budgetpal init

# Process recurring transactions
poetry run budgetpal process-recurring

# Generate monthly report
poetry run budgetpal report --year 2024 --month 1

# Use custom database location
poetry run budgetpal --db-path /path/to/db.sqlite app
```

## Architecture

```
budgetpal/
├── domain/          # Business logic and models (Pydantic)
├── infrastructure/  # Database, entities, repositories (SQLAlchemy)
├── application/     # Services and use cases
└── presentation/    # TUI components (Textual)
```

## Account Types

- **Checking**: Daily transaction accounts
- **Savings**: Emergency funds and short-term savings
- **Investment**: Stock portfolios, ETFs
- **Retirement**: Pillar 3a, pension accounts
- **Goal**: Saving for specific purposes (car, vacation)
- **Expense Pool**: Pre-allocated funds for future expenses
- **Credit**: Credit cards
- **Cash**: Physical cash tracking

## Development

```bash
# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/

# Type check
mypy src/
```

## Database

SQLite database is stored at `~/.budgetpal/budgetpal.db` by default.