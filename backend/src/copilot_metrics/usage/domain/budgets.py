"""GitHub's spending budgets as last synced."""

from datetime import date, datetime

from copilot_metrics.shared.kernel import Amount, Frozen, Period


class Budget(Frozen):
    """A GitHub spending budget as last synced. Amounts are dollars for the current month."""

    id: str
    scope: str  # "user" for a personal budget, "organization" for the org-wide one, ...
    sku: str
    amount_usd: Amount
    consumed_usd: Amount
    prevent_further_usage: bool  # true: usage stops once the budget is used up
    expires_at: datetime | None = None
    synced_at: datetime


def current_only[T](value: T, period: Period, today: date) -> T | None:
    """Budgets reflect GitHub's current month only; don't pair them with other periods."""
    return value if period.contains(today) else None


class UserBudget(Frozen):
    user_id: int
    budget: Budget
