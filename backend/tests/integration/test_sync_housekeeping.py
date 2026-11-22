"""The worker closes runs a stopped worker left open, and prunes its old bookkeeping."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.kernel import Role, RunStatus, SyncJob, Viewer
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresRunLog
from copilot_metrics.sync.adapters.outbound.postgres.requests import PostgresRequestInbox, PostgresSyncRequests
from copilot_metrics.sync.domain import SyncAction, SyncRequest, SyncTarget

from ..clock import FixedClock

NOW = datetime(2026, 11, 19, 8, tzinfo=UTC)
HEARTBEAT = timedelta(seconds=30)


async def _workers(engine: AsyncEngine, *seconds_since_heartbeat: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM procrastinate_workers"))
        for seconds in seconds_since_heartbeat:
            await conn.execute(
                text("INSERT INTO procrastinate_workers (last_heartbeat) VALUES (now() - make_interval(secs => :s))"),
                {"s": seconds},
            )


async def _runs(engine: AsyncEngine) -> dict[int, tuple[str, str | None]]:
    async with engine.begin() as conn:
        rows = await conn.execute(text("SELECT id, status, error FROM sync_run"))
        return {r.id: (r.status, r.error) for r in rows}


async def test_runs_left_running_are_failed_when_no_worker_is_alive(worker_engine: AsyncEngine) -> None:
    runs = PostgresRunLog(worker_engine)
    left = await runs.start(SyncJob.CREDITS, NOW - timedelta(hours=1))
    done = await runs.start(SyncJob.SEATS, NOW - timedelta(hours=1))
    await runs.finish(done, RunStatus.SUCCEEDED, NOW - timedelta(minutes=59), 3, None)

    await _workers(worker_engine, 1)  # another worker is alive: the run may be its own
    assert await runs.close_interrupted(NOW, HEARTBEAT) == 0
    assert (await _runs(worker_engine))[left][0] == "running"

    await _workers(worker_engine, 600)  # only a dead one
    assert await runs.close_interrupted(NOW, HEARTBEAT) == 1
    assert await _runs(worker_engine) == {
        left: ("failed", "The worker stopped during this run"),
        done: ("succeeded", None),
    }


async def test_old_runs_are_pruned_but_each_jobs_latest_success_stays(worker_engine: AsyncEngine) -> None:
    runs = PostgresRunLog(worker_engine)
    old = NOW - timedelta(days=200)

    async def run(job: SyncJob, at: datetime, status: RunStatus | None) -> int:
        run_id = await runs.start(job, at)
        if status is not None:
            await runs.finish(run_id, status, at + timedelta(minutes=1), 0, None)
        return run_id

    old_success = await run(SyncJob.CREDITS, old, RunStatus.SUCCEEDED)
    old_failure = await run(SyncJob.CREDITS, old + timedelta(hours=1), RunStatus.FAILED)
    latest_old_success = await run(SyncJob.METRICS, old, RunStatus.SUCCEEDED)  # METRICS' only success
    still_running = await run(SyncJob.HISTORY, old, None)
    recent_success = await run(SyncJob.CREDITS, NOW, RunStatus.SUCCEEDED)

    assert await runs.prune(NOW - timedelta(days=90)) == 2
    remaining = set(await _runs(worker_engine))
    assert remaining == {latest_old_success, still_running, recent_success}
    assert not {old_success, old_failure} & remaining


async def test_handled_requests_are_pruned_open_ones_stay(api_engine: AsyncEngine, worker_engine: AsyncEngine) -> None:
    admin = Viewer(user_id=3, login="owner", role=Role.ADMIN)
    requests = PostgresSyncRequests(api_engine)
    handled = await requests.request(admin, SyncTarget.CREDITS, SyncAction.RUN)

    async def queued(request: SyncRequest) -> str:
        return "Queued"

    # Handled 200 days ago, then a new one comes in and stays open.
    await PostgresRequestInbox(worker_engine, FixedClock(NOW - timedelta(days=200))).handle_pending(queued)
    open_one = await requests.request(admin, SyncTarget.CREDITS, SyncAction.RUN)
    inbox = PostgresRequestInbox(worker_engine, FixedClock(NOW))

    assert await inbox.prune(NOW - timedelta(days=90)) == 1
    assert [r.id for r in await requests.recent(admin, 10)] == [open_one.id]
    assert open_one.id != handled.id


async def test_failures_since_success_counts_per_job(worker_engine: AsyncEngine) -> None:
    runs = PostgresRunLog(worker_engine)

    async def run(job: SyncJob, minutes_ago: int, status: RunStatus) -> None:
        at = NOW - timedelta(minutes=minutes_ago)
        await runs.finish(await runs.start(job, at), status, at + timedelta(seconds=30), 0, None)

    await run(SyncJob.CREDITS, 90, RunStatus.FAILED)  # before the success: forgiven
    await run(SyncJob.CREDITS, 60, RunStatus.SUCCEEDED)
    await run(SyncJob.CREDITS, 40, RunStatus.FAILED)
    await run(SyncJob.CREDITS, 20, RunStatus.FAILED)
    await run(SyncJob.SEATS, 30, RunStatus.FAILED)  # never succeeded
    await run(SyncJob.METRICS, 30, RunStatus.FAILED)
    await run(SyncJob.METRICS, 10, RunStatus.SUCCEEDED)  # recovered

    assert await runs.failures_since_success() == {SyncJob.CREDITS: 2, SyncJob.SEATS: 1}
