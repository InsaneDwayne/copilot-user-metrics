"""Postgres implementation of the read ports.

Runs as the read-only API role inside ``viewer_scope``, so row-level security
applies on top of the explicit ``user_id`` filters below.
"""

from collections.abc import Mapping
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Executable, Table, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.adapters.outbound.postgres.engine import viewer_scope
from copilot_metrics.shared.adapters.outbound.postgres.tables import (
    credit_usage,
    org_activity_day,
    org_budget,
    org_credit_day,
    org_seat_cost,
    org_seat_summary,
    seat,
    user_activity,
    user_budget,
    user_team_day,
)
from copilot_metrics.shared.kernel import Period, RunStatus, Viewer
from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.usage.adapters.outbound.postgres.breakdowns import (
    FEATURE_USE_SQL,
    IDE_USE_SQL,
    LANGUAGE_MODEL_SQL,
    LANGUAGE_USE_SQL,
    MODEL_FEATURE_SQL,
    SKILL_USE_SQL,
)
from copilot_metrics.usage.adapters.outbound.postgres.queries import (
    JOBS_SQL,
    MEMBERS_SQL,
    MODEL_TOKENS_SQL,
    REPORT_USE_SQL,
    TEAM_MODELS_SQL,
)
from copilot_metrics.usage.domain import (
    ActivityBreakdown,
    ActivityDayRow,
    Budget,
    CreditRow,
    FeatureUse,
    IdeUse,
    JobStatus,
    LanguageModelUse,
    LanguageTotals,
    MemberProfile,
    MemberRow,
    ModelCallsRow,
    ModelFeatureUse,
    NamedCount,
    OrgReportDay,
    OrgReportUse,
    SeatCost,
    SeatSummary,
    SkillUse,
    TeamModelCredits,
    UserBudget,
)
from copilot_metrics.usage.ports import UsageReader


def _credit_columns(table: Table) -> tuple[ColumnElement[Any], ...]:
    return (
        table.c.day,
        table.c.model,
        table.c.gross_qty.label("credits"),
        table.c.gross_usd,
        table.c.discount_usd.label("included_usd"),
        table.c.net_usd.label("billed_usd"),
    )


def _budget_columns(table: Table) -> tuple[ColumnElement[Any], ...]:
    c = table.c
    return (c.scope, c.sku, c.amount_usd, c.consumed_usd, c.prevent_further_usage, c.expires_at, c.synced_at)


class PostgresUsageReader(UsageReader):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def _rows[M: BaseModel](
        self, viewer: Viewer, model: type[M], query: Executable, params: Mapping[str, Any] | None = None
    ) -> list[M]:
        async with viewer_scope(self._engine, viewer) as conn:
            return [model.model_validate(row._mapping) for row in await conn.execute(query, params)]

    async def _first[M: BaseModel](self, viewer: Viewer, model: type[M], query: Executable) -> M | None:
        async with viewer_scope(self._engine, viewer) as conn:
            row = (await conn.execute(query)).first()
        return model.model_validate(row._mapping) if row else None

    async def user_credits(self, viewer: Viewer, user_id: int, period: Period) -> list[CreditRow]:
        t = credit_usage
        query = select(*_credit_columns(t)).where(t.c.user_id == user_id, t.c.day.between(period.start, period.end))
        return await self._rows(viewer, CreditRow, query)

    async def org_credits(self, viewer: Viewer, period: Period) -> list[CreditRow]:
        t = org_credit_day
        query = select(*_credit_columns(t)).where(t.c.day.between(period.start, period.end))
        return await self._rows(viewer, CreditRow, query)

    async def user_activity(self, viewer: Viewer, user_id: int, period: Period) -> list[UserDayMetrics]:
        t = user_activity
        query = (
            select(t.c.raw).where(t.c.user_id == user_id, t.c.day.between(period.start, period.end)).order_by(t.c.day)
        )
        async with viewer_scope(self._engine, viewer) as conn:
            return [UserDayMetrics.model_validate(raw) for raw in (await conn.scalars(query))]

    async def model_calls(self, viewer: Viewer, period: Period, user_id: int | None = None) -> list[ModelCallsRow]:
        params = {"start": period.start, "end": period.end, "user_id": user_id}
        return await self._rows(viewer, ModelCallsRow, MODEL_TOKENS_SQL, params)

    async def activity_days(
        self, viewer: Viewer, first: date, last: date, team: str | None = None
    ) -> list[ActivityDayRow]:
        t = user_activity
        query = select(
            t.c.user_id,
            t.c.day,
            t.c.prompts,
            t.c.generations,
            t.c.acceptances,
            t.c.loc_suggested,
            t.c.loc_added,
            t.c.used_chat,
            t.c.used_agent,
            t.c.used_cli,
            t.c.used_cloud_agent,
            t.c.used_app,
            t.c.used_review,
        ).where(t.c.day.between(first, last))
        if team is not None:
            in_team = select(user_team_day.c.user_id).where(
                user_team_day.c.user_id == t.c.user_id,
                user_team_day.c.day == t.c.day,
                user_team_day.c.team_slug == team,
            )
            query = query.where(in_team.exists())
        return await self._rows(viewer, ActivityDayRow, query)

    async def activity_breakdown(self, viewer: Viewer, period: Period, team: str | None = None) -> ActivityBreakdown:
        params = {"start": period.start, "end": period.end, "team": team}
        async with viewer_scope(self._engine, viewer) as conn:

            async def rows[M: BaseModel](model: type[M], query: Executable) -> list[M]:
                return [model.model_validate(r._mapping) for r in await conn.execute(query, params)]

            return ActivityBreakdown(
                features=await rows(FeatureUse, FEATURE_USE_SQL),
                languages=await rows(LanguageTotals, LANGUAGE_USE_SQL),
                ides=await rows(IdeUse, IDE_USE_SQL),
                model_features=await rows(ModelFeatureUse, MODEL_FEATURE_SQL),
                language_models=await rows(LanguageModelUse, LANGUAGE_MODEL_SQL),
                skills=await rows(SkillUse, SKILL_USE_SQL),
            )

    async def metrics_through(self, viewer: Viewer) -> date | None:
        async with viewer_scope(self._engine, viewer) as conn:
            day: date | None = await conn.scalar(select(func.max(user_activity.c.day)))
            return day

    async def org_report_days(self, viewer: Viewer, period: Period) -> list[OrgReportDay]:
        t = org_activity_day
        query = select(*(c for c in t.c if c.name != "raw")).where(t.c.day.between(period.start, period.end))
        return await self._rows(viewer, OrgReportDay, query.order_by(t.c.day))

    async def org_report_use(self, viewer: Viewer, period: Period) -> OrgReportUse:
        params = {"start": period.start, "end": period.end}
        async with viewer_scope(self._engine, viewer) as conn:

            async def named(key: str, name: str) -> list[NamedCount]:
                rows = await conn.execute(REPORT_USE_SQL, {**params, "key": key, "name": name})
                return [NamedCount.model_validate(r._mapping) for r in rows]

            return OrgReportUse(
                mcp_servers=await named("totals_by_mcp", "mcp"),
                custom_agents=await named("totals_by_custom_agent", "custom_agent"),
            )

    async def seat_summary(self, viewer: Viewer) -> SeatSummary | None:
        return await self._first(viewer, SeatSummary, select(org_seat_summary).where(org_seat_summary.c.id == 1))

    async def user_budgets(self, viewer: Viewer, user_id: int | None = None) -> list[UserBudget]:
        t = user_budget
        query = select(t.c.user_id, t.c.budget_id.label("id"), *_budget_columns(t))
        if user_id is not None:
            query = query.where(t.c.user_id == user_id)
        async with viewer_scope(self._engine, viewer) as conn:
            rows = (await conn.execute(query)).all()
        return [UserBudget(user_id=r.user_id, budget=Budget.model_validate(r._mapping)) for r in rows]

    async def org_budgets(self, viewer: Viewer) -> list[Budget]:
        t = org_budget
        query = select(t.c.id, *_budget_columns(t)).order_by(t.c.scope, t.c.sku)
        return await self._rows(viewer, Budget, query)

    async def seat_cost(self, viewer: Viewer, month: date) -> SeatCost | None:
        return await self._first(viewer, SeatCost, select(org_seat_cost).where(org_seat_cost.c.month == month))

    async def members(self, viewer: Viewer, period: Period) -> list[MemberRow]:
        return await self._rows(viewer, MemberRow, MEMBERS_SQL, {"start": period.start, "end": period.end})

    async def team_models(self, viewer: Viewer, period: Period) -> list[TeamModelCredits]:
        return await self._rows(viewer, TeamModelCredits, TEAM_MODELS_SQL, {"start": period.start, "end": period.end})

    async def member_profile(self, viewer: Viewer, login: str) -> MemberProfile | None:
        return await self._first(viewer, MemberProfile, select(seat).where(func.lower(seat.c.login) == login.lower()))

    async def jobs(self, viewer: Viewer) -> list[JobStatus]:
        params = {"failed": RunStatus.FAILED.value, "succeeded": RunStatus.SUCCEEDED.value}
        return await self._rows(viewer, JobStatus, JOBS_SQL, params)
