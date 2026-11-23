"""GitHub budgets and the ones stored for the org and for each person."""

from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Any

from pydantic import BeforeValidator

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen
from copilot_metrics.sync.domain.credits import CreditUsageItem


def _null_as(default: Any) -> BeforeValidator:
    return BeforeValidator(lambda v: default if v is None else v)


# GitHub sends optional fields as null as well as leaving them out; either means "none reported".
# Rejecting null would fail the whole budgets sync and leave the stored consumption stale.
GitHubAmount = Annotated[Amount, _null_as(ZERO)]
GitHubFlag = Annotated[bool, _null_as(False)]


class GitHubBudget(Frozen):
    """One budget from GET /organizations/{org}/settings/billing/budgets."""

    id: str
    budget_type: str | None = None
    budget_amount: GitHubAmount = ZERO
    prevent_further_usage: GitHubFlag = False
    budget_scope: str
    budget_entity_name: str | None = None
    user: str | None = None
    # Optional in GitHub's schema, and in practice often left out of the org-wide list: None
    # means "not reported", which must not be mistaken for "nothing spent".
    consumed_amount: Amount | None = None
    budget_product_sku: str | None = None
    expires_at: datetime | None = None

    @property
    def is_copilot(self) -> bool:
        # Budgets GitHub converted from premium requests to AI credits may still come back with
        # the old ``premium_requests`` SKU, although the UI shows them as AI credit budgets.
        sku = (self.budget_product_sku or "").lower()
        return any(part in sku for part in ("ai_credit", "copilot", "premium_request"))

    def applies_only_to(self, login: str) -> bool:
        return self.budget_scope == "user" and (self.user or "").lower() == login.lower()


class EffectiveBudget(Frozen):
    id: str
    budget_amount: GitHubAmount = ZERO
    consumed_amount: GitHubAmount = ZERO


class BudgetPage(Frozen):
    budgets: list[GitHubBudget] = []
    effective_budget: EffectiveBudget | None = None
    has_next_page: GitHubFlag = False


class BudgetRecord(Frozen):
    """A budget as stored: amounts in dollars, consumption for the org or for one person."""

    id: str
    scope: str
    entity_name: str | None
    sku: str
    budget_type: str | None
    amount_usd: Amount
    consumed_usd: Amount
    prevent_further_usage: bool
    expires_at: datetime | None

    @classmethod
    def of(cls, b: GitHubBudget, consumed_usd: Amount | None = None) -> BudgetRecord:
        return cls(
            id=b.id,
            scope=b.budget_scope,
            entity_name=b.budget_entity_name or None,
            sku=b.budget_product_sku or "",
            budget_type=b.budget_type,
            amount_usd=b.budget_amount,
            consumed_usd=(b.consumed_amount or ZERO) if consumed_usd is None else consumed_usd,
            prevent_further_usage=b.prevent_further_usage,
            expires_at=b.expires_at,
        )


def billed_usd(items: Iterable[CreditUsageItem]) -> Amount:
    """What GitHub billed for AI credits beyond the included ones (the net amount)."""
    return sum((i.net_amount for i in items), ZERO)


def org_budgets(page: BudgetPage, org_billed_usd: Amount = ZERO) -> list[BudgetRecord]:
    """Copilot budgets that apply org-wide. Personal budgets are stored per person only.

    An organization budget caps the org's paid AI credit spend: everything billed beyond the
    included credits this month, i.e. ``org_billed_usd``. GitHub's list call often leaves its
    ``consumed_amount`` out (or reports 0), which left the org meter stuck at $0, so the org's
    billed spend is the floor. Other scopes (enterprise, cost center, ...) cover spend outside
    this org's own report, so for them only GitHub's figure is used.
    """
    return [
        BudgetRecord.of(b, max(b.consumed_amount or ZERO, org_billed_usd) if b.budget_scope == "organization" else None)
        for b in page.budgets
        if b.is_copilot and b.budget_scope != "user"
    ]


def budget_for_user(login: str, page: BudgetPage) -> BudgetRecord | None:
    """The Copilot budget GitHub applies to ``login``: a personal one wins over the org-wide one.

    ``page`` must come from the list call filtered with ``?user=login``, so consumed amounts
    (and ``effective_budget``) are that person's.
    """
    copilot = [b for b in page.budgets if b.is_copilot]
    by_id = {b.id: b for b in copilot}
    effective = page.effective_budget
    chosen = (
        next((b for b in copilot if b.applies_only_to(login)), None)
        or (by_id.get(effective.id) if effective else None)
        or next((b for b in copilot if b.budget_scope != "user"), None)
    )
    if chosen is None:
        return None
    consumed = effective.consumed_amount if effective and effective.id == chosen.id else None
    return BudgetRecord.of(chosen, consumed)
