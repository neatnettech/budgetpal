import click
from pathlib import Path
from rich import print
from rich.console import Console
from rich.table import Table

from budgetpal.application.services import RecurringTransactionService, ReportingService
from budgetpal.infrastructure.database import Database, DatabaseConfig
from budgetpal.presentation.app import BudgetPalApp

console = Console()


@click.group()
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    help="Path to database file",
    default=None,
)
@click.pass_context
def cli(ctx, db_path):
    """BudgetPal - A modern CLI budget planner"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


@cli.command()
@click.pass_context
def app(ctx):
    """Launch the interactive TUI application"""
    db_path = ctx.obj.get("db_path")
    app = BudgetPalApp(db_path)
    app.run()


@cli.command()
@click.pass_context
def process_recurring(ctx):
    """Process all due recurring transactions"""
    db_path = ctx.obj.get("db_path")
    config = DatabaseConfig(db_path)
    db = Database(config)
    db.create_tables()

    service = RecurringTransactionService(db)
    created = service.process_due_transactions()

    if created:
        console.print(f"[green]✓[/green] Processed {len(created)} recurring transactions")
        for trans in created:
            console.print(f"  - {trans.description}: {trans.amount}")
    else:
        console.print("[yellow]No recurring transactions due[/yellow]")


@cli.command()
@click.option("--year", type=int, help="Year (defaults to current year)")
@click.option("--month", type=int, help="Month (1-12, defaults to current month)")
@click.pass_context
def report(ctx, year, month):
    """Generate monthly financial report"""
    from datetime import date

    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    db_path = ctx.obj.get("db_path")
    config = DatabaseConfig(db_path)
    db = Database(config)
    db.create_tables()

    service = ReportingService(db)
    summary = service.get_monthly_summary(year, month)

    # Create summary table
    table = Table(title=f"Financial Report - {year}/{month:02d}")
    table.add_column("Metric", style="cyan")
    table.add_column("Amount", style="yellow", justify="right")

    table.add_row("Total Income", f"CHF {summary.total_income:,.2f}")
    table.add_row("Total Expenses", f"CHF {summary.total_expenses:,.2f}")
    table.add_row("Net Flow", f"CHF {summary.net_flow:+,.2f}")

    console.print(table)

    # Show category breakdown if available
    if summary.category_breakdown:
        cat_table = Table(title="Expenses by Category")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Amount", style="yellow", justify="right")

        from budgetpal.infrastructure.repositories import CategoryRepository

        with db.get_session() as session:
            cat_repo = CategoryRepository(session)
            for cat_id, amount in summary.category_breakdown.items():
                category = cat_repo.get_by_id(cat_id)
                if category:
                    cat_table.add_row(category.name, f"CHF {amount:,.2f}")

        console.print(cat_table)


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the database with sample data"""
    db_path = ctx.obj.get("db_path")
    config = DatabaseConfig(db_path)
    db = Database(config)
    db.create_tables()

    console.print("[green]✓[/green] Database initialized successfully")
    console.print(f"[dim]Database location: {config.db_url}[/dim]")


if __name__ == "__main__":
    # If no arguments provided, launch the app directly
    import sys
    if len(sys.argv) == 1:
        from budgetpal.presentation.app import BudgetPalApp
        app = BudgetPalApp()
        app.run()
    else:
        cli()