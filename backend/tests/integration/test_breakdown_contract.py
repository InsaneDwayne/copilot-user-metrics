"""The read side's contract with the stored records.

The breakdown queries read field names straight out of ``user_activity.raw`` and count a
missing field as zero. Stored here is a record with every field the model knows, each above
zero; if a query reads a name the model doesn't have (a typo, or only one side of a rename),
its column comes back zero and this fails.
"""

from datetime import date
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.kernel import Period, Role, Viewer
from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresSyncStore
from copilot_metrics.usage.adapters.outbound.postgres.repository import PostgresUsageReader

SAMPLE = Path(__file__).parent.parent / "fixtures" / "users-1-day.ndjson"
ADMIN = Viewer(user_id=3, login="owner", role=Role.ADMIN)
PERIOD = Period(start=date(2026, 11, 1), end=date(2026, 11, 30))


def zero_columns(rows: list[BaseModel]) -> list[str]:
    return [
        f"{type(row).__name__}.{name}"
        for row in rows
        for name, value in row.model_dump().items()
        if isinstance(value, int) and not isinstance(value, bool) and value <= 0
    ]


async def stored_sample(worker_engine: AsyncEngine) -> None:
    record = UserDayMetrics.model_validate_json(SAMPLE.read_text())
    assert await PostgresSyncStore(worker_engine).upsert_activity([record]) == 1


async def test_every_breakdown_column_is_fed(worker_engine: AsyncEngine, api_engine: AsyncEngine) -> None:
    await stored_sample(worker_engine)

    breakdown = await PostgresUsageReader(api_engine).activity_breakdown(ADMIN, PERIOD)

    groups: dict[str, list[BaseModel]] = {
        "features": list(breakdown.features),
        "languages": list(breakdown.languages),
        "ides": list(breakdown.ides),
        "model_features": list(breakdown.model_features),
        "language_models": list(breakdown.language_models),
        "skills": list(breakdown.skills),
    }
    assert [name for name, rows in groups.items() if len(rows) != 1] == []
    assert zero_columns([row for rows in groups.values() for row in rows]) == []


async def test_every_model_call_column_is_fed(worker_engine: AsyncEngine, api_engine: AsyncEngine) -> None:
    await stored_sample(worker_engine)

    rows = await PostgresUsageReader(api_engine).model_calls(ADMIN, PERIOD)

    assert [(r.client, r.model) for r in rows] == [("vscode", "claude-sonnet-4.6")]
    assert zero_columns(list(rows)) == []
