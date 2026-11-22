from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

from copilot_metrics.shared.kernel import Period, Role, Viewer
from copilot_metrics.usage import domain
from copilot_metrics.usage.service import UsageService
from tests.clock import FixedClock

NOW = datetime(2026, 11, 13, 12, tzinfo=UTC)
NOV = Period.cycle_of(date(2026, 11, 13))
ADMIN = Viewer(user_id=3, login="owner", role=Role.ADMIN)


def budget(scope: str) -> domain.Budget:
    return domain.Budget(
        id=scope,
        scope=scope,
        sku="ai_credits",
        amount_usd=500,
        consumed_usd=4,
        prevent_further_usage=True,
        synced_at=NOW,
    )


def service(scope: str) -> UsageService:
    reader = AsyncMock()
    reader.user_credits.return_value = []
    reader.user_budgets.return_value = [domain.UserBudget(user_id=3, budget=budget(scope))]
    return UsageService(reader, FixedClock(NOW), stale_after=timedelta(hours=2))


async def test_own_page_shows_the_org_budget_that_applies() -> None:
    """A person sees the budget GitHub applies to them, even when it is the org-wide one."""
    own = (await service("organization").summary(ADMIN, ADMIN.user_id, NOV)).budget
    assert own is not None
    assert (own.scope, own.amount_usd, own.consumed_usd) == ("organization", Decimal(500), Decimal(4))


async def test_own_page_shows_a_personal_budget() -> None:
    own = (await service("user").summary(ADMIN, ADMIN.user_id, NOV)).budget
    assert own is not None
    assert own.scope == "user"


async def test_admin_drill_down_keeps_the_org_budget() -> None:
    other = (await service("organization").summary(ADMIN, 1, NOV)).budget
    assert other is not None
    assert other.scope == "organization"
