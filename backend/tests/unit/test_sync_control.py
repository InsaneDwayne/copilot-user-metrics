"""Run/stop from the admin console: what the worker does with a request, and aborted runs."""

import asyncio
from datetime import UTC, datetime

import pytest

from copilot_metrics.shared.kernel import RunStatus, SyncJob
from copilot_metrics.sync.domain import QueuedJob, SyncAction, SyncRequest, SyncTarget, stop_outcome, target_queues
from copilot_metrics.sync.ports import JobQueue
from copilot_metrics.sync.service import SyncRequestHandler, SyncService

from ..clock import FixedClock

NOW = datetime(2026, 11, 13, 8, tzinfo=UTC)


def request(action: SyncAction, target: SyncTarget = SyncTarget.HISTORY) -> SyncRequest:
    return SyncRequest(
        id=1, requested_at=NOW, admin_login="owner", action=action, target=target, handled_at=None, outcome=None
    )


class FakeQueue(JobQueue):
    def __init__(self, jobs: list[QueuedJob], waiting: bool = False, broken: bool = False) -> None:
        self._jobs = jobs
        self._waiting = waiting
        self._broken = broken
        self.started: list[SyncTarget] = []
        self.cancelled: list[int] = []
        self.aborted: list[int] = []

    async def start(self, target: SyncTarget) -> bool:
        if self._broken:
            raise RuntimeError("queue is down")
        self.started.append(target)
        return not self._waiting

    async def jobs(self, target: SyncTarget) -> list[QueuedJob]:
        return self._jobs

    async def cancel(self, job_id: int) -> bool:
        self.cancelled.append(job_id)
        return True

    async def abort(self, job_id: int) -> bool:
        self.aborted.append(job_id)
        return True


async def test_run_queues_the_target_once() -> None:
    queue = FakeQueue([])
    assert await SyncRequestHandler(queue).handle(request(SyncAction.RUN, SyncTarget.CREDITS)) == "Queued"
    assert queue.started == [SyncTarget.CREDITS]
    waiting = FakeQueue([], waiting=True)
    assert await SyncRequestHandler(waiting).handle(request(SyncAction.RUN)) == "Already queued"


async def test_stop_cancels_waiting_jobs_and_aborts_running_ones() -> None:
    queue = FakeQueue([QueuedJob(id=1, status="todo"), QueuedJob(id=2, status="todo"), QueuedJob(id=3, status="doing")])
    outcome = await SyncRequestHandler(queue).handle(request(SyncAction.STOP))
    assert outcome == "Cancelled 2 queued, stopping 1 running"
    assert (queue.cancelled, queue.aborted) == ([1, 2], [3])
    assert await SyncRequestHandler(FakeQueue([])).handle(request(SyncAction.STOP)) == "Nothing to stop"


async def test_a_failing_request_reports_instead_of_crashing_the_worker() -> None:
    outcome = await SyncRequestHandler(FakeQueue([], broken=True)).handle(request(SyncAction.RUN))
    assert outcome == "Failed: RuntimeError: queue is down"


def test_stop_outcome_wording() -> None:
    assert stop_outcome(0, 2) == "Stopping 2 running"
    assert stop_outcome(3, 0) == "Cancelled 3 queued"


def test_queue_counts_group_tasks_by_target() -> None:
    counts = {("sync_credits", "doing"): 1, ("sync_credits_month", "todo"): 4, ("sync_metrics_day", "todo"): 2}
    queues = {q.target: (q.queued, q.running) for q in target_queues(counts)}
    assert list(queues) == list(SyncTarget)
    assert queues[SyncTarget.CREDITS] == (0, 1)
    assert queues[SyncTarget.HISTORY] == (6, 0)


class RecordingRunLog:
    def __init__(self) -> None:
        self.finished: list[tuple[RunStatus, str | None]] = []

    async def start(self, job: SyncJob, at: datetime) -> int:
        return 7

    async def finish(self, run_id: int, status: RunStatus, at: datetime, rows: int, error: str | None) -> None:
        self.finished.append((status, error))


class HangingGitHub:
    async def copilot_billing(self) -> None:
        await asyncio.Event().wait()


async def test_a_stopped_run_is_recorded_as_aborted() -> None:
    runs = RecordingRunLog()
    service = SyncService(HangingGitHub(), None, runs, FixedClock(NOW))  # type: ignore[arg-type]
    task = asyncio.create_task(service.sync_seats())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runs.finished == [(RunStatus.ABORTED, "Stopped from the admin console")]
