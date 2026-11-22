"""The worker's procrastinate queue, as the admin console's run/stop needs it."""

import logging

import procrastinate
from procrastinate.exceptions import AlreadyEnqueued, UniqueViolation
from procrastinate.jobs import Status

from copilot_metrics.shared.kernel import Clock
from copilot_metrics.sync.domain import SYNC_TASKS, QueuedJob, SyncTarget
from copilot_metrics.sync.ports import JobQueue

log = logging.getLogger(__name__)

# A worker that sent no heartbeat for this long is gone (procrastinate's default; workers beat every 10 s).
STALLED_AFTER_SECONDS = 30

# Ahead of the periodic syncs (0) and history (-10): an admin asked for it now.
MANUAL_PRIORITY = 10


class ProcrastinateJobQueue(JobQueue):
    def __init__(self, app: procrastinate.App, clock: Clock) -> None:
        self._app = app
        self._clock = clock

    async def start(self, target: SyncTarget) -> bool:
        task = SYNC_TASKS[target][0]
        # The task's own queueing lock applies, so a run already waiting isn't doubled.
        deferrer = self._app.configure_task(task, priority=MANUAL_PRIORITY)
        # Periodic tasks (every target but history) take the tick they were deferred for.
        kwargs = {"timestamp": int(self._clock.now().timestamp())} if target is not SyncTarget.HISTORY else {}
        try:
            await deferrer.defer_async(**kwargs)
        except AlreadyEnqueued:
            return False
        return True

    async def jobs(self, target: SyncTarget) -> list[QueuedJob]:
        manager = self._app.job_manager
        found: list[QueuedJob] = []
        for task in SYNC_TASKS[target]:
            for status in ("todo", "doing"):
                for job in await manager.list_jobs_async(task=task, status=status):
                    if job.id is not None:
                        found.append(QueuedJob(id=job.id, status=status))
        return found

    async def cancel(self, job_id: int) -> bool:
        return await self._app.job_manager.cancel_job_by_id_async(job_id)

    async def abort(self, job_id: int) -> bool:
        # The worker cancels the running asyncio task; SyncService records the run as aborted.
        return await self._app.job_manager.cancel_job_by_id_async(job_id, abort=True)


async def recover_stalled_jobs(app: procrastinate.App, queue: str) -> int:
    """Re-queue jobs left running by a worker that died (killed, restarted, crashed).

    procrastinate keeps such a job in ``doing`` forever: the Sync page shows it running and
    its day or month is never synced. A worker counts as gone once it has missed its
    heartbeats for 30 s (live workers send one every 10 s), so a busy job is never touched.
    A job someone asked to stop is failed instead, and so is one whose queueing lock is taken
    by a newer waiting copy (that copy does the work).
    """
    manager = app.job_manager
    recovered = 0
    for job in await manager.get_stalled_jobs(queue=queue):
        try:
            await manager.retry_job(job)
        except UniqueViolation:
            assert job.id is not None
            await manager.finish_job_by_id_async(job.id, Status.FAILED, delete_job=False)
        log.warning("job %s (%s) was left running by a stopped worker; recovered", job.id, job.task_name)
        recovered += 1
    await manager.prune_stalled_workers(seconds_since_heartbeat=STALLED_AFTER_SECONDS)
    return recovered
