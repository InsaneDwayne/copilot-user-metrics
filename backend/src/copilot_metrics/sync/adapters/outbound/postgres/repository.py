"""Postgres implementation of the write ports (runs as the worker role)."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import Table, delete, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.adapters.outbound.postgres.tables import (
    credit_usage,
    org_activity_day,
    org_budget,
    org_credit_day,
    org_seat_cost,
    org_seat_summary,
    seat,
    sync_day,
    sync_run,
    user_activity,
    user_budget,
    user_team_day,
)
from copilot_metrics.shared.kernel import RunStatus, SyncJob
from copilot_metrics.shared.metrics_record import OrgDayMetrics, UserDayMetrics
from copilot_metrics.sync.domain import (
    BudgetRecord,
    CopilotBilling,
    CopilotSeat,
    ModelCredits,
    SeatCostRecord,
    SeatHolder,
    UserTeamRecord,
)
from copilot_metrics.sync.ports import RunLog, SyncStore


def _upsert(table: Table, keys: Sequence[str]) -> Insert:
    """INSERT that overwrites every non-key column when a row with the same ``keys`` exists."""
    stmt = pg_insert(table)
    updatable = {c.name: stmt.excluded[c.name] for c in table.columns if c.name not in keys}
    return stmt.on_conflict_do_update(index_elements=keys, set_=updatable)


class PostgresSyncStore(SyncStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save_seats(self, billing: CopilotBilling, seats: list[CopilotSeat], now: datetime) -> int:
        """Upsert current seats; seats that disappeared are marked ended (history is kept)."""
        rows = [
            {
                "user_id": s.assignee.id,
                "login": s.assignee.login,
                "avatar_url": s.assignee.avatar_url,
                "assigned_at": s.created_at,
                "ended_at": None,
                "pending_cancellation_date": s.pending_cancellation_date,
                "last_activity_at": s.last_activity_at,
                "last_activity_editor": s.last_activity_editor,
                "plan_type": s.plan_type,
                "assigning_team": s.assigning_team.slug if s.assigning_team else None,
                "updated_at": now,
            }
            for s in seats
            if s.assignee is not None
        ]
        summary = {"id": 1, "plan_type": billing.plan_type, "synced_at": now, **billing.seat_breakdown.model_dump()}
        async with self._engine.begin() as conn:
            await conn.execute(_upsert(org_seat_summary, ["id"]), summary)
            if rows:
                await conn.execute(_upsert(seat, ["user_id"]), rows)
            current = [r["user_id"] for r in rows]
            await conn.execute(
                update(seat)
                .where(seat.c.ended_at.is_(None), seat.c.user_id.not_in(current))
                .values(ended_at=now, updated_at=now)
            )
        return len(rows)

    async def seat_holders_since(self, day: date) -> list[SeatHolder]:
        query = select(seat.c.user_id, seat.c.login).where(or_(seat.c.ended_at.is_(None), seat.c.ended_at >= day))
        async with self._engine.connect() as conn:
            return [SeatHolder.model_validate(row._mapping) for row in await conn.execute(query)]

    async def replace_day_credits(
        self,
        day: date,
        holders: Sequence[SeatHolder],
        user_rows: Mapping[int, list[ModelCredits]],
        org_rows: list[ModelCredits],
    ) -> int:
        login = {h.user_id: h.login for h in holders}
        users = [
            {"user_id": user_id, "login": login[user_id], "day": day, **r.model_dump()}
            for user_id, rows in user_rows.items()
            for r in rows
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(credit_usage).where(credit_usage.c.day == day, credit_usage.c.user_id.in_(list(login)))
            )
            if users:
                await conn.execute(insert(credit_usage), users)
            await conn.execute(delete(org_credit_day).where(org_credit_day.c.day == day))
            if org_rows:
                await conn.execute(
                    insert(org_credit_day), [{"day": day, **r.model_dump(exclude={"sku"})} for r in org_rows]
                )
        return len(users) + len(org_rows)

    async def upsert_activity(self, records: list[UserDayMetrics]) -> int:
        if not records:
            return 0
        values = [
            {
                "user_id": r.user_id,
                "day": r.day,
                "login": r.user_login,
                "prompts": r.user_initiated_interaction_count,
                "generations": r.code_generation_activity_count,
                "acceptances": r.code_acceptance_activity_count,
                "loc_suggested": r.loc_suggested_to_add_sum,
                "loc_added": r.loc_added_sum,
                "used_agent": r.used_agent,
                "used_chat": r.used_chat,
                "used_cli": r.used_cli,
                "used_cloud_agent": r.used_cloud_agent,
                "used_app": r.used_copilot_app,
                "used_review": r.used_code_review,
                "raw": r.model_dump(mode="json"),
            }
            for r in records
        ]
        async with self._engine.begin() as conn:
            await conn.execute(_upsert(user_activity, ["user_id", "day"]), values)
        return len(values)

    async def upsert_org_activity(self, records: list[OrgDayMetrics]) -> int:
        if not records:
            return 0
        values = [_org_activity_row(r) for r in {r.day: r for r in records}.values()]
        async with self._engine.begin() as conn:
            await conn.execute(_upsert(org_activity_day, ["day"]), values)
        return len(values)

    async def replace_user_teams(self, day: date, records: list[UserTeamRecord]) -> int:
        unique = {(r.user_id, r.team_slug): r for r in records}.values()
        async with self._engine.begin() as conn:
            await conn.execute(delete(user_team_day).where(user_team_day.c.day == day))
            if unique:
                values = [
                    {"user_id": r.user_id, "day": day, "team_slug": r.team_slug, "login": r.user_login} for r in unique
                ]
                await conn.execute(insert(user_team_day), values)
        return len(unique)

    async def replace_org_budgets(self, records: list[BudgetRecord], now: datetime) -> int:
        async with self._engine.begin() as conn:
            await conn.execute(delete(org_budget))
            if records:
                await conn.execute(insert(org_budget), [{**r.model_dump(), "synced_at": now} for r in records])
        return len(records)

    async def save_user_budget(self, holder: SeatHolder, record: BudgetRecord | None, now: datetime) -> int:
        """One row per seat holder: the budget GitHub applies to them, or none."""
        async with self._engine.begin() as conn:
            await conn.execute(delete(user_budget).where(user_budget.c.user_id == holder.user_id))
            if record is None:
                return 0
            values = record.model_dump(exclude={"id", "entity_name", "budget_type"})
            row = {**values, "budget_id": record.id, "user_id": holder.user_id, "login": holder.login, "synced_at": now}
            await conn.execute(insert(user_budget).values(row))
        return 1

    async def save_seat_cost(self, record: SeatCostRecord, now: datetime) -> int:
        async with self._engine.begin() as conn:
            await conn.execute(_upsert(org_seat_cost, ["month"]), {**record.model_dump(), "synced_at": now})
        return 1

    async def mark_day_synced(self, job: SyncJob, day: date, at: datetime) -> None:
        stmt = pg_insert(sync_day).values(job=job.value, day=day, synced_at=at)
        async with self._engine.begin() as conn:
            await conn.execute(stmt.on_conflict_do_update(index_elements=["job", "day"], set_={"synced_at": at}))

    async def last_synced(self, job: SyncJob, first: date, last: date) -> dict[date, datetime]:
        query = select(sync_day.c.day, sync_day.c.synced_at).where(
            sync_day.c.job == job.value, sync_day.c.day.between(first, last)
        )
        async with self._engine.connect() as conn:
            return {row.day: row.synced_at for row in await conn.execute(query)}


def _org_activity_row(r: OrgDayMetrics) -> dict[str, object]:
    pr = r.pull_requests
    return {
        "day": r.day,
        "daily_active_users": r.daily_active_users,
        "weekly_active_users": r.weekly_active_users,
        "monthly_active_users": r.monthly_active_users,
        "missing_telemetry_users": r.missing_client_telemetry_user_count,
        "below_minimum_users": r.below_usage_metrics_minimum_user_count,
        "prs_created": pr and pr.total_created,
        "prs_created_by_copilot": pr and pr.total_created_by_copilot,
        "prs_reviewed": pr and pr.total_reviewed,
        "prs_reviewed_by_copilot": pr and pr.total_reviewed_by_copilot,
        "prs_merged": pr and pr.total_merged,
        "prs_merged_created_by_copilot": pr and pr.total_merged_created_by_copilot,
        "pr_suggestions": pr and pr.total_suggestions,
        "pr_applied_suggestions": pr and pr.total_applied_suggestions,
        "pr_copilot_suggestions": pr and pr.total_copilot_suggestions,
        "pr_copilot_applied_suggestions": pr and pr.total_copilot_applied_suggestions,
        "median_minutes_to_merge": pr and pr.median_minutes_to_merge,
        "median_minutes_to_merge_copilot": pr and pr.median_minutes_to_merge_copilot_authored,
        "raw": r.model_dump(mode="json"),
    }


class PostgresRunLog(RunLog):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def start(self, job: SyncJob, at: datetime) -> int:
        stmt = (
            insert(sync_run)
            .values(job=job.value, started_at=at, status=RunStatus.RUNNING.value)
            .returning(sync_run.c.id)
        )
        async with self._engine.begin() as conn:
            run_id: int = (await conn.execute(stmt)).scalar_one()
            return run_id

    async def finish(self, run_id: int, status: RunStatus, at: datetime, rows: int, error: str | None) -> None:
        stmt = (
            update(sync_run)
            .where(sync_run.c.id == run_id)
            .values(status=status.value, finished_at=at, rows=rows, error=error)
        )
        async with self._engine.begin() as conn:
            await conn.execute(stmt)

    async def close_interrupted(self, at: datetime, heartbeat_within: timedelta) -> int:
        async with self._engine.begin() as conn:
            result = await conn.execute(_CLOSE_INTERRUPTED_SQL, {"at": at, "within": heartbeat_within})
            return result.rowcount

    async def prune(self, before: datetime) -> int:
        async with self._engine.begin() as conn:
            return (await conn.execute(_PRUNE_RUNS_SQL, {"before": before})).rowcount

    async def failures_since_success(self) -> dict[SyncJob, int]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(_FAILURES_SINCE_SUCCESS_SQL)
            return {SyncJob(r.job): r.failures for r in rows}


# procrastinate keeps its workers' heartbeats in the same database.
_CLOSE_INTERRUPTED_SQL = text("""
UPDATE sync_run SET status = 'failed', finished_at = :at, error = 'The worker stopped during this run'
WHERE status = 'running'
  AND NOT EXISTS (SELECT 1 FROM procrastinate_workers WHERE last_heartbeat > now() - :within)
""")

# The latest success per job stays: it is the "Synced 18 min ago" on every page.
_PRUNE_RUNS_SQL = text("""
DELETE FROM sync_run
WHERE started_at < :before AND status <> 'running'
  AND id NOT IN (SELECT max(id) FROM sync_run WHERE status = 'succeeded' GROUP BY job)
""")

# Same count as the Sync page's (usage JOBS_SQL), for every job at once.
_FAILURES_SINCE_SUCCESS_SQL = text("""
SELECT f.job, count(*) AS failures
FROM sync_run f
WHERE f.status = 'failed'
  AND f.started_at > coalesce(
      (SELECT max(s.finished_at) FROM sync_run s WHERE s.job = f.job AND s.status = 'succeeded'), '-infinity')
GROUP BY f.job
""")
