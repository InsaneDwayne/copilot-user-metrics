"""``catch_up`` queues low-priority jobs for missing days (credits per month, metrics per day), never twice."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import procrastinate
from procrastinate.jobs import Job
from procrastinate.testing import InMemoryConnector

from copilot_metrics.settings import SyncSettings
from copilot_metrics.shared.kernel import SyncJob
from copilot_metrics.sync.adapters.inbound.jobs.tasks import HISTORY_PRIORITY, HISTORY_RETRY, register_tasks
from copilot_metrics.sync.domain import days_to_catch_up
from copilot_metrics.sync.service import SyncService

from ..clock import FixedClock

NOW = datetime(2026, 11, 13, 8, tzinfo=UTC)


async def _no_prune(before: datetime) -> int:
    return 0


class FakeService:
    """Credits synced (and settled) for every day but Nov 10 and 11; metrics never synced."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def sync_seats(self) -> int:
        self.calls.append("seats")
        return 0

    async def sync_budgets(self) -> int:
        self.calls.append("budgets")
        return 0

    async def queue_history(self, defer: Callable[[], Awaitable[int]]) -> int:
        queued = await defer()
        self.calls.append(f"history:{queued}")
        return queued

    async def days_to_catch_up(self, job: SyncJob, window: Sequence[date], settle_days: int) -> list[date]:
        if job is SyncJob.METRICS:
            return days_to_catch_up(window, {}, settle_days)
        settled = datetime(2027, 1, 1, tzinfo=UTC)
        synced = {d: settled for d in window if d not in (date(2026, 11, 10), date(2026, 11, 11))}
        return days_to_catch_up(window, synced, settle_days)


async def test_catch_up_queues_missing_days_newest_first_once() -> None:
    connector = InMemoryConnector()
    app = procrastinate.App(connector=connector)
    fake = FakeService()

    async def service() -> SyncService:
        return cast(SyncService, fake)

    settings = SyncSettings(backfill_credits_days=5, backfill_metrics_days=2, credits_lookback_days=2)
    register_tasks(app, service, _no_prune, settings, FixedClock(NOW), queue="sync")

    async with app.open_async():
        catch_up: Any = app.tasks["catch_up"]
        await catch_up.func()
        await catch_up.func()  # e.g. the worker restarted before the queue drained

    jobs = sorted(connector.jobs.values(), key=lambda j: j["id"])
    queued = [(j["task_name"], j["args"]) for j in jobs]
    # Credits: one month job for the two unsynced days of Nov 9-13. Metrics: the two complete days up to yesterday.
    assert queued == [
        ("sync_credits_month", {"days": ["2026-11-11", "2026-11-10"]}),
        ("sync_metrics_day", {"day": "2026-11-12"}),
        ("sync_metrics_day", {"day": "2026-11-11"}),
    ]
    assert {j["priority"] for j in jobs} == {HISTORY_PRIORITY}
    assert {j["queue_name"] for j in jobs} == {"sync"}
    # Each catch-up logs one history run counting what it queued; the second finds it all queued already.
    assert fake.calls == ["seats", "budgets", "history:3", "seats", "budgets", "history:0"]


def test_history_jobs_retry_within_minutes_not_days() -> None:
    def wait(attempts: int) -> timedelta | None:
        job = Job(id=1, queue="sync", lock=None, queueing_lock=None, task_name="sync_metrics_day", attempts=attempts)
        decision = HISTORY_RETRY.get_retry_decision(exception=RuntimeError(), job=job)
        if decision is None or decision.retry_at is None:
            return None
        return decision.retry_at - datetime.now(UTC)

    waits = [wait(attempts) for attempts in range(5)]
    assert all(w is not None and w < timedelta(minutes=15) for w in waits[:4])
    assert waits[4] is None  # gives up after four retries

    app = procrastinate.App(connector=InMemoryConnector())
    register_tasks(app, cast(Any, None), _no_prune, SyncSettings(), FixedClock(NOW), queue="sync")
    for name in ("sync_credits_month", "sync_metrics_day"):
        assert app.tasks[name].retry_strategy is HISTORY_RETRY
