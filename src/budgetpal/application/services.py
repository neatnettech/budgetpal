from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta
from dependency_injector.wiring import Provide, inject

from budgetpal.application.interfaces import AccountServiceInterface, TransactionServiceInterface
from budgetpal.domain.models import (
    Account,
    Budget,
    RecurrenceFrequency,
    RecurringTransaction,
    Transaction,
    TransactionSummary,
    TransactionType,
)
from budgetpal.infrastructure.database import Database
from budgetpal.infrastructure.logging import LoggerMixin
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


class TransactionService(TransactionServiceInterface, LoggerMixin):
    \"\"\"Service for transaction business logic with proper DI\"\"\"

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        account_repo: AccountRepository,
        category_repo: CategoryRepository,
    ):
        super().__init__()
        self.transaction_repo = transaction_repo
        self.account_repo = account_repo
        self.category_repo = category_repo

    def create_transaction(self, transaction_data: dict) -> bool:
        \"\"\"Create a new transaction and update account balances\"\"\"
        self.logger.info(\"Creating transaction\",
                        amount=transaction_data.get(\"amount\"),
                        description=transaction_data.get(\"description\"),
                        transaction_type=str(transaction_data.get(\"transaction_type\")))

        try:
            # Convert string UUIDs to UUID objects if needed
            from_account_id = transaction_data[\"from_account_id\"]
            if isinstance(from_account_id, str):
                from_account_id = UUID(from_account_id)

            to_account_id = transaction_data.get(\"to_account_id\")
            if to_account_id and isinstance(to_account_id, str):
                to_account_id = UUID(to_account_id)

            category_id = transaction_data.get(\"category_id\")
            if category_id and isinstance(category_id, str):
                category_id = UUID(category_id)

            # Create transaction domain object
            transaction = Transaction(
                amount=Decimal(str(transaction_data[\"amount\"])),
                description=transaction_data[\"description\"],
                transaction_type=transaction_data[\"transaction_type\"],
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                category_id=category_id,
                transaction_date=transaction_data[\"transaction_date\"],
                notes=transaction_data.get(\"notes\"),
            )

            # Coordinate repositories in shared transaction
            with self.transaction_repo.db.get_session() as session:
                # Save transaction using shared session
                self.transaction_repo.add(transaction, session)

                # Update account balances using shared session
                if transaction.transaction_type == TransactionType.EXPENSE:
                    self.account_repo.update_balance(transaction.from_account_id, transaction.amount, \"subtract\", session)
                elif transaction.transaction_type == TransactionType.INCOME:
                    self.account_repo.update_balance(transaction.from_account_id, transaction.amount, \"add\", session)
                elif transaction.transaction_type == TransactionType.TRANSFER:
                    self.account_repo.update_balance(transaction.from_account_id, transaction.amount, \"subtract\", session)
                    if transaction.to_account_id:
                        self.account_repo.update_balance(transaction.to_account_id, transaction.amount, \"add\", session)

                session.commit()

            self.logger.info(\"Transaction created successfully\")
            return True

        except Exception as e:
            self.logger.error(\"Failed to create transaction\",
                            error=str(e),
                            transaction_data=transaction_data,
                            exc_info=True)
            return False

    def get_all_transactions(self, limit: Optional[int] = None) -> List[dict]:
        \"\"\"Get all transactions with enriched data\"\"\"
        self.logger.debug(\"Fetching all transactions\", limit=limit)

        transactions = self.transaction_repo.get_all()
        if limit:
            transactions = transactions[:limit]

        enriched_transactions = []
        for trans in transactions:
            # Get related entities
            from_account = self.account_repo.get_by_id(trans.from_account_id) if trans.from_account_id else None
            to_account = self.account_repo.get_by_id(trans.to_account_id) if trans.to_account_id else None
            category = self.category_repo.get_by_id(trans.category_id) if trans.category_id else None

            enriched_trans = {
                \"id\": str(trans.id),
                \"amount\": trans.amount,
                \"description\": trans.description,
                \"transaction_type\": trans.transaction_type,
                \"from_account_name\": from_account.name if from_account else \"Unknown\",
                \"to_account_name\": to_account.name if to_account else None,
                \"category_name\": category.name if category else None,
                \"transaction_date\": trans.transaction_date,
                \"notes\": trans.notes,
                \"type_enum\": trans.transaction_type,
            }
            enriched_transactions.append(enriched_trans)

        self.logger.info(\"Retrieved enriched transactions\", count=len(enriched_transactions))
        return enriched_transactions

    def get_transactions_by_account(self, account_id: UUID, limit: Optional[int] = None) -> List[dict]:
        \"\"\"Get transactions for a specific account\"\"\"
        # Implementation similar to get_all_transactions but filtered by account
        all_transactions = self.get_all_transactions()
        account_transactions = [
            t for t in all_transactions
            if (str(t.get(\"from_account_id\")) == str(account_id) or
                str(t.get(\"to_account_id\")) == str(account_id))
        ]
        return account_transactions[:limit] if limit else account_transactions

    def get_recent_transactions(self, days: int = 30, limit: int = 10) -> List[dict]:
        \"\"\"Get recent transactions\"\"\"
        today = date.today()
        start_date = today - timedelta(days=days)
        transactions = self.transaction_repo.get_by_date_range(start_date, today)

        # Sort by date descending
        transactions.sort(key=lambda t: t.transaction_date, reverse=True)

        recent_transactions = []
        for trans in transactions[:limit]:
            amount_str = f\"{trans.amount:,.2f}\"
            if trans.transaction_type == TransactionType.EXPENSE:
                amount_str = f\"-{amount_str}\"
            elif trans.transaction_type == TransactionType.INCOME:
                amount_str = f\"+{amount_str}\"

            recent_transactions.append({
                \"date\": trans.transaction_date.strftime(\"%m/%d\"),
                \"description\": trans.description[:30],
                \"amount\": amount_str,
                \"type\": trans.transaction_type.value[:3].upper(),
            })

        return recent_transactions

    def get_monthly_stats(self, year: Optional[int] = None, month: Optional[int] = None) -> dict:
        \"\"\"Get monthly statistics\"\"\"
        if year is None or month is None:
            today = date.today()
            year = today.year
            month = today.month

        start_of_month = date(year, month, 1)
        today = date.today()

        transactions = self.transaction_repo.get_by_date_range(start_of_month, today)

        income = sum(
            t.amount for t in transactions if t.transaction_type == TransactionType.INCOME
        )
        expenses = sum(
            t.amount for t in transactions if t.transaction_type == TransactionType.EXPENSE
        )
        net = income - expenses

        return {
            \"income\": income,
            \"expenses\": expenses,
            \"net\": net,
        }

    def count_transactions_by_account(self, account_id: UUID) -> int:
        \"\"\"Count transactions for an account\"\"\"
        all_trans = self.transaction_repo.get_all()
        return sum(
            1 for t in all_trans
            if t.from_account_id == account_id or t.to_account_id == account_id
        )


class AccountService(AccountServiceInterface, LoggerMixin):
    \"\"\"Service for account business logic with proper DI\"\"\"

    @inject
    def __init__(
        self,
        account_repo: AccountRepository = Provide['account_repository'],
        transaction_repo: TransactionRepository = Provide['transaction_repository'],
    ):
        super().__init__()
        self.account_repo = account_repo
        self.transaction_repo = transaction_repo

    def create_account(self, account_data: dict) -> bool:
        \"\"\"Create a new account\"\"\"
        self.logger.info(\"Creating account\",
                        name=account_data.get(\"name\"),
                        account_type=str(account_data.get(\"account_type\")))

        try:
            account = Account(
                name=account_data[\"name\"],
                account_type=account_data[\"account_type\"],
                balance=account_data[\"balance\"],
                currency=account_data[\"currency\"],
                description=account_data.get(\"description\"),
                goal_amount=account_data.get(\"goal_amount\"),
                goal_date=account_data.get(\"goal_date\"),
            )

            self.account_repo.add(account)
            self.logger.info(\"Account created successfully\")
            return True

        except Exception as e:
            self.logger.error(\"Failed to create account\", error=str(e), exc_info=True)
            return False

    def update_account(self, account_id: UUID, account_data: dict) -> bool:
        \"\"\"Update an existing account\"\"\"
        try:
            account = self.account_repo.get_by_id(account_id)
            if not account:
                return False

            # Update account fields
            account.name = account_data[\"name\"]
            account.account_type = account_data[\"account_type\"]
            account.balance = account_data[\"balance\"]
            account.currency = account_data[\"currency\"]
            account.description = account_data.get(\"description\")
            account.goal_amount = account_data.get(\"goal_amount\")
            account.goal_date = account_data.get(\"goal_date\")

            self.account_repo.update(account)
            self.logger.info(\"Account updated successfully\")
            return True

        except Exception as e:
            self.logger.error(\"Failed to update account\", error=str(e), exc_info=True)
            return False

    def delete_account(self, account_id: UUID) -> bool:
        \"\"\"Delete an account and related transactions\"\"\"
        try:
            # Delete related transactions first
            all_trans = self.transaction_repo.get_all()
            for trans in all_trans:
                if trans.from_account_id == account_id or trans.to_account_id == account_id:
                    self.transaction_repo.delete(trans.id)

            # Delete the account
            self.account_repo.delete(account_id)
            self.logger.info(\"Account and related transactions deleted successfully\")
            return True

        except Exception as e:
            self.logger.error(\"Failed to delete account\", error=str(e), exc_info=True)
            return False

    def get_all_accounts(self) -> List[Account]:
        \"\"\"Get all accounts\"\"\"
        return self.account_repo.get_active_accounts()

    def get_account_by_id(self, account_id: UUID) -> Optional[Account]:
        \"\"\"Get account by ID\"\"\"
        return self.account_repo.get_by_id(account_id)

    def get_total_balance(self, currency: str = \"CHF\") -> Decimal:
        \"\"\"Get total balance\"\"\"
        accounts = self.get_all_accounts()
        return sum(acc.balance for acc in accounts if acc.currency == currency)