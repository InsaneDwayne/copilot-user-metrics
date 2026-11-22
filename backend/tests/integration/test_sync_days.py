"""The worker records synced days per job and reads them back."""

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.kernel import SyncJob
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresSyncStore


async def test_marks_days_and_reads_them_back_per_job(worker_engine: AsyncEngine) -> None:
    store = PostgresSyncStore(worker_engine)
    first, later = datetime(2026, 11, 3, 9, tzinfo=UTC), datetime(2026, 11, 9, 9, tzinfo=UTC)

    await store.mark_day_synced(SyncJob.CREDITS, date(2026, 11, 2), first)
    await store.mark_day_synced(SyncJob.CREDITS, date(2026, 11, 2), later)  # re-sync moves it on
    await store.mark_day_synced(SyncJob.CREDITS, date(2026, 10, 1), first)  # outside the range
    await store.mark_day_synced(SyncJob.METRICS, date(2026, 11, 2), first)  # other job

    synced = await store.last_synced(SyncJob.CREDITS, date(2026, 11, 1), date(2026, 11, 30))
    assert synced == {date(2026, 11, 2): later}
