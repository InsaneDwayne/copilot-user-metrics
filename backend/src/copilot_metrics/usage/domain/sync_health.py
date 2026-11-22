"""How fresh the synced data is."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from copilot_metrics.shared.kernel import Frozen, RunStatus, SyncJob


class JobStatus(Frozen):
    job: SyncJob
    last_started_at: datetime | None
    last_status: RunStatus | None
    last_error: str | None
    last_rows: int
    last_success_at: datetime | None
    failures_since_success: int


class SyncStatus(Frozen):
    last_success_at: datetime | None
    stale: bool
    jobs: list[JobStatus]  # empty for non-admins


def sync_status(jobs: Sequence[JobStatus], now: datetime, stale_after: timedelta, include_jobs: bool) -> SyncStatus:
    credits = next((j for j in jobs if j.job == SyncJob.CREDITS), None)
    last = credits.last_success_at if credits else None
    return SyncStatus(
        last_success_at=last,
        stale=last is None or now - last > stale_after,
        jobs=list(jobs) if include_jobs else [],
    )
