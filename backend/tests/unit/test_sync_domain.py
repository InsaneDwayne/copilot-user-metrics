from datetime import date
from decimal import Decimal
from typing import Any

from copilot_metrics.sync.domain import (
    BudgetPage,
    CreditUsageReport,
    UsageSummaryReport,
    UserTeamRecord,
    budget_for_user,
    credits_by_model,
    org_budgets,
    seat_cost,
)

BILLING_RESPONSE = b"""{
  "timePeriod": {"year": 2026, "month": 11, "day": 9},
  "organization": "acme-labs",
  "user": "mlindqvist",
  "usageItems": [
    {"product": "copilot", "sku": "ai_credits", "model": "Claude Sonnet 4.6", "unitType": "credits",
     "pricePerUnit": 0.01, "grossQuantity": 96.8, "grossAmount": 0.968, "discountQuantity": 96.8,
     "discountAmount": 0.968, "netQuantity": 0, "netAmount": 0},
    {"product": "copilot", "sku": "ai_credits_extra", "model": "Claude Sonnet 4.6", "unitType": "credits",
     "pricePerUnit": 0.01, "grossQuantity": 3.2, "grossAmount": 0.032, "discountQuantity": 0,
     "discountAmount": 0, "netQuantity": 3.2, "netAmount": 0.032},
    {"product": "copilot", "sku": "ai_credits", "model": "GPT-5.5", "grossQuantity": 22.1, "grossAmount": 0.221}
  ]
}"""


def test_billing_items_collapse_to_one_row_per_model() -> None:
    items = CreditUsageReport.model_validate_json(BILLING_RESPONSE).usage_items
    rows = {r.model: r for r in credits_by_model(items)}
    assert set(rows) == {"Claude Sonnet 4.6", "GPT-5.5"}
    assert rows["Claude Sonnet 4.6"].gross_qty == Decimal(100)
    assert rows["Claude Sonnet 4.6"].net_usd == Decimal("0.032")  # exact: 1.000 - 0.968, not 0.03200000000000003


def test_user_team_record_accepts_known_team_field_names() -> None:
    a = UserTeamRecord.model_validate({"day": "2026-11-08", "user_id": 1, "user_login": "a", "team_slug": "platform"})
    b = UserTeamRecord.model_validate({"day": "2026-11-08", "user_id": 1, "user_login": "a", "team_name": "platform"})
    assert a.team_slug == b.team_slug == "platform"


def test_user_team_record_reads_githubs_report_line() -> None:
    """The user-teams-1-day report as GitHub documents it: the team is under ``slug``."""
    line = (
        '{"user_id": 1, "user_login": "a", "day": "2026-11-08",'
        ' "organization_id": 9, "team_id": 42, "slug": "platform"}'
    )
    assert UserTeamRecord.model_validate_json(line).team_slug == "platform"


BUDGETS: dict[str, Any] = {
    "budgets": [
        {
            "id": "org",
            "budget_scope": "organization",
            "budget_entity_name": "acme-labs",
            "budget_amount": 500,
            "consumed_amount": 120.5,
            "prevent_further_usage": True,
            "budget_product_sku": "ai_credits",
            "budget_type": "SkuPricing",
        },
        {
            "id": "tara",
            "budget_scope": "user",
            "budget_entity_name": "",
            "user": "tkaur",
            "budget_amount": 80,
            "consumed_amount": 31,
            "prevent_further_usage": True,
            "budget_product_sku": "ai_credits",
        },
        {"id": "actions", "budget_scope": "organization", "budget_amount": 50, "budget_product_sku": "actions"},
    ],
    "has_next_page": False,
    "total_count": 3,
}


def test_org_budgets_keep_copilot_org_scopes_only() -> None:
    records = org_budgets(BudgetPage.model_validate(BUDGETS))
    assert [(r.id, r.amount_usd, r.consumed_usd) for r in records] == [("org", Decimal(500), Decimal("120.5"))]


def test_null_amounts_from_github_read_as_zero_instead_of_failing_the_sync() -> None:
    org = {**BUDGETS["budgets"][0], "consumed_amount": None, "prevent_further_usage": None}
    page = BudgetPage.model_validate(
        {"budgets": [org], "effective_budget": {"id": "org", "budget_amount": 500, "consumed_amount": None}}
    )
    assert org_budgets(page)[0].consumed_usd == 0


def test_personal_budget_wins_over_the_org_budget() -> None:
    page = BudgetPage.model_validate(
        {**BUDGETS, "effective_budget": {"id": "tara", "budget_amount": 80, "consumed_amount": 33}}
    )
    record = budget_for_user("TKaur", page)
    assert record is not None
    assert (record.id, record.scope, record.amount_usd, record.consumed_usd) == (
        "tara",
        "user",
        Decimal(80),
        Decimal(33),
    )


def test_members_without_a_personal_budget_fall_under_the_org_budget() -> None:
    page = BudgetPage.model_validate(
        {**BUDGETS, "effective_budget": {"id": "org", "budget_amount": 500, "consumed_amount": 7}}
    )
    record = budget_for_user("jbrennan", page)
    assert record is not None
    assert (record.id, record.consumed_usd) == ("org", Decimal(7))


def test_no_copilot_budget_means_none() -> None:
    assert budget_for_user("x", BudgetPage.model_validate({"budgets": [BUDGETS["budgets"][2]]})) is None


def test_seat_cost_comes_from_copilot_user_month_items() -> None:
    report = UsageSummaryReport.model_validate(
        {
            "usageItems": [
                {
                    "product": "Copilot",
                    "sku": "Copilot Business",
                    "unitType": "UserMonths",
                    "pricePerUnit": 19,
                    "grossQuantity": 48,
                    "grossAmount": 912,
                    "netAmount": 912,
                },
                {
                    "product": "Copilot",
                    "sku": "ai_credits",
                    "unitType": "credits",
                    "pricePerUnit": 0.01,
                    "grossQuantity": 31850,
                    "grossAmount": 318.5,
                },
                {"product": "Actions", "sku": "actions_linux", "unitType": "Minutes", "grossAmount": 3},
            ]
        }
    )
    cost = seat_cost(report.usage_items, date(2026, 11, 1))
    assert cost is not None
    assert (cost.seats, cost.price_per_seat_usd, cost.net_usd) == (Decimal(48), Decimal(19), Decimal(912))
    assert seat_cost(report.usage_items[1:], date(2026, 11, 1)) is None


def test_catch_up_skips_settled_days_and_goes_newest_first() -> None:
    from datetime import UTC, datetime, timedelta

    from copilot_metrics.sync.domain import days_to_catch_up

    window = [date(2026, 11, d) for d in range(1, 11)]

    def at(day: int, hour: int = 12) -> datetime:
        return datetime(2026, 11, day, hour, tzinfo=UTC)

    synced = {
        date(2026, 11, 2): at(5),  # three days later: settled
        date(2026, 11, 3): at(3, 18),  # same day (worker stopped that evening): fetch again
        date(2026, 11, 4): at(6),  # two days later: one short of settled
        date(2026, 11, 5): at(8),  # settled
    }
    todo = days_to_catch_up(window, synced, settle_days=3)
    assert todo == sorted(set(window) - {date(2026, 11, 2), date(2026, 11, 5)}, reverse=True)
    assert todo[0] == date(2026, 11, 10)
    assert days_to_catch_up([], synced, settle_days=3) == []
    assert days_to_catch_up(window, {d: at(30) + timedelta(days=1) for d in window}, settle_days=3) == []
