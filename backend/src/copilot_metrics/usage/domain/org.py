"""Org-wide totals and seat charges."""

from collections.abc import Sequence
from datetime import date, datetime

from copilot_metrics.shared.kernel import Amount, Frozen, Period
from copilot_metrics.usage.domain.budgets import Budget, current_only
from copilot_metrics.usage.domain.credits import CreditRow, CreditTotals, DailyCredits, Projection, daily_series


class SeatSummary(Frozen):
    total: int
    active_this_cycle: int
    inactive_this_cycle: int
    pending_cancellation: int
    synced_at: datetime


class SeatCost(Frozen):
    """Copilot seat charges for one month, from GitHub's billing usage summary."""

    month: date
    # User-months GitHub billed so far, not a head count: seats are billed per day, so during
    # a month this grows from 0 to about the number of seats.
    seats: Amount
    price_per_seat_usd: Amount
    gross_usd: Amount
    net_usd: Amount


class OrgSummary(Frozen):
    """Org-wide totals (seat holders see these; never per person)."""

    period: Period
    seats: int
    active_seats: int
    totals: CreditTotals
    projection: Projection | None
    daily: list[DailyCredits]
    budgets: list[Budget]  # org-level Copilot budgets; current month, org owners only
    seat_cost: SeatCost | None  # only when the period is one billing cycle


def org_summary(
    rows: Sequence[CreditRow],
    period: Period,
    today: date,
    seats: SeatSummary | None,
    budgets: Sequence[Budget],
    seat_cost: SeatCost | None,
) -> OrgSummary:
    totals = CreditTotals.of(rows)
    is_cycle = period == Period.cycle_of(period.start)
    return OrgSummary(
        period=period,
        seats=seats.total if seats else 0,
        active_seats=seats.active_this_cycle if seats else 0,
        totals=totals,
        projection=Projection.of(totals, period, today),
        daily=daily_series(rows, period, today),
        budgets=list(current_only(budgets, period, today) or []),
        seat_cost=seat_cost if is_cycle else None,
    )
