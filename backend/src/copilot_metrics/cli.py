"""``copilot-metrics`` command: one image, several entry points."""

import argparse
import asyncio
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _api(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "copilot_metrics.api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        proxy_headers=True,
    )


def _worker(_: argparse.Namespace) -> None:
    from copilot_metrics.worker import main

    main()


def _migrate(args: argparse.Namespace) -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), args.revision)


def _backfill(args: argparse.Namespace) -> None:
    from copilot_metrics.worker import create_worker

    job_id = asyncio.run(create_worker().defer_backfill(args.credits_days, args.metrics_days))
    print(f"Backfill deferred (job {job_id}). The worker will pick it up.")


def _healthcheck(_: argparse.Namespace) -> None:
    from datetime import UTC, datetime

    from copilot_metrics.sync.adapters.inbound.jobs.heartbeat import problem, read_heartbeat

    if reason := problem(read_heartbeat(), datetime.now(UTC)):
        raise SystemExit(f"unhealthy: {reason}")
    print("ok")


def main() -> None:
    parser = argparse.ArgumentParser(prog="copilot-metrics")
    # Release images get the version at build time (Dockerfile); anything else is a dev build.
    version = os.environ.get("COPILOT_METRICS_VERSION") or "dev"
    parser.add_argument("--version", action="version", version=f"%(prog)s {version}")
    commands = parser.add_subparsers(required=True)

    api = commands.add_parser("api", help="run the dashboard API")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8000)
    api.add_argument("--reload", action="store_true")
    api.set_defaults(run=_api)

    commands.add_parser("worker", help="run the sync worker").set_defaults(run=_worker)
    commands.add_parser(
        "healthcheck", help="exit 1 unless the worker in this container is alive and no sync job keeps failing"
    ).set_defaults(run=_healthcheck)

    migrate = commands.add_parser("migrate", help="apply database migrations (owner role)")
    migrate.add_argument("revision", nargs="?", default="head")
    migrate.set_defaults(run=_migrate)

    backfill = commands.add_parser(
        "backfill", help="re-fetch all history, synced or not (the worker catches up on start anyway)"
    )
    backfill.add_argument("--credits-days", type=int)
    backfill.add_argument("--metrics-days", type=int)
    backfill.set_defaults(run=_backfill)

    args = parser.parse_args()
    args.run(args)
