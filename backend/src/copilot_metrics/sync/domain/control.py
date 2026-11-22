"""Run / stop from the admin console."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum

from copilot_metrics.shared.kernel import Frozen


class SyncTarget(StrEnum):
    """What an admin can run or stop from the Sync page."""

    CREDITS = "credits"
    SEATS = "seats"
    BUDGETS = "budgets"
    METRICS = "metrics"
    HISTORY = "history"  # the catch-up / backfill and the per-month/per-day jobs they queue


class SyncAction(StrEnum):
    RUN = "run"
    STOP = "stop"


# The worker's task names behind each target; the first one is what "run" queues.
# The API counts queued jobs by these names, the worker registers tasks under them.
SYNC_TASKS: dict[SyncTarget, tuple[str, ...]] = {
    SyncTarget.CREDITS: ("sync_credits",),
    SyncTarget.SEATS: ("sync_seats",),
    SyncTarget.BUDGETS: ("sync_budgets",),
    SyncTarget.METRICS: ("sync_metrics",),
    SyncTarget.HISTORY: ("catch_up", "backfill", "sync_credits_month", "sync_metrics_day"),
}


class SyncRequest(Frozen):
    """An admin's "run now" or "stop", written by the API and applied by the worker."""

    id: int
    requested_at: datetime
    admin_login: str
    action: SyncAction
    target: SyncTarget
    handled_at: datetime | None
    outcome: str | None  # what the worker did, e.g. "Queued" or "Cancelled 3 queued"


class TargetQueue(Frozen):
    target: SyncTarget
    queued: int  # jobs waiting in the worker's queue
    running: int  # jobs a worker is running now


class SyncControlStatus(Frozen):
    targets: list[TargetQueue]  # every target, in SyncTarget order
    requests: list[SyncRequest]  # the most recent, newest first


class QueuedJob(Frozen):
    id: int
    status: str  # procrastinate's: "todo" (waiting) or "doing" (running)


def target_queues(counts: Mapping[tuple[str, str], int]) -> list[TargetQueue]:
    """``counts`` maps (task name, procrastinate status) to a number of jobs."""
    return [
        TargetQueue(
            target=target,
            queued=sum(counts.get((task, "todo"), 0) for task in tasks),
            running=sum(counts.get((task, "doing"), 0) for task in tasks),
        )
        for target, tasks in SYNC_TASKS.items()
    ]


def stop_outcome(cancelled: int, stopping: int) -> str:
    parts = [f"cancelled {cancelled} queued"] if cancelled else []
    if stopping:
        parts.append(f"stopping {stopping} running")
    return ", ".join(parts).capitalize() if parts else "Nothing to stop"
