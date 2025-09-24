import click
import os
from pathlib import Path
from rich import print
from rich.console import Console
from rich.table import Table

from budgetpal.application.services import RecurringTransactionService, ReportingService
from budgetpal.infrastructure.database import Database, DatabaseConfig
from budgetpal.infrastructure.logging import configure_logging, get_logger
from budgetpal.presentation.app import BudgetPalApp

console = Console()


@click.group()
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    help="Path to database file",
    default=None,
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Set logging level",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    help="Log file path (optional)",
    default=None,
)
@click.pass_context
def cli(ctx, db_path, log_level, log_file):
    """BudgetPal - A modern CLI budget planner"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path

    # Configure logging
    configure_logging(log_level, str(log_file) if log_file else None)
    logger = get_logger("budgetpal.cli")
    logger.info("BudgetPal CLI started", log_level=log_level, db_path=str(db_path) if db_path else None)


@cli.command()
@click.pass_context
def app(ctx):
    """Launch the interactive TUI application"""
    # Check for debug mode
    if os.environ.get("DEBUGPY") == "1":
        try:
            import debugpy
            port = int(os.environ.get("DEBUGPY_PORT", "5678"))
            debugpy.listen(("localhost", port))
            print(f"🐛 Debug mode enabled - waiting for debugger on port {port}")
            print("   In VSCode: Run & Debug > Attach to Python")
            debugpy.wait_for_client()
            print("✅ Debugger attached!")
        except ImportError:
            print("⚠️  debugpy not installed. Install with: poetry add --group dev debugpy")
        except Exception as e:
            print(f"⚠️  Debug setup failed: {e}")

    # For TUI apps, set up file logging if not already configured
    if not ctx.parent.params.get("log_file"):
        default_log_file = Path.home() / ".budgetpal" / "logs" / "budgetpal.log"
        default_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Reconfigure logging with file output
        configure_logging(
            log_level=ctx.parent.params.get("log_level", "INFO"),
            log_file=str(default_log_file)
        )

        print(f"💡 TUI Mode: Logs are being written to {default_log_file}")
        print(f"   Watch logs: tail -f {default_log_file}")
        print()

    logger = get_logger("budgetpal.cli.app")
    db_path = ctx.obj.get("db_path")

    logger.info("Starting BudgetPal TUI application", db_path=str(db_path) if db_path else None)

    try:
        app = BudgetPalApp(db_path)
        app.run()
        logger.info("BudgetPal application closed successfully")
    except Exception as e:
        logger.error("Application failed to start", error=str(e), exc_info=True)
        raise


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