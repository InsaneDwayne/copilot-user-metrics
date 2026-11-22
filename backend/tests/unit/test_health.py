"""Health checks: /healthz reaches the database, the worker's heartbeat reports failing syncs."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from copilot_metrics.shared.adapters.inbound.http.router import PublicConfig, build_system_router
from copilot_metrics.shared.kernel import SyncJob
from copilot_metrics.sync.adapters.inbound.jobs import heartbeat as hb
from copilot_metrics.sync.adapters.inbound.jobs.heartbeat import Heartbeat, problem, read_heartbeat

from ..clock import FixedClock

NOW = datetime(2026, 11, 19, 8, tzinfo=UTC)


async def _healthz(ping_ok: bool) -> httpx.Response:
    async def ping() -> None:
        if not ping_ok:
            raise ConnectionError("db down")

    app = FastAPI()
    app.include_router(build_system_router(PublicConfig(org="acme", session_max_age_hours=4), ping))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        return await http.get("/healthz")


async def test_healthz_is_ok_while_the_database_answers() -> None:
    response = await _healthz(ping_ok=True)
    assert (response.status_code, response.text) == (200, "ok")


async def test_healthz_is_503_when_the_database_does_not() -> None:
    response = await _healthz(ping_ok=False)
    assert response.status_code == 503
    assert "db down" not in response.text


def test_a_fresh_heartbeat_without_failing_jobs_is_healthy() -> None:
    assert problem(Heartbeat(at=NOW - timedelta(seconds=40), failing={}), NOW) is None


@pytest.mark.parametrize(
    ("heartbeat", "reason"),
    [
        (None, "no heartbeat yet"),
        (Heartbeat(at=NOW - timedelta(minutes=5), failing={}), "last heartbeat 300 s ago"),
        (Heartbeat(at=NOW, failing={SyncJob.CREDITS: 4}), "failing: sync-credits (4x since its last success)"),
    ],
)
def test_unhealthy_heartbeats(heartbeat: Heartbeat | None, reason: str) -> None:
    assert problem(heartbeat, NOW) == reason


def test_a_missing_or_garbled_heartbeat_file_reads_as_none(tmp_path: Path) -> None:
    path = tmp_path / "beat.json"
    assert read_heartbeat(path) is None
    path.write_text("{not json")
    assert read_heartbeat(path) is None


class FakeRuns:
    def __init__(self, *answers: dict[SyncJob, int] | Exception) -> None:
        self.answers = list(answers)

    async def failures_since_success(self) -> dict[SyncJob, int]:
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


async def test_beat_writes_failing_jobs_and_alerts_once_per_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "beat.json"
    runs = FakeRuns(
        {SyncJob.CREDITS: 2},  # below the threshold
        {SyncJob.CREDITS: 3, SyncJob.SEATS: 1},  # alert
        {SyncJob.CREDITS: 4},  # still failing: no second alert
        ConnectionError("db down"),  # nothing written
        {},  # recovered
    )
    beats: list[Heartbeat | None] = []

    async def tick(_: float) -> None:
        beats.append(read_heartbeat(path))
        if not runs.answers:
            raise asyncio.CancelledError

    monkeypatch.setattr(f"{hb.__name__}.asyncio.sleep", tick)
    caplog.set_level(logging.INFO, logger=hb.__name__)
    with pytest.raises(asyncio.CancelledError):
        await hb.beat(runs, FixedClock(NOW), alert_after=3, path=path)  # type: ignore[arg-type]

    assert [b.failing if b else None for b in beats] == [
        {},
        {SyncJob.CREDITS: 3},
        {SyncJob.CREDITS: 4},
        {SyncJob.CREDITS: 4},  # unchanged file: it goes stale
        {},
    ]
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == [
        "sync-credits has failed 3 times since its last success; see the Sync page",
        "heartbeat: cannot read the sync runs",
    ]
    assert "sync-credits is no longer failing" in caplog.text
