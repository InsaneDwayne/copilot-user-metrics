"""One person's usage summary."""

from collections.abc import Iterable, Sequence
from datetime import date

from copilot_metrics.shared.kernel import Amount, Frozen, Period
from copilot_metrics.usage.domain.budgets import Budget, current_only
from copilot_metrics.usage.domain.credits import CreditRow, CreditTotals, DailyCredits, Projection, daily_series


class UsageSummary(Frozen):
    period: Period
    totals: CreditTotals
    projection: Projection | None
    daily: list[DailyCredits]
    budget: Budget | None  # the budget GitHub applies to this person (personal, else org-wide), their consumption


class DailyModelUsage(Frozen):
    day: date
    model: str
    credits: Amount
    gross_usd: Amount
    included_usd: Amount
    billed_usd: Amount


def summarize(rows: Sequence[CreditRow], period: Period, today: date, budget: Budget | None) -> UsageSummary:
    totals = CreditTotals.of(rows)
    return UsageSummary(
        period=period,
        totals=totals,
        projection=Projection.of(totals, period, today),
        daily=daily_series(rows, period, today),
        budget=current_only(budget, period, today),
    )


def daily_line_items(rows: Iterable[CreditRow]) -> list[DailyModelUsage]:
    items = [DailyModelUsage.model_validate(r.model_dump()) for r in rows]
    return sorted(items, key=lambda i: (i.day, i.credits), reverse=True)
