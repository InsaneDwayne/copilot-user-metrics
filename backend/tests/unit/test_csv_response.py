from datetime import UTC, date, datetime
from decimal import Decimal

from copilot_metrics.shared.adapters.inbound.http.csv_response import csv_response, to_csv
from copilot_metrics.shared.kernel import Frozen


class Row(Frozen):
    login: str
    team: str
    n: float
    when: date | datetime
    none: bool | None


def test_csv_quotes_and_defuses_formulas() -> None:
    text = to_csv(
        Row,
        [
            Row(login="=cmd|' /C calc'!A0", team="+team, a", n=-3, when=date(2026, 11, 2), none=None),
            Row(login="@bob", team='say "hi"', n=1.5, when=datetime(2026, 11, 2, 8, tzinfo=UTC), none=True),
        ],
    )
    assert text.splitlines() == [
        "login,team,n,when,none",
        "'=cmd|' /C calc'!A0,\"'+team, a\",-3.0,2026-11-02,",
        '\'@bob,"say ""hi""",1.5,2026-11-02T08:00:00+00:00,true',
    ]


class Money(Frozen):
    usd: Decimal


def test_csv_writes_exact_amounts_without_trailing_zeros() -> None:
    rows = [Money(usd=Decimal("12.5000")), Money(usd=Decimal("-0.0400")), Money(usd=Decimal("100.0000"))]
    assert to_csv(Money, rows).splitlines() == ["usd", "12.5", "-0.04", "100"]


def test_csv_response_is_a_download_with_a_header_when_empty() -> None:
    response = csv_response("seats.csv", Row, [])
    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="seats.csv"'
    assert bytes(response.body).decode() == "login,team,n,when,none\n"
