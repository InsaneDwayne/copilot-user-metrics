"""AI credits: GitHub's usage items and the per-model rows stored from them."""

from collections import defaultdict
from collections.abc import Iterable

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen
from copilot_metrics.sync.domain.wire import CamelModel


class CreditUsageItem(CamelModel):
    product: str | None = None
    sku: str | None = None
    model: str | None = None
    unit_type: str | None = None
    price_per_unit: Amount = ZERO
    gross_quantity: Amount = ZERO
    gross_amount: Amount = ZERO
    discount_quantity: Amount = ZERO
    discount_amount: Amount = ZERO
    net_quantity: Amount = ZERO
    net_amount: Amount = ZERO


class CreditUsageReport(CamelModel):
    usage_items: list[CreditUsageItem] = []


class ModelCredits(Frozen):
    """One stored row: a day's AI credits for one model."""

    model: str
    sku: str | None
    gross_qty: Amount
    gross_usd: Amount
    discount_usd: Amount
    net_qty: Amount
    net_usd: Amount


UNKNOWN_MODEL = "Unknown model"


def billed_usd(items: Iterable[CreditUsageItem]) -> Amount:
    """What GitHub billed for AI credits beyond the included ones (the net amount)."""
    return sum((i.net_amount for i in items), ZERO)


def credits_by_model(items: Iterable[CreditUsageItem]) -> list[ModelCredits]:
    """GitHub may return several items per model (e.g. per SKU); store one row per model."""
    groups: defaultdict[str, list[CreditUsageItem]] = defaultdict(list)
    for item in items:
        groups[item.model or UNKNOWN_MODEL].append(item)
    return [
        ModelCredits(
            model=model,
            sku=group[0].sku,
            gross_qty=sum((i.gross_quantity for i in group), ZERO),
            gross_usd=sum((i.gross_amount for i in group), ZERO),
            discount_usd=sum((i.discount_amount for i in group), ZERO),
            net_qty=sum((i.net_quantity for i in group), ZERO),
            net_usd=sum((i.net_amount for i in group), ZERO),
        )
        for model, group in groups.items()
    ]
