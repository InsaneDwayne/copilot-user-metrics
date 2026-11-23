"""Write-side use cases, one per job in the architecture's job table."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import date
from functools import partial

from copilot_metrics.shared.kernel import Clock, RunStatus, SyncJob, Viewer
from copilot_metrics.sync import domain
from copilot_metrics.sync.domain import (
    SeatHolder,
    SyncAction,
    SyncTarget,
    billed_usd,
    budget_for_user,
    by_month,
    credits_by_model,
    days_to_catch_up,
    org_budgets,
    seat_cost,
    stop_outcome,
    target_queues,
)
from copilot_metrics.sync.ports import GitHubOrg, JobQueue, RunLog, SyncRequests, SyncStore

log = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self, github: GitHubOrg, store: SyncStore, runs: RunLog, clock: Clock, parallel_requests: int = 1
    ) -> None:
        self._github = github
        self._limit = asyncio.Semaphore(parallel_requests)
        self._store = store
        self._runs = runs
        self._clock = clock

    async def _tracked(self, job: SyncJob, work: Callable[[], Awaitable[int]]) -> int:
        """Record every run in sync_run - the UI's "Synced 18 min ago" and stale banner read it."""
        run_id = await self._runs.start(job, self._clock.now())
        try:
            rows = await work()
        except asyncio.CancelledError:
            # An admin stopped the job (procrastinate cancels an aborted async task).
            await asyncio.shield(
                self._runs.finish(run_id, RunStatus.ABORTED, self._clock.now(), 0, "Stopped from the admin console")
            )
            raise
        except Exception as exc:
            await self._runs.finish(
                run_id, RunStatus.FAILED, self._clock.now(), 0, f"{type(exc).__name__}: {exc}"[:2000]
            )
            raise
        await self._runs.finish(run_id, RunStatus.SUCCEEDED, self._clock.now(), rows, None)
        log.info("%s: %d rows", job, rows)
        return rows

    async def sync_seats(self) -> int:
        async def work() -> int:
            now = self._clock.now()
            billing = await self._github.copilot_billing()
            seats = await self._github.seats()
            rows = await self._store.save_seats(billing, seats, now)
            # What GitHub charges per seat this month, if its usage summary lists seats.
            cost = seat_cost(await self._github.usage_summary(now.year, now.month), now.date().replace(day=1))
            if cost is not None:
                rows += await self._store.save_seat_cost(cost, now)
            return rows

        return await self._tracked(SyncJob.SEATS, work)

    async def sync_budgets(self) -> int:
        """GitHub's Copilot budgets: the org-wide ones, and the one applying to each seat holder."""

        async def work() -> int:
            now = self._clock.now()
            # The org's paid AI credit spend this month, which its organization budgets cap.
            billed = billed_usd(await self._github.monthly_credit_usage(now.year, now.month))
            rows = await self._store.replace_org_budgets(org_budgets(await self._github.budgets(), billed), now)
            for holder in await self._store.seat_holders_since(now.date()):
                page = await self._github.budgets(user=holder.login)
                rows += await self._store.save_user_budget(holder, budget_for_user(holder.login, page), now)
            return rows

        return await self._tracked(SyncJob.BUDGETS, work)

    async def sync_credits(self, days: Sequence[date]) -> int:
        """Recent days: ask about every seat holder (in parallel), plus one org-wide call per day."""

        async def work() -> int:
            holders = await self._store.seat_holders_since(min(days))
            return sum([await self._sync_credit_day(day, holders, holders) for day in days])

        return await self._tracked(SyncJob.CREDITS, work)

    async def sync_credits_history(self, days: Sequence[date]) -> int:
        """Older days, a month at a time. GitHub only splits by day per call, so one month call
        per seat holder finds who used credits that month, and only they are asked about each day."""

        async def work() -> int:
            rows = 0
            for month_days in by_month(days):
                holders = await self._store.seat_holders_since(min(month_days))
                first = month_days[0]
                totals = await self._parallel(
                    partial(self._github.monthly_credit_usage, first.year, first.month, h.login) for h in holders
                )
                active = [h for h, items in zip(holders, totals, strict=True) if items]
                log.info(
                    "credits %s: %d of %d seat holders used credits", first.strftime("%Y-%m"), len(active), len(holders)
                )
                for day in month_days:
                    rows += await self._sync_credit_day(day, holders, active)
            return rows

        return await self._tracked(SyncJob.CREDITS, work)

    async def _sync_credit_day(self, day: date, holders: Sequence[SeatHolder], ask: Sequence[SeatHolder]) -> int:
        """Replace ``day`` for every holder; only ``ask`` can have usage.

        If GitHub has nothing for the whole org that day, nothing is written: either no one used
        credits, or GitHub no longer keeps the day. In the second case the stored rows are the only
        copy, so they must never be deleted. A day GitHub does have is replaced in full, so its
        corrections reach the database.
        """
        org_items = await self._github.credit_usage(day)
        if not org_items:
            await self._store.mark_day_synced(SyncJob.CREDITS, day, self._clock.now())
            return 0
        items = await self._parallel(partial(self._github.credit_usage, day, h.login) for h in ask)
        user_rows = {h.user_id: credits_by_model(i) for h, i in zip(ask, items, strict=True)}
        rows = await self._store.replace_day_credits(day, holders, user_rows, credits_by_model(org_items))
        await self._store.mark_day_synced(SyncJob.CREDITS, day, self._clock.now())
        return rows

    async def _parallel[T](self, calls: Iterable[Callable[[], Awaitable[T]]]) -> list[T]:
        """Run ``calls`` at once, at most ``parallel_requests`` across this service; results in order.

        If one fails, the others are cancelled and its error is raised (not an ExceptionGroup),
        so a failed run reports what went wrong, as a sequential one would.
        """

        async def limited(call: Callable[[], Awaitable[T]]) -> T:
            async with self._limit:
                return await call()

        try:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(limited(call)) for call in calls]
        except ExceptionGroup as failed:
            raise failed.exceptions[0] from None
        return [task.result() for task in tasks]

    async def sync_metrics(self, days: Sequence[date]) -> int:
        """Daily reports for complete days; links are signed and short-lived, so download at once."""

        async def work() -> int:
            rows = 0
            for day in days:
                rows += await self._store.upsert_activity(await self._github.user_metrics(day))
                rows += await self._store.replace_user_teams(day, await self._github.user_teams(day))
                rows += await self._store.upsert_org_activity(await self._github.org_metrics(day))
                await self._store.mark_day_synced(SyncJob.METRICS, day, self._clock.now())
            return rows

        return await self._tracked(SyncJob.METRICS, work)

    async def queue_history(self, defer: Callable[[], Awaitable[int]]) -> int:
        """The catch-up or a backfill: one logged run, whose rows are the jobs ``defer`` queued.

        The per-month and per-day jobs log their own runs, as credits and metrics.
        """
        return await self._tracked(SyncJob.HISTORY, defer)

    async def days_to_catch_up(self, job: SyncJob, window: Sequence[date], settle_days: int) -> list[date]:
        """Days of ``window`` not synced yet, or synced before their numbers settled; newest first."""
        if not window:
            return []
        synced = await self._store.last_synced(job, min(window), max(window))
        return days_to_catch_up(window, synced, settle_days)


# ---------------------------------------------------------------- run / stop from the admin console

RECENT_REQUESTS = 20


class SyncControlService:
    """API side of the Sync page: records requests; the worker applies them (SyncRequestHandler)."""

    def __init__(self, requests: SyncRequests) -> None:
        self._requests = requests

    async def status(self, admin: Viewer) -> domain.SyncControlStatus:
        return domain.SyncControlStatus(
            targets=target_queues(await self._requests.job_counts(admin)),
            requests=await self._requests.recent(admin, RECENT_REQUESTS),
        )

    async def request(self, admin: Viewer, target: SyncTarget, action: SyncAction) -> domain.SyncRequest:
        return await self._requests.request(admin, target, action)


class SyncRequestHandler:
    """Worker side: turns one request into queue operations and says what happened."""

    def __init__(self, queue: JobQueue) -> None:
        self._queue = queue

    async def handle(self, request: domain.SyncRequest) -> str:
        try:
            if request.action is SyncAction.RUN:
                return "Queued" if await self._queue.start(request.target) else "Already queued"
            cancelled = stopping = 0
            for job in await self._queue.jobs(request.target):
                if job.status == "todo":
                    cancelled += await self._queue.cancel(job.id)
                elif job.status == "doing":
                    stopping += await self._queue.abort(job.id)
            return stop_outcome(cancelled, stopping)
        except Exception as exc:
            log.exception("sync request %s failed", request.id)
            return f"Failed: {type(exc).__name__}: {exc}"[:500]
