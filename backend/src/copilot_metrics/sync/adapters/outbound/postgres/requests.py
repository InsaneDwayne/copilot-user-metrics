"""Run/stop requests from the admin console, in Postgres.

The API writes them as an admin (row-level security checks it is their own name) and
wakes the worker with ``NOTIFY``; the worker applies them and records the outcome.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.adapters.outbound.postgres.engine import viewer_scope
from copilot_metrics.shared.adapters.outbound.postgres.tables import sync_request
from copilot_metrics.shared.kernel import Clock, Viewer
from copilot_metrics.sync.domain import SyncAction, SyncRequest, SyncTarget
from copilot_metrics.sync.ports import RequestHandler, RequestInbox, SyncRequests

CHANNEL = "copilot_sync_request"

_COLUMNS = (
    sync_request.c.id,
    sync_request.c.requested_at,
    sync_request.c.admin_login,
    sync_request.c.action,
    sync_request.c.target,
    sync_request.c.handled_at,
    sync_request.c.outcome,
)

_JOB_COUNTS_SQL = text("""
SELECT task_name, status::text AS status, count(*) AS jobs
FROM procrastinate_jobs WHERE status IN ('todo', 'doing')
GROUP BY task_name, status
""")


def _request(row: Any) -> SyncRequest:
    return SyncRequest.model_validate(row._mapping)


class PostgresSyncRequests(SyncRequests):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def request(self, admin: Viewer, target: SyncTarget, action: SyncAction) -> SyncRequest:
        t = sync_request
        async with viewer_scope(self._engine, admin) as conn:
            open_one = (
                await conn.execute(
                    select(*_COLUMNS)
                    .where(t.c.target == target.value, t.c.action == action.value, t.c.handled_at.is_(None))
                    .order_by(t.c.id)
                    .limit(1)
                )
            ).first()
            if open_one:
                return _request(open_one)
            row = (
                await conn.execute(
                    t.insert()
                    .values(
                        admin_user_id=admin.user_id, admin_login=admin.login, action=action.value, target=target.value
                    )
                    .returning(*_COLUMNS)
                )
            ).one()
            # Delivered when the transaction commits, so the worker always finds the row.
            await conn.execute(text("SELECT pg_notify(:channel, '')"), {"channel": CHANNEL})
            return _request(row)

    async def recent(self, admin: Viewer, limit: int) -> list[SyncRequest]:
        query = select(*_COLUMNS).order_by(sync_request.c.id.desc()).limit(limit)
        async with viewer_scope(self._engine, admin) as conn:
            return [_request(row) for row in await conn.execute(query)]

    async def job_counts(self, admin: Viewer) -> dict[tuple[str, str], int]:
        async with viewer_scope(self._engine, admin) as conn:
            return {(r.task_name, r.status): r.jobs for r in await conn.execute(_JOB_COUNTS_SQL)}


class PostgresRequestInbox(RequestInbox):
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def handle_pending(self, handler: RequestHandler) -> int:
        t = sync_request
        # Locked while handled, so a second worker skips them instead of applying them twice.
        query = select(*_COLUMNS).where(t.c.handled_at.is_(None)).order_by(t.c.id).with_for_update(skip_locked=True)
        async with self._engine.begin() as conn:
            pending = [_request(row) for row in await conn.execute(query)]
            for request in pending:
                outcome = await handler(request)
                await conn.execute(
                    update(t).where(t.c.id == request.id).values(handled_at=self._clock.now(), outcome=outcome)
                )
        return len(pending)

    async def prune(self, before: datetime) -> int:
        t = sync_request
        async with self._engine.begin() as conn:
            return (await conn.execute(delete(t).where(t.c.handled_at < before))).rowcount
