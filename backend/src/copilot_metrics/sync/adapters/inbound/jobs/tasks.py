"""Inbound adapter: procrastinate tasks that drive the SyncService.

Periodic jobs refresh recent days. ``catch_up`` (deferred whenever the worker starts)
and ``backfill`` (on demand) fan out into one job per month of credits and one per day
of metrics, so loading history is resumable and visible in the procrastinate job table.
"""

import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any

import procrastinate
from procrastinate.exceptions import AlreadyEnqueued

from copilot_metrics.settings import SyncSettings
from copilot_metrics.shared.kernel import Clock, SyncJob, recent_days
from copilot_metrics.sync.adapters.outbound.procrastinate.job_queue import recover_stalled_jobs
from copilot_metrics.sync.domain import by_month
from copilot_metrics.sync.service import SyncService

log = logging.getLogger(__name__)

ServiceProvider = Callable[[], Awaitable[SyncService]]
# Deletes the sync's bookkeeping (runs, handled requests) from before the given time.
Pruner = Callable[[datetime], Awaitable[int]]

# Per-day history jobs queue below the periodic ones (priority 0), so a long backfill never
# holds up fresh data: with one worker, an hourly sync still runs within the hour.
HISTORY_PRIORITY = -10
# Recovering jobs a dead worker left behind goes first: the rest of the queue may depend on it.
STALLED_PRIORITY = 5
# Retries of a failed history job, 1, 5, 9 and 13 minutes after each failure (wait +
# linear_wait * attempts). Not exponential_wait: procrastinate raises it to the power of the
# attempt, so 30 meant 30 s, 15 min, 7.5 h and then 9.4 days, and a job waiting that long
# shows as queued on the Sync page and blocks the catch-up from queueing its day again.
HISTORY_RETRY = procrastinate.RetryStrategy(max_attempts=4, wait=60, linear_wait=240)


def register_tasks(
    app: procrastinate.App,
    service: ServiceProvider,
    prune: Pruner,
    settings: SyncSettings,
    clock: Clock,
    queue: str,
) -> None:
    def today() -> date:
        return clock.now().date()

    def yesterday() -> date:
        """Metrics cover complete days only, so they end with yesterday."""
        return today() - timedelta(days=1)

    @app.periodic(cron=settings.seats_cron)
    @app.task(name="sync_seats", queue=queue, queueing_lock="sync_seats")
    async def sync_seats(timestamp: int) -> None:
        await (await service()).sync_seats()

    @app.periodic(cron=settings.budgets_cron)
    @app.task(name="sync_budgets", queue=queue, queueing_lock="sync_budgets")
    async def sync_budgets(timestamp: int) -> None:
        await (await service()).sync_budgets()

    @app.periodic(cron=settings.credits_cron)
    @app.task(name="sync_credits", queue=queue, queueing_lock="sync_credits")
    async def sync_credits(timestamp: int) -> None:
        await (await service()).sync_credits(recent_days(today(), settings.credits_lookback_days))

    @app.periodic(cron=settings.metrics_cron)
    @app.task(name="sync_metrics", queue=queue, queueing_lock="sync_metrics")
    async def sync_metrics(timestamp: int) -> None:
        await (await service()).sync_metrics(recent_days(yesterday(), settings.metrics_lookback_days))

    @app.periodic(cron=settings.recover_stalled_cron)
    @app.task(name="recover_stalled_jobs", queue=queue, queueing_lock="recover_stalled_jobs", priority=STALLED_PRIORITY)
    async def recover_stalled(timestamp: int) -> None:
        await recover_stalled_jobs(app, queue)

    @app.periodic(cron=settings.prune_cron)
    @app.task(name="prune_history", queue=queue, queueing_lock="prune_history")
    async def prune_history(timestamp: int) -> None:
        keep = timedelta(days=settings.history_retention_days)
        rows = await prune(clock.now() - keep)
        await app.job_manager.delete_old_jobs(
            nb_hours=int(keep.total_seconds() // 3600),
            queue=queue,
            include_failed=True,
            include_cancelled=True,
            include_aborted=True,
        )
        log.info("pruned %d sync runs and requests older than %d days", rows, settings.history_retention_days)

    # Per-day jobs come from the catch-up and the backfill; retry transient GitHub errors with backoff.
    @app.task(name="sync_credits_month", queue=queue, retry=HISTORY_RETRY, priority=HISTORY_PRIORITY)
    async def sync_credits_month(days: list[str]) -> None:
        await (await service()).sync_credits_history([date.fromisoformat(day) for day in days])

    @app.task(name="sync_metrics_day", queue=queue, retry=HISTORY_RETRY, priority=HISTORY_PRIORITY)
    async def sync_metrics_day(day: str) -> None:
        await (await service()).sync_metrics([date.fromisoformat(day)])

    async def try_defer(task: procrastinate.tasks.Task[..., Any, ...], lock: str, **kwargs: Any) -> bool:
        """Queue one job, unless one with the same lock is still waiting (say, after a restart)."""
        try:
            await task.configure(queueing_lock=f"{task.name}:{lock}").defer_async(**kwargs)
        except AlreadyEnqueued:
            return False
        return True

    async def defer_metrics_days(days: Iterable[date]) -> int:
        """Metrics history goes one job per day."""
        return sum([await try_defer(sync_metrics_day, f"{day}", day=day.isoformat()) for day in days])

    async def defer_credit_months(days: Iterable[date]) -> int:
        """Credit history goes one job per month (see ``sync_credits_history``)."""
        return sum(
            [
                await try_defer(sync_credits_month, f"{month[0]:%Y-%m}", days=[day.isoformat() for day in month])
                for month in by_month(days)
            ]
        )

    async def seats_and_budgets() -> None:
        # Seats first, so per-user calls know who to ask about.
        await (await service()).sync_seats()
        await (await service()).sync_budgets()

    @app.task(name="catch_up", queue=queue, queueing_lock="catch_up")
    async def catch_up() -> None:
        """Fetch every day within GitHub's retention that isn't synced yet, newest first.

        The first start loads all available history; later starts only fill gaps, e.g. while
        the worker was down. Days synced before they settled (see ``days_to_catch_up``) count
        as gaps too.
        """
        await seats_and_budgets()
        svc = await service()

        async def queue_missing() -> int:
            credits = await svc.days_to_catch_up(
                SyncJob.CREDITS, recent_days(today(), settings.backfill_credits_days), settings.credits_lookback_days
            )
            metrics = await svc.days_to_catch_up(
                SyncJob.METRICS,
                recent_days(yesterday(), settings.backfill_metrics_days),
                settings.metrics_lookback_days,
            )
            months, days = await defer_credit_months(credits), await defer_metrics_days(metrics)
            log.info(
                "catch-up: queued %d credit months (%d days) and %d of %d metrics days",
                months,
                len(credits),
                days,
                len(metrics),
            )
            return months + days

        await svc.queue_history(queue_missing)

    @app.task(name="backfill", queue=queue, queueing_lock="backfill")
    async def backfill(credits_days: int | None = None, metrics_days: int | None = None) -> None:
        """Re-fetch whole windows, synced or not (``copilot-metrics backfill``), newest first."""
        await seats_and_budgets()

        async def queue_all() -> int:
            months = await defer_credit_months(
                reversed(recent_days(today(), credits_days or settings.backfill_credits_days))
            )
            days = await defer_metrics_days(
                reversed(recent_days(yesterday(), metrics_days or settings.backfill_metrics_days))
            )
            return months + days

        await (await service()).queue_history(queue_all)
