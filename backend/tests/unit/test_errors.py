import pytest

from copilot_metrics.identity.domain import NoSeat, SessionExpired, SignInFailed
from copilot_metrics.shared.adapters.inbound.http.error_handlers import status_for
from copilot_metrics.shared.errors import DomainError
from copilot_metrics.shared.kernel import InvalidPeriod, Period
from copilot_metrics.usage.service import MemberNotFound


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (SessionExpired(), 401),
        (NoSeat(), 403),
        (MemberNotFound(), 404),
        (InvalidPeriod("x"), 422),
        (SignInFailed(), 400),
        (DomainError(), 400),
    ],
)
def test_categories_map_to_status_codes(error: DomainError, status: int) -> None:
    assert status_for(error) == status


def test_period_between_raises_a_domain_error() -> None:
    from datetime import date

    with pytest.raises(InvalidPeriod, match="before its start"):
        Period.between(date(2026, 5, 2), date(2026, 5, 1))
