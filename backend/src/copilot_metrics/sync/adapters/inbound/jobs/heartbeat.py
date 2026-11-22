"""The worker's health: a heartbeat file the container's health check reads.

Every ``BEAT_SECONDS`` the worker asks the database how often each sync job has failed since
its last success and writes the jobs at or past ``SYNC_ALERT_AFTER_FAILURES`` to
``HEARTBEAT_FILE``; a job reaching that count is also logged as an error, once. ``copilot-metrics
healthcheck`` (the compose health check) fails when the file is missing or older than
``STALE_AFTER`` (the worker is stuck or cannot reach the database) or names a failing job.
"""

import asyncio
import logging
import tempfile
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from copilot_metrics.shared.kernel import Clock, Frozen, SyncJob
from copilot_metrics.sync.ports import RunLog

log = logging.getLogger(__name__)

HEARTBEAT_FILE = Path(tempfile.gettempdir()) / "copilot-metrics-worker.json"
BEAT_SECONDS = 30
STALE_AFTER = timedelta(seconds=3 * BEAT_SECONDS)


class Heartbeat(Frozen):
    at: datetime
    failing: dict[SyncJob, int]  # failures since the last success, for jobs at or past the threshold


def failing_jobs(failures: Mapping[SyncJob, int], threshold: int) -> dict[SyncJob, int]:
    return {job: count for job, count in failures.items() if count >= threshold}


def problem(heartbeat: Heartbeat | None, now: datetime, stale_after: timedelta = STALE_AFTER) -> str | None:
    """Why the worker is unhealthy, or None when it is fine."""
    if heartbeat is None:
        return "no heartbeat yet"
    if now - heartbeat.at > stale_after:
        return f"last heartbeat {int((now - heartbeat.at).total_seconds())} s ago"
    if heartbeat.failing:
        return "failing: " + ", ".join(
            f"{job} ({count}x since its last success)" for job, count in heartbeat.failing.items()
        )
    return None


def read_heartbeat(path: Path = HEARTBEAT_FILE) -> Heartbeat | None:
    try:
        return Heartbeat.model_validate_json(path.read_bytes())
    except OSError, ValidationError:
        return None


def write_heartbeat(heartbeat: Heartbeat, path: Path = HEARTBEAT_FILE) -> None:
    """Replace the file in one step, so the health check never reads half of it."""
    partial = path.with_suffix(".tmp")
    partial.write_text(heartbeat.model_dump_json())
    partial.replace(path)


async def beat(runs: RunLog, clock: Clock, alert_after: int, path: Path = HEARTBEAT_FILE) -> None:
    """Write the heartbeat every ``BEAT_SECONDS`` until cancelled."""
    alerted: set[SyncJob] = set()
    while True:
        try:
            failing = failing_jobs(await runs.failures_since_success(), alert_after)
        except Exception:
            # No new heartbeat: the file goes stale and the health check fails.
            log.exception("heartbeat: cannot read the sync runs")
        else:
            for job in failing.keys() - alerted:
                log.error("%s has failed %d times since its last success; see the Sync page", job, failing[job])
            for job in alerted - failing.keys():
                log.info("%s is no longer failing", job)
            alerted = set(failing)
            write_heartbeat(Heartbeat(at=clock.now(), failing=failing), path)
        await asyncio.sleep(BEAT_SECONDS)
