"""Composition root of the sync worker (the only process holding the App key).

``create_worker(settings)`` wires everything; nothing happens at import time.
Start the worker with ``copilot-metrics worker``. ``app`` stays importable for
procrastinate's own CLI, e.g. ``procrastinate --app=copilot_metrics.worker.app defer backfill``;
it is built from the environment on first access.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from functools import cache

import httpx
import procrastinate
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.settings import Settings, get_settings
from copilot_metrics.shared.adapters.outbound.github.http_client import github_client
from copilot_metrics.shared.adapters.outbound.postgres.engine import create_engine
from copilot_metrics.shared.kernel import SystemClock
from copilot_metrics.sync.adapters.inbound.jobs.heartbeat import beat
from copilot_metrics.sync.adapters.inbound.jobs.requests import apply_requests
from copilot_metrics.sync.adapters.inbound.jobs.tasks import register_tasks
from copilot_metrics.sync.adapters.outbound.github.org_client import AppTokenProvider, GitHubOrgClient
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresRunLog, PostgresSyncStore
from copilot_metrics.sync.adapters.outbound.postgres.requests import CHANNEL, PostgresRequestInbox
from copilot_metrics.sync.adapters.outbound.procrastinate.job_queue import (
    STALLED_AFTER_SECONDS,
    ProcrastinateJobQueue,
    recover_stalled_jobs,
)
from copilot_metrics.sync.service import SyncRequestHandler, SyncService

log = logging.getLogger(__name__)


class SyncRuntime:
    """Builds the SyncService on first use, inside the worker's event loop."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._service: SyncService | None = None
        self._engine: AsyncEngine | None = None
        self._clients: list[httpx.AsyncClient] = []

    def _database(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_engine(self._settings.require_worker().database_url, pool_size=2)
        return self._engine

    async def service(self) -> SyncService:
        if self._service is None:
            s = self._settings
            app_id, private_key = s.require_app_credentials()
            api = github_client(s.github)
            downloads = httpx.AsyncClient(timeout=s.github.timeout_seconds, follow_redirects=True)
            self._clients = [api, downloads]
            github = GitHubOrgClient(s.github, AppTokenProvider(s.github, app_id, private_key, api), api, downloads)
            self._service = SyncService(
                github,
                PostgresSyncStore(self._database()),
                PostgresRunLog(self._database()),
                SystemClock(),
                parallel_requests=s.sync.parallel_requests,
            )
        return self._service

    async def prune(self, before: datetime) -> int:
        """Drop finished sync runs and handled admin requests from before ``before``."""
        engine = self._database()
        clock = SystemClock()
        return await PostgresRunLog(engine).prune(before) + await PostgresRequestInbox(engine, clock).prune(before)

    async def close(self) -> None:
        for client in self._clients:
            await client.aclose()
        if self._engine is not None:
            await self._engine.dispose()


class Worker:
    """The procrastinate app with the sync tasks registered, and how to run it."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._worker = settings.require_worker()
        self.runtime = SyncRuntime(settings)
        self.app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=str(self._worker.database_url)))
        register_tasks(
            self.app, self.runtime.service, self.runtime.prune, settings.sync, SystemClock(), queue=self._worker.queue
        )

    async def run(self) -> None:
        settings, worker = self._settings, self._worker
        settings.require_app_credentials()  # fail fast, before taking jobs
        requests_engine = create_engine(worker.database_url, pool_size=1)
        clock = SystemClock()
        try:
            async with self.app.open_async():
                # Jobs the previous worker was running when it stopped; the periodic task catches
                # the ones whose worker hasn't missed enough heartbeats yet.
                await recover_stalled_jobs(self.app, worker.queue)
                # Their sync_run rows still say "running": close them, unless another worker is
                # alive and may be the one running them.
                if closed := await PostgresRunLog(requests_engine).close_interrupted(
                    clock.now(), timedelta(seconds=STALLED_AFTER_SECONDS)
                ):
                    log.warning("closed %d sync run(s) a stopped worker left running", closed)
                if settings.sync.catch_up_on_start:
                    await self.defer_catch_up()
                # Run/stop from the admin console, applied alongside the jobs (even while one is busy).
                requests = asyncio.create_task(
                    apply_requests(
                        str(worker.database_url),
                        CHANNEL,
                        PostgresRequestInbox(requests_engine, clock),
                        SyncRequestHandler(ProcrastinateJobQueue(self.app, clock)),
                    )
                )
                # The container's health check reads what this writes (see heartbeat.py).
                heartbeat = asyncio.create_task(
                    beat(PostgresRunLog(requests_engine), clock, settings.sync.alert_after_failures)
                )
                try:
                    await self.app.run_worker_async(queues=[worker.queue], concurrency=worker.concurrency)
                finally:
                    requests.cancel()
                    heartbeat.cancel()
                    await asyncio.gather(requests, heartbeat, return_exceptions=True)
        finally:
            await requests_engine.dispose()
            await self.runtime.close()

    async def defer_catch_up(self) -> None:
        """Queue the sync of every day GitHub still has but the database doesn't."""
        try:
            job_id = await self.app.configure_task("catch_up").defer_async()
            log.info("catch-up with GitHub deferred as job %s", job_id)
        except AlreadyEnqueued:
            log.info("catch-up with GitHub already queued")

    async def defer_backfill(self, credits_days: int | None, metrics_days: int | None) -> int:
        async with self.app.open_async():
            job_id = await self.app.configure_task("backfill").defer_async(
                credits_days=credits_days, metrics_days=metrics_days
            )
        log.info("backfill deferred as job %s", job_id)
        return job_id


def create_worker(settings: Settings | None = None) -> Worker:
    """The worker for ``settings`` (default: from the environment)."""
    return Worker(settings or get_settings())


@cache
def _cli_app() -> procrastinate.App:
    return create_worker().app


def __getattr__(name: str) -> procrastinate.App:
    """``copilot_metrics.worker.app`` for procrastinate's CLI, built on first access."""
    if name == "app":
        return _cli_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(create_worker(settings).run())


if __name__ == "__main__":
    main()
