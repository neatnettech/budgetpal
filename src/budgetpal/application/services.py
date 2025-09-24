from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta

from budgetpal.domain.models import (
    Budget,
    RecurrenceFrequency,
    RecurringTransaction,
    Transaction,
    TransactionSummary,
    TransactionType,
)
from budgetpal.infrastructure.database import Database
from budgetpal.infrastructure.repositories import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    RecurringTransactionRepository,
    TransactionRepository,
)


class RecurringTransactionService:
    """Service to handle recurring transactions"""

    def __init__(self, db: Database):
        self.db = db

    def process_due_transactions(self, as_of_date: Optional[date] = None) -> list[Transaction]:
        """Process all due recurring transactions and create actual transactions"""
        if as_of_date is None:
            as_of_date = date.today()

        created_transactions = []

        with self.db.get_session() as session:
            recurring_repo = RecurringTransactionRepository(session)
            trans_repo = TransactionRepository(session)
            acc_repo = AccountRepository(session)

            due_transactions = recurring_repo.get_due_transactions(as_of_date)

            for recurring in due_transactions:
                # Create transaction from recurring template
                transaction = Transaction(
                    amount=recurring.amount,
                    description=f"{recurring.description} (Recurring)",
                    category_id=recurring.category_id,
                    transaction_type=recurring.transaction_type,
                    from_account_id=recurring.from_account_id,
                    to_account_id=recurring.to_account_id,
                    transaction_date=recurring.next_date,
                    is_planned=not recurring.auto_confirm,
                    is_cleared=recurring.auto_confirm,
                )

                # Add transaction
                created_transaction = trans_repo.add(transaction)
                created_transactions.append(created_transaction)

                # Update account balances if auto-confirmed
                if recurring.auto_confirm:
                    if recurring.transaction_type == TransactionType.EXPENSE:
                        acc_repo.update_balance(recurring.from_account_id, recurring.amount, "subtract")
                    elif recurring.transaction_type == TransactionType.INCOME:
                        acc_repo.update_balance(recurring.from_account_id, recurring.amount, "add")
                    elif recurring.transaction_type == TransactionType.TRANSFER and recurring.to_account_id:
                        acc_repo.update_balance(recurring.from_account_id, recurring.amount, "subtract")
                        acc_repo.update_balance(recurring.to_account_id, recurring.amount, "add")

                # Calculate next occurrence date
                next_date = self._calculate_next_date(recurring.next_date, recurring.frequency)

                # Update recurring transaction with new next_date
                # Check if it should still be active
                if recurring.end_date and next_date > recurring.end_date:
                    recurring.is_active = False
                else:
                    recurring.next_date = next_date

                recurring_repo.update(recurring)

            session.commit()

        return created_transactions

    def _calculate_next_date(self, current_date: date, frequency: RecurrenceFrequency) -> date:
        """Calculate the next occurrence date based on frequency"""
        if frequency == RecurrenceFrequency.DAILY:
            return current_date + timedelta(days=1)
        elif frequency == RecurrenceFrequency.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif frequency == RecurrenceFrequency.BIWEEKLY:
            return current_date + timedelta(weeks=2)
        elif frequency == RecurrenceFrequency.MONTHLY:
            return current_date + relativedelta(months=1)
        elif frequency == RecurrenceFrequency.QUARTERLY:
            return current_date + relativedelta(months=3)
        elif frequency == RecurrenceFrequency.YEARLY:
            return current_date + relativedelta(years=1)
        else:
            return current_date + timedelta(days=1)


class BudgetService:
    """Service to handle budget tracking and analysis"""

    def __init__(self, db: Database):
        self.db = db

    def get_budget_status(self, budget_id: UUID) -> dict:
        """Get current status of a budget including spending"""
        with self.db.get_session() as session:
            budget_repo = BudgetRepository(session)
            trans_repo = TransactionRepository(session)

            budget = budget_repo.get_by_id(budget_id)
            if not budget:
                raise ValueError(f"Budget {budget_id} not found")

            # Get all expenses in budget period for budget categories
            transactions = trans_repo.get_by_date_range(budget.period_start, budget.period_end)

            total_spent = Decimal("0")
            category_spending = {}

            for trans in transactions:
                if (
                    trans.transaction_type == TransactionType.EXPENSE
                    and trans.category_id
                    and trans.category_id in budget.category_ids
                ):
                    total_spent += trans.amount
                    if trans.category_id not in category_spending:
                        category_spending[trans.category_id] = Decimal("0")
                    category_spending[trans.category_id] += trans.amount

            remaining = budget.amount - total_spent
            percentage_used = float(total_spent / budget.amount * 100) if budget.amount > 0 else 0

            return {
                "budget": budget,
                "total_spent": total_spent,
                "remaining": remaining,
                "percentage_used": percentage_used,
                "category_spending": category_spending,
            }

    def check_budget_alerts(self) -> list[dict]:
        """Check all active budgets and return alerts for those over threshold"""
        alerts = []
        threshold_percentage = 80  # Alert when 80% of budget is used

        with self.db.get_session() as session:
            budget_repo = BudgetRepository(session)
            active_budgets = budget_repo.get_active_budgets(date.today())

            for budget in active_budgets:
                status = self.get_budget_status(budget.id)
                if status["percentage_used"] >= threshold_percentage:
                    alerts.append({
                        "budget": budget,
                        "percentage_used": status["percentage_used"],
                        "remaining": status["remaining"],
                        "message": f"Budget '{budget.name}' is {status['percentage_used']:.1f}% used",
                    })

        return alerts


class ReportingService:
    """Service for generating financial reports"""

    def __init__(self, db: Database):
        self.db = db

    def get_monthly_summary(self, year: int, month: int) -> TransactionSummary:
        """Get summary statistics for a specific month"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        return self.get_period_summary(start_date, end_date)

    def get_period_summary(self, start_date: date, end_date: date) -> TransactionSummary:
        """Get summary statistics for a date range"""
        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)
            acc_repo = AccountRepository(session)

            transactions = trans_repo.get_by_date_range(start_date, end_date)

            total_income = Decimal("0")
            total_expenses = Decimal("0")
            total_transfers = Decimal("0")
            category_breakdown = {}

            for trans in transactions:
                if trans.transaction_type == TransactionType.INCOME:
                    total_income += trans.amount
                elif trans.transaction_type == TransactionType.EXPENSE:
                    total_expenses += trans.amount
                elif trans.transaction_type == TransactionType.TRANSFER:
                    total_transfers += trans.amount

                if trans.category_id:
                    if trans.category_id not in category_breakdown:
                        category_breakdown[trans.category_id] = Decimal("0")
                    if trans.transaction_type == TransactionType.EXPENSE:
                        category_breakdown[trans.category_id] += trans.amount

            # Get current account balances
            accounts = acc_repo.get_active_accounts()
            account_balances = {acc.id: acc.balance for acc in accounts}

            return TransactionSummary(
                period_start=start_date,
                period_end=end_date,
                total_income=total_income,
                total_expenses=total_expenses,
                total_transfers=total_transfers,
                net_flow=total_income - total_expenses,
                category_breakdown=category_breakdown,
                account_balances=account_balances,
            )

    def get_category_trends(self, category_id: UUID, months: int = 6) -> list[dict]:
        """Get spending trends for a category over the last N months"""
        trends = []
        today = date.today()

        with self.db.get_session() as session:
            trans_repo = TransactionRepository(session)

            for i in range(months):
                # Calculate month boundaries
                month_date = today - relativedelta(months=i)
                start_date = date(month_date.year, month_date.month, 1)
                if month_date.month == 12:
                    end_date = date(month_date.year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(month_date.year, month_date.month + 1, 1) - timedelta(days=1)

                # Get transactions for this category in this month
                all_transactions = trans_repo.get_by_date_range(start_date, end_date)
                category_transactions = [
                    t for t in all_transactions
                    if t.category_id == category_id and t.transaction_type == TransactionType.EXPENSE
                ]

                total = sum(t.amount for t in category_transactions)
                trends.append({
                    "month": month_date.strftime("%Y-%m"),
                    "total": total,
                    "transaction_count": len(category_transactions),
                })

        trends.reverse()  # Return in chronological order
        return trends