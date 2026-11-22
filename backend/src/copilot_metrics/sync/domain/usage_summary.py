"""Copilot seat charges from GitHub's monthly billing usage summary."""

from collections.abc import Iterable
from datetime import date

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen
from copilot_metrics.sync.domain.wire import CamelModel


class UsageSummaryItem(CamelModel):
    product: str | None = None
    sku: str | None = None
    unit_type: str | None = None
    price_per_unit: Amount = ZERO
    gross_quantity: Amount = ZERO
    gross_amount: Amount = ZERO
    net_amount: Amount = ZERO


class UsageSummaryReport(CamelModel):
    usage_items: list[UsageSummaryItem] = []


class SeatCostRecord(Frozen):
    month: date
    seats: Amount
    price_per_seat_usd: Amount
    gross_usd: Amount
    net_usd: Amount


def seat_cost(items: Iterable[UsageSummaryItem], month: date) -> SeatCostRecord | None:
    """Copilot seat (license) line items of the monthly usage summary, if GitHub lists them.

    Seats are the Copilot items billed per user (unit type like "UserMonths"), as opposed to
    AI credits. Their quantity is user-months billed so far (seats are billed per day), so
    mid-month it is a fraction of the seat count. Returns None when there are none, rather
    than inventing a price.
    """
    seats = [
        i
        for i in items
        if "copilot" in (i.product or "").lower()
        and "user" in (i.unit_type or "").lower()
        and "credit" not in (i.sku or "").lower()
    ]
    if not seats:
        return None
    return SeatCostRecord(
        month=month,
        seats=sum((i.gross_quantity for i in seats), ZERO),
        price_per_seat_usd=max(i.price_per_unit for i in seats),
        gross_usd=sum((i.gross_amount for i in seats), ZERO),
        net_usd=sum((i.net_amount for i in seats), ZERO),
    )
