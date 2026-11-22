"""Jobs a dead worker left in ``doing`` are re-queued; a live worker's jobs are left alone."""

from collections.abc import AsyncGenerator

import procrastinate
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.sync.adapters.outbound.procrastinate.job_queue import recover_stalled_jobs

from .conftest import DB


@pytest.fixture
async def app(worker_engine: AsyncEngine) -> AsyncGenerator[procrastinate.App]:
    async with worker_engine.begin() as conn:
        await conn.execute(text("DELETE FROM procrastinate_jobs"))
        await conn.execute(text("DELETE FROM procrastinate_workers"))
    queue_app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=DB.as_role(DB.worker_role)))
    async with queue_app.open_async():
        yield queue_app


async def _worker(engine: AsyncEngine, seconds_since_heartbeat: int) -> int:
    async with engine.begin() as conn:
        return int(
            (
                await conn.execute(
                    text(
                        "INSERT INTO procrastinate_workers (last_heartbeat) "
                        "VALUES (now() - make_interval(secs => :s)) RETURNING id"
                    ),
                    {"s": seconds_since_heartbeat},
                )
            ).scalar_one()
        )


async def _job(engine: AsyncEngine, task: str, status: str, worker: int | None, lock: str | None = None) -> int:
    async with engine.begin() as conn:
        return int(
            (
                await conn.execute(
                    text(
                        "INSERT INTO procrastinate_jobs (queue_name, task_name, status, worker_id, queueing_lock) "
                        "VALUES ('sync', :task, CAST(:status AS procrastinate_job_status), :worker, :lock) RETURNING id"
                    ),
                    {"task": task, "status": status, "worker": worker, "lock": lock},
                )
            ).scalar_one()
        )


async def _statuses(engine: AsyncEngine) -> dict[int, str]:
    async with engine.begin() as conn:
        rows = await conn.execute(text("SELECT id, status::text FROM procrastinate_jobs"))
        return {r.id: r.status for r in rows}


async def test_jobs_of_a_dead_worker_are_requeued(app: procrastinate.App, worker_engine: AsyncEngine) -> None:
    dead, alive = await _worker(worker_engine, 600), await _worker(worker_engine, 1)
    orphan = await _job(worker_engine, "sync_metrics_day", "doing", dead)
    busy = await _job(worker_engine, "sync_credits_month", "doing", alive)
    # The catch-up was queued again after the restart, so the stalled copy can't go back to waiting.
    stalled_catch_up = await _job(worker_engine, "catch_up", "doing", dead, lock="catch_up")
    waiting_catch_up = await _job(worker_engine, "catch_up", "todo", None, lock="catch_up")

    assert await recover_stalled_jobs(app, "sync") == 2

    assert await _statuses(worker_engine) == {
        orphan: "todo",
        busy: "doing",
        stalled_catch_up: "failed",
        waiting_catch_up: "todo",
    }
    assert await recover_stalled_jobs(app, "sync") == 0
