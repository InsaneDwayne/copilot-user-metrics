"""Seed data shared by the integration tests: Alice and Bob hold seats, the owner does not."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresSyncStore
from copilot_metrics.sync.domain import (
    BudgetRecord,
    CopilotBilling,
    CopilotSeat,
    ModelCredits,
    SeatAssignee,
    SeatBreakdown,
    SeatHolder,
)

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)
ALICE = SeatHolder(user_id=1, login="alice")
BOB = SeatHolder(user_id=2, login="bob")


def credits(model: str, qty: float) -> ModelCredits:
    return ModelCredits(
        model=model, sku="ai_credits", gross_qty=qty, gross_usd=qty / 100, discount_usd=qty / 100, net_qty=0, net_usd=0
    )


def seat(holder: SeatHolder) -> CopilotSeat:
    return CopilotSeat(
        assignee=SeatAssignee(id=holder.user_id, login=holder.login),
        created_at=NOW - timedelta(days=90),
        last_activity_at=NOW - timedelta(hours=2),
    )


@pytest.fixture
async def seeded(worker_engine: AsyncEngine) -> None:
    """Alice and Bob hold seats; the owner does not. Written as the worker role."""
    store = PostgresSyncStore(worker_engine)
    billing = CopilotBilling(seat_breakdown=SeatBreakdown(total=2, active_this_cycle=2))
    assert await store.save_seats(billing, [seat(ALICE), seat(BOB)], NOW) == 2
    await store.replace_day_credits(
        date(2026, 11, 3),
        [ALICE, BOB],
        {
            ALICE.user_id: [credits("Claude Sonnet 4.6", 100)],
            BOB.user_id: [credits("GPT-5.5", 300), credits("Claude Opus 4.7", 50)],
        },
        [credits("GPT-5.5", 300), credits("Claude Sonnet 4.6", 150)],
    )
    await store.replace_org_budgets([budget("org", "organization", 500, 120)], NOW)
    await store.save_user_budget(ALICE, budget("org", "organization", 500, 4), NOW)
    await store.save_user_budget(BOB, budget("bob", "user", 80, 31), NOW)
    await store.upsert_activity(
        [
            activity(ALICE, {"vscode": [("claude-sonnet-4.6", 10, 5000, 800)]}),
            activity(BOB, {"vscode": [("gpt-5-mini", 40, 90000, 12000)], "opencode": [("gpt-5-mini", 2, 1000, 200)]}),
            activity(
                BOB,
                {"vscode": [("gpt-5-mini", 5, 3000, 400)], "code_review": [("unknown", 2, 700, 100)]},
                day="2026-11-04",
                user_initiated_interaction_count=6,
                code_generation_activity_count=4,
                code_acceptance_activity_count=2,
                loc_added_sum=30,
                used_chat=True,
                ai_adoption_phase={"phase_number": 1, "phase": "Phase 1", "version": "v1"},
                totals_by_feature=[
                    {"feature": "chat_panel_agent_mode", "user_initiated_interaction_count": 6},
                    {"feature": "agent_edit", "loc_added_sum": 24, "loc_deleted_sum": 6},
                    {"feature": "code_completion", "loc_suggested_to_add_sum": 40, "loc_added_sum": 6},
                ],
                totals_by_model_feature=[
                    {"model": "gpt-5-mini", "feature": "chat_panel_agent_mode", "user_initiated_interaction_count": 6},
                    {"model": "gpt-5-mini", "feature": "agent_edit", "loc_added_sum": 24, "loc_deleted_sum": 6},
                ],
                totals_by_language_model=[
                    {
                        "language": "python",
                        "model": "gpt-5-mini",
                        "code_generation_activity_count": 4,
                        "loc_added_sum": 30,
                    }
                ],
                totals_by_language_feature=[
                    {
                        "language": "python",
                        "feature": "chat_panel_agent_mode",
                        "code_generation_activity_count": 4,
                        "code_acceptance_activity_count": 2,
                        "loc_added_sum": 30,
                    }
                ],
                totals_by_ide=[{"ide": "vscode", "user_initiated_interaction_count": 6}],
            ),
            activity(
                BOB,
                {},
                day="2026-11-05",
                used_code_review=True,
                ai_adoption_phase={"phase_number": 2, "phase": "Phase 2", "version": "v1"},
            ),
        ]
    )


def activity(
    holder: SeatHolder, clients: dict[str, list[tuple[str, int, int, int]]], day: str = "2026-11-03", **fields: object
) -> UserDayMetrics:
    """One day of metrics with per-client, per-model calls: (model, requests, prompt tokens, output tokens).

    ``fields`` sets any other field of GitHub's record."""
    return UserDayMetrics.model_validate(
        {
            **fields,
            "day": day,
            "user_id": holder.user_id,
            "user_login": holder.login,
            "totals_by_client": [
                {
                    "client": client,
                    "totals_by_model": [
                        {
                            "model": model,
                            "request_count": requests,
                            "token_usage": {"prompt_tokens_sum": prompt, "output_tokens_sum": output},
                        }
                        for model, requests, prompt, output in models
                    ],
                }
                for client, models in clients.items()
            ],
        }
    )


def budget(budget_id: str, scope: str, amount: float, consumed: float) -> BudgetRecord:
    return BudgetRecord(
        id=budget_id,
        scope=scope,
        entity_name=None,
        sku="ai_credits",
        budget_type="SkuPricing",
        amount_usd=amount,
        consumed_usd=consumed,
        prevent_further_usage=True,
        expires_at=None,
    )
