# ruff: noqa: S311 - seeded pseudo-random demo data, not cryptography
"""Fictional demo data for the documentation screenshots.

Writes through the sync worker's own store (``PostgresSyncStore``), as the worker role, so the
data takes the same path as a real sync and the dashboard reads it through row-level security.
Every person, team and number is made up; the random generator is seeded, so the same day gives
the same screenshots.
"""

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from copilot_metrics.shared.adapters.outbound.postgres.engine import create_engine
from copilot_metrics.shared.kernel import RunStatus, SyncJob
from copilot_metrics.shared.metrics_record import OrgDayMetrics, UserDayMetrics
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresRunLog, PostgresSyncStore
from copilot_metrics.sync.domain import (
    BudgetRecord,
    CopilotBilling,
    CopilotSeat,
    ModelCredits,
    SeatAssignee,
    SeatBreakdown,
    SeatHolder,
)
from copilot_metrics.sync.domain.reports import UserTeamRecord
from copilot_metrics.sync.domain.seats import AssigningTeam
from copilot_metrics.sync.domain.usage_summary import SeatCostRecord

ORG = "acme-labs"
CREDIT_DAYS = 180
METRICS_DAYS = 120
USD_PER_CREDIT = Decimal("0.01")
INCLUDED_USD_PER_MONTH = Decimal("20")
SEAT_PRICE_USD = Decimal("19")

# Display names in billing, ids in the metrics reports.
MODELS = {
    "Claude Sonnet 4.6": "claude-sonnet-4.6",
    "Claude Opus 4.7": "claude-opus-4.7",
    "GPT-5.5": "gpt-5.5",
    "GPT-5 mini": "gpt-5-mini",
    "Gemini 3 Pro": "gemini-3-pro",
}
TEAMS = {
    "platform": ["go", "terraform", "yaml"],
    "payments": ["java", "kotlin", "sql"],
    "mobile": ["swift", "kotlin", "typescript"],
    "web": ["typescript", "css", "html"],
    "data": ["python", "sql", "scala"],
    "sre": ["python", "go", "shell"],
}
SKILLS = ["write-tests", "code-review", "release-notes", "migrate-api", "other"]
MCP_SERVERS = ["github", "jira", "docs-search", "sentry"]
CUSTOM_AGENTS = ["reviewer", "migration-helper", "test-writer"]


@dataclass(frozen=True)
class Person:
    holder: SeatHolder
    team: str
    ide: str
    intensity: float  # credits on an average working day
    models: dict[str, float]  # billing model name -> share
    personal_budget: Decimal | None = None
    seat_age_days: int = 400
    pending_cancellation: bool = False


# The personas the screenshots sign in as.
MEMBER = "dana-dev"
ADMIN = "olivia-owner"
READER = "rui-reader"
OUTSIDER = "pat-personal"

_LOGINS = [
    (MEMBER, "web", 240),
    (ADMIN, "platform", 60),
    (READER, "data", 30),
    ("amir-k", "platform", 310),
    ("bea-lindqvist", "payments", 180),
    ("chen-wu", "mobile", 140),
    ("diego-alvarez", "web", 200),
    ("emma-schulz", "data", 260),
    ("farah-n", "sre", 120),
    ("gus-okafor", "payments", 90),
    ("hana-sato", "mobile", 210),
    ("ivan-petrov", "platform", 160),
    ("jules-martin", "web", 75),
    ("kemal-yilmaz", "sre", 220),
    ("lena-fischer", "data", 150),
    ("marco-rossi", "payments", 130),
    ("nia-thompson", "web", 290),
    ("omar-haddad", "mobile", 40),
    ("priya-raman", "platform", 270),
    ("quinn-baker", "sre", 15),
    ("rosa-mendes", "data", 110),
    ("sam-oconnor", "payments", 60),
    ("tara-singh", "web", 170),
    ("uli-brandt", "platform", 0),
    ("vera-novak", "mobile", 95),
    ("wes-carter", "sre", 140),
]
_MODEL_MIXES = [
    {"Claude Sonnet 4.6": 0.55, "GPT-5.5": 0.25, "GPT-5 mini": 0.2},
    {"Claude Opus 4.7": 0.35, "Claude Sonnet 4.6": 0.45, "Gemini 3 Pro": 0.2},
    {"GPT-5.5": 0.5, "GPT-5 mini": 0.3, "Claude Sonnet 4.6": 0.2},
    {"Claude Sonnet 4.6": 0.7, "Claude Opus 4.7": 0.3},
    {"Gemini 3 Pro": 0.4, "GPT-5.5": 0.4, "GPT-5 mini": 0.2},
]
_IDES = ["vscode", "vscode", "vscode", "jetbrains", "visualstudio"]


def people() -> list[Person]:
    rng = random.Random(7)
    result = []
    for i, (login, team, intensity) in enumerate(_LOGINS):
        result.append(
            Person(
                holder=SeatHolder(user_id=10_000 + i, login=login),
                team=team,
                ide="vscode" if login == MEMBER else rng.choice(_IDES),
                intensity=intensity,
                models=_MODEL_MIXES[i % len(_MODEL_MIXES)],
                personal_budget=Decimal(60) if login in (MEMBER, "amir-k", "nia-thompson") else None,
                seat_age_days=25 if login == "quinn-baker" else rng.randint(200, 700),
                pending_cancellation=login == "uli-brandt",
            )
        )
    return result


def _credits(model: str, qty: Decimal, included_left: Decimal) -> tuple[ModelCredits, Decimal]:
    gross_usd = qty * USD_PER_CREDIT
    discount = min(gross_usd, max(included_left, Decimal(0)))
    net_usd = gross_usd - discount
    row = ModelCredits(
        model=model,
        sku="ai_credits",
        gross_qty=qty,
        gross_usd=gross_usd,
        discount_usd=discount,
        net_qty=(net_usd / USD_PER_CREDIT).quantize(Decimal(1)),
        net_usd=net_usd,
    )
    return row, included_left - discount


def _activity(rng: random.Random, p: Person, day: date, credits_today: float) -> UserDayMetrics | None:
    if credits_today <= 0:
        return None
    scale = credits_today / 100
    interactions = max(1, int(rng.gauss(14, 4) * scale))
    generated = max(1, int(interactions * rng.uniform(0.6, 1.1)))
    accepted = int(generated * rng.uniform(0.35, 0.7))
    suggested_loc = int(generated * rng.uniform(8, 20))
    added_loc = int(suggested_loc * rng.uniform(0.3, 0.6))
    languages = TEAMS[p.team]
    model_ids = [MODELS[m] for m in p.models]
    agent = rng.random() < 0.6
    features = {
        "code_completion": (0, int(generated * 0.5)),
        "chat_panel_agent_mode" if agent else "chat_panel_ask_mode": (int(interactions * 0.6), int(generated * 0.3)),
        "agent_edit": (0, int(generated * 0.2)),
        "chat_inline": (int(interactions * 0.4), 0),
    }
    skills = [{"skill": s, "interaction_count": rng.randint(1, 4)} for s in rng.sample(SKILLS, k=rng.randint(0, 2))]
    return UserDayMetrics.model_validate(
        {
            "day": day,
            "user_id": p.holder.user_id,
            "user_login": p.holder.login,
            "user_initiated_interaction_count": interactions,
            "code_generation_activity_count": generated,
            "code_acceptance_activity_count": accepted,
            "loc_suggested_to_add_sum": suggested_loc,
            "loc_added_sum": added_loc,
            "used_agent": agent,
            "used_chat": True,
            "used_cli": rng.random() < 0.25,
            "used_cloud_agent": rng.random() < 0.1,
            "used_copilot_app": False,
            "used_code_review": rng.random() < 0.3,
            "ai_adoption_phase": {"phase_number": 2 if agent else 1, "phase": "Phase 2" if agent else "Phase 1"},
            "totals_by_ide": [
                {
                    "ide": p.ide,
                    "user_initiated_interaction_count": interactions,
                    "code_generation_activity_count": generated,
                }
            ],
            "totals_by_feature": [
                {
                    "feature": feature,
                    "user_initiated_interaction_count": inter,
                    "code_generation_activity_count": gen,
                    "code_acceptance_activity_count": int(gen * 0.5),
                    "loc_suggested_to_add_sum": gen * 12,
                    "loc_added_sum": gen * 5,
                    "loc_deleted_sum": gen,
                }
                for feature, (inter, gen) in features.items()
            ],
            "totals_by_model_feature": [
                {
                    "model": model,
                    "feature": "chat_panel_agent_mode" if agent else "chat_panel_ask_mode",
                    "user_initiated_interaction_count": max(1, int(interactions * share)),
                    "code_generation_activity_count": int(generated * share),
                    "loc_added_sum": int(added_loc * share),
                }
                for model, share in zip(model_ids, p.models.values(), strict=True)
            ],
            "totals_by_language_model": [
                {
                    "language": language,
                    "model": model_ids[0],
                    "code_generation_activity_count": int(generated * w),
                    "code_acceptance_activity_count": int(accepted * w),
                    "loc_added_sum": int(added_loc * w),
                }
                for language, w in zip(languages, (0.6, 0.3, 0.1), strict=True)
            ],
            "totals_by_language_feature": [
                {
                    "language": language,
                    "feature": "code_completion",
                    "code_generation_activity_count": int(generated * w),
                    "code_acceptance_activity_count": int(accepted * w),
                    "loc_suggested_to_add_sum": int(suggested_loc * w),
                    "loc_added_sum": int(added_loc * w),
                }
                for language, w in zip(languages, (0.6, 0.3, 0.1), strict=True)
            ],
            "totals_by_client": [
                {
                    "client": p.ide,
                    "totals_by_model": [
                        {
                            "model": model,
                            "request_count": max(1, int(interactions * share * 3)),
                            "token_usage": {
                                "prompt_tokens_sum": int(interactions * share * 9000),
                                "output_tokens_sum": int(interactions * share * 1200),
                            },
                        }
                        for model, share in zip(model_ids, p.models.values(), strict=True)
                    ],
                }
            ],
            "totals_by_skill": skills,
        }
    )


def _org_day(rng: random.Random, day: date, active: dict[date, set[int]]) -> OrgDayMetrics:
    def active_within(days: int) -> int:
        return len(set().union(*(active.get(day - timedelta(d), set()) for d in range(days))))

    weekday = day.weekday() < 5
    created = rng.randint(28, 45) if weekday else rng.randint(0, 4)
    merged = int(created * rng.uniform(0.7, 0.95))
    by_copilot = int(created * rng.uniform(0.15, 0.3))
    return OrgDayMetrics.model_validate(
        {
            "day": day,
            "daily_active_users": len(active.get(day, set())),
            "weekly_active_users": active_within(7),
            "monthly_active_users": active_within(28),
            "pull_requests": {
                "total_created": created,
                "total_created_by_copilot": by_copilot,
                "total_reviewed": int(created * 0.9),
                "total_reviewed_by_copilot": int(created * 0.4),
                "total_merged": merged,
                "total_merged_created_by_copilot": int(by_copilot * 0.8),
                "total_merged_reviewed_by_copilot": int(merged * 0.4),
                "total_suggestions": created * 3,
                "total_applied_suggestions": created,
                "total_copilot_suggestions": created * 2,
                "total_copilot_applied_suggestions": int(created * 0.8),
                **(
                    {
                        "median_minutes_to_merge": rng.uniform(180, 600),
                        "median_minutes_to_merge_copilot_authored": rng.uniform(90, 400),
                    }
                    if merged
                    else {}
                ),
            },
            "totals_by_mcp": [{"mcp": m, "interaction_count": rng.randint(2, 40)} for m in MCP_SERVERS],
            "totals_by_custom_agent": [
                {"custom_agent": a, "interaction_count": rng.randint(0, 15)} for a in CUSTOM_AGENTS
            ],
        }
    )


async def seed(worker_database_url: str, now: datetime) -> None:
    """Fill an empty, migrated database with the demo organization, as of ``now``."""
    engine = create_engine(worker_database_url, pool_size=2)
    store = PostgresSyncStore(engine)
    runs = PostgresRunLog(engine)
    rng = random.Random(42)
    team = people()
    holders = [p.holder for p in team]
    today = now.date()

    try:
        # Seats: everyone but the outsider; one pending cancellation, one new.
        seats = [
            CopilotSeat(
                assignee=SeatAssignee(id=p.holder.user_id, login=p.holder.login),
                created_at=now - timedelta(days=p.seat_age_days),
                pending_cancellation_date=today.replace(day=1) + timedelta(days=40) if p.pending_cancellation else None,
                last_activity_at=None if p.intensity == 0 else now - timedelta(hours=rng.randint(1, 30)),
                last_activity_editor=None if p.intensity == 0 else f"{p.ide}/1.106",
                plan_type="business",
                assigning_team=AssigningTeam(slug=p.team),
            )
            for p in team
        ]
        breakdown = SeatBreakdown(
            total=len(seats),
            added_this_cycle=1,
            pending_cancellation=1,
            active_this_cycle=sum(p.intensity > 0 for p in team),
            inactive_this_cycle=sum(p.intensity == 0 for p in team),
        )
        await store.save_seats(CopilotBilling(seat_breakdown=breakdown, plan_type="business"), seats, now)

        # AI credits, per person, model and day, with a monthly included allowance per person.
        active: dict[date, set[int]] = defaultdict(set)
        daily_credits: dict[tuple[int, date], float] = {}
        month_net: dict[int, Decimal] = defaultdict(Decimal)
        included: dict[tuple[int, date], Decimal] = {}
        for offset in range(CREDIT_DAYS - 1, -1, -1):
            day = today - timedelta(days=offset)
            weekday = day.weekday() < 5
            growth = 0.6 + 0.4 * (1 - offset / CREDIT_DAYS)  # adoption grows over time
            user_rows: dict[int, list[ModelCredits]] = {}
            org_totals: dict[str, Decimal] = defaultdict(Decimal)
            for p in team:
                month = day.replace(day=1)
                left = included.setdefault((p.holder.user_id, month), INCLUDED_USD_PER_MONTH)
                works = weekday and rng.random() < 0.88
                amount = (
                    p.intensity * growth * rng.lognormvariate(0, 0.35) if works else p.intensity * 0.05 * rng.random()
                )
                if day == today:
                    amount *= now.hour / 24  # today is still running
                daily_credits[(p.holder.user_id, day)] = amount
                if amount < 1:
                    continue
                active[day].add(p.holder.user_id)
                rows = []
                for model, share in p.models.items():
                    qty = Decimal(int(amount * share * rng.uniform(0.8, 1.2)))
                    if qty <= 0:
                        continue
                    row, left = _credits(model, qty, left)
                    rows.append(row)
                    org_totals[model] += qty
                    if month == today.replace(day=1):
                        month_net[p.holder.user_id] += row.net_usd
                included[(p.holder.user_id, month)] = left
                user_rows[p.holder.user_id] = rows
            # The org's rows are the sum of everyone's, included and billed amounts alike.
            org_rows = [
                ModelCredits(
                    model=model,
                    sku="ai_credits",
                    **{
                        f: sum(
                            (getattr(r, f) for rows in user_rows.values() for r in rows if r.model == model), Decimal(0)
                        )
                        for f in ("gross_qty", "gross_usd", "discount_usd", "net_qty", "net_usd")
                    },
                )
                for model in org_totals
            ]
            await store.replace_day_credits(day, holders, user_rows, org_rows)
            await store.mark_day_synced(SyncJob.CREDITS, day, now - timedelta(minutes=7))

        # Activity metrics: GitHub publishes them a day late; the daily sync runs at 06:00.
        last_metrics_run = datetime.combine(today if now.hour >= 6 else today - timedelta(days=1), time(6), UTC)
        metrics_synced_at = last_metrics_run + timedelta(minutes=2)
        user_metrics = []
        for offset in range(METRICS_DAYS, 0, -1):
            day = today - timedelta(days=offset)
            for p in team:
                record = _activity(rng, p, day, daily_credits.get((p.holder.user_id, day), 0))
                if record:
                    user_metrics.append(record)
            await store.replace_user_teams(
                day,
                [
                    UserTeamRecord(day=day, user_id=p.holder.user_id, user_login=p.holder.login, slug=p.team)
                    for p in team
                ],
            )
            await store.mark_day_synced(SyncJob.METRICS, day, metrics_synced_at)
        for start in range(0, len(user_metrics), 500):
            await store.upsert_activity(user_metrics[start : start + 500])
        await store.upsert_org_activity(
            [_org_day(rng, today - timedelta(days=offset), active) for offset in range(METRICS_DAYS, 0, -1)]
        )

        # Budgets: one org-wide budget; three people have a personal one.
        org_consumed = sum(month_net.values(), Decimal(0))
        await store.replace_org_budgets([_budget("org", "organization", Decimal(1500), org_consumed)], now)
        for p in team:
            if p.personal_budget is not None:
                record = _budget(f"user-{p.holder.login}", "user", p.personal_budget, month_net[p.holder.user_id])
            else:
                record = _budget("org", "organization", Decimal(1500), month_net[p.holder.user_id])
            await store.save_user_budget(p.holder, record, now)

        # Seat cost: seats are billed per day, so mid-month the quantity is a fraction.
        month = today.replace(day=1)
        billed = (Decimal(len(seats)) * Decimal(today.day) / Decimal(30)).quantize(Decimal("0.01"))
        await store.save_seat_cost(
            SeatCostRecord(
                month=month,
                seats=billed,
                price_per_seat_usd=SEAT_PRICE_USD,
                gross_usd=billed * SEAT_PRICE_USD,
                net_usd=billed * SEAT_PRICE_USD,
            ),
            now,
        )

        # Sync history for the Sync page: regular runs, the first history load, and one failure
        # that was followed by a success.
        await _run(runs, SyncJob.HISTORY, now - timedelta(days=21), timedelta(hours=3), 48_210)
        for hours_ago in range(0, 48):
            at = now - timedelta(hours=hours_ago, minutes=10)
            await _run(runs, SyncJob.SEATS, at, timedelta(seconds=4), len(seats))
            await _run(runs, SyncJob.BUDGETS, at + timedelta(minutes=10), timedelta(seconds=9), len(seats) + 1)
            for quarter in range(3):
                await _run(runs, SyncJob.CREDITS, at - timedelta(minutes=20 * quarter), timedelta(seconds=40), 140)
        failed_at = last_metrics_run - timedelta(days=2)
        failed = await runs.start(SyncJob.METRICS, failed_at)
        await runs.finish(
            failed, RunStatus.FAILED, failed_at + timedelta(minutes=1), 0, "GitHub answered 502 Bad Gateway"
        )
        for days_ago in (1, 0):
            await _run(runs, SyncJob.METRICS, last_metrics_run - timedelta(days=days_ago), timedelta(minutes=2), 1_900)
    finally:
        await engine.dispose()


def _budget(budget_id: str, scope: str, amount: Decimal, consumed: Decimal) -> BudgetRecord:
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


async def _run(runs: PostgresRunLog, job: SyncJob, at: datetime, took: timedelta, rows: int) -> None:
    run_id = await runs.start(job, at)
    await runs.finish(run_id, RunStatus.SUCCEEDED, at + took, rows, None)
