"""Credit sync: who gets asked about which day, and that every seat holder's day is replaced."""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from copilot_metrics.shared.kernel import SyncJob
from copilot_metrics.sync.domain import CreditUsageItem, ModelCredits, SeatHolder, by_month
from copilot_metrics.sync.ports import GitHubOrg, RunLog, SyncStore
from copilot_metrics.sync.service import SyncService

from ..clock import FixedClock

NOW = datetime(2026, 11, 13, 8, tzinfo=UTC)
ALICE, BOB, CAROL = (
    SeatHolder(user_id=1, login="alice"),
    SeatHolder(user_id=2, login="bob"),
    SeatHolder(user_id=3, login="carol"),
)
OCT_1, OCT_4, NOV_2 = date(2026, 10, 1), date(2026, 10, 4), date(2026, 11, 2)  # Oct 4: no org usage


def item(qty: float) -> CreditUsageItem:
    return CreditUsageItem(model="GPT-5.5", sku="ai_credits", gross_quantity=qty)


class FakeGitHub:
    """Alice used credits in October and November, Bob only in November, Carol never."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.in_flight = self.max_in_flight = 0

    async def _call(self, *key: Any) -> None:
        self.calls.append(key)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0)
        self.in_flight -= 1

    async def monthly_credit_usage(self, year: int, month: int, login: str | None = None) -> list[CreditUsageItem]:
        await self._call("month", month, login)
        used = {10: {"alice"}, 11: {"alice", "bob"}}[month]
        return [item(10)] if login in used else []

    async def credit_usage(self, day: date, login: str | None = None) -> list[CreditUsageItem]:
        await self._call("day", day, login)
        if day == OCT_4:
            return []
        return [item(1)] if login in (None, "alice", "bob") else []


class FakeStore:
    def __init__(self) -> None:
        self.days: dict[date, tuple[set[int], dict[int, list[ModelCredits]]]] = {}
        self.synced: list[date] = []

    async def seat_holders_since(self, day: date) -> list[SeatHolder]:
        return [ALICE, BOB, CAROL]

    async def replace_day_credits(
        self,
        day: date,
        holders: Sequence[SeatHolder],
        user_rows: Mapping[int, list[ModelCredits]],
        org_rows: list[ModelCredits],
    ) -> int:
        self.days[day] = ({h.user_id for h in holders}, dict(user_rows))
        return sum(map(len, user_rows.values())) + len(org_rows)

    async def mark_day_synced(self, job: SyncJob, day: date, at: datetime) -> None:
        self.synced.append(day)


class FakeRuns:
    async def start(self, job: SyncJob, at: datetime) -> int:
        return 1

    async def finish(self, *args: Any) -> None:
        pass


def service(github: FakeGitHub, store: FakeStore, parallel: int = 2) -> SyncService:
    return SyncService(
        cast(GitHubOrg, github), cast(SyncStore, store), cast(RunLog, FakeRuns()), FixedClock(NOW), parallel
    )


async def test_history_asks_only_holders_with_usage_that_month_and_skips_days_without_org_usage() -> None:
    github, store = FakeGitHub(), FakeStore()

    await service(github, store).sync_credits_history([NOV_2, OCT_4, OCT_1])

    day_calls = {(d, login) for kind, d, login in github.calls if kind == "day"}
    assert day_calls == {
        (NOV_2, None), (NOV_2, "alice"), (NOV_2, "bob"),
        (OCT_4, None),  # nothing org-wide: no one asked
        (OCT_1, None), (OCT_1, "alice"),
    }  # fmt: skip
    assert sorted(m for kind, m, _ in github.calls if kind == "month") == [10, 10, 10, 11, 11, 11]
    # Every holder's day is replaced, asked or not, so stale rows can't survive a re-sync.
    assert all(holders == {1, 2, 3} for holders, _ in store.days.values())
    assert set(store.days[OCT_1][1]) == {1}
    # Nothing org-wide may mean GitHub dropped the day: its stored rows are left untouched.
    assert OCT_4 not in store.days
    assert store.synced == [NOV_2, OCT_4, OCT_1]


async def test_recent_sync_asks_every_holder_in_parallel_within_the_limit() -> None:
    github, store = FakeGitHub(), FakeStore()

    await service(github, store, parallel=2).sync_credits([NOV_2])

    assert {login for _, _, login in github.calls} == {None, "alice", "bob", "carol"}
    assert github.max_in_flight == 2
    assert set(store.days[NOV_2][1]) == {1, 2, 3}


def test_days_group_by_month_in_order() -> None:
    assert by_month([NOV_2, OCT_4, OCT_1]) == [[NOV_2], [OCT_4, OCT_1]]


class BobFails(FakeGitHub):
    """Bob's call fails at once; Carol's would take long."""

    def __init__(self) -> None:
        super().__init__()
        self.carol_cancelled = False

    async def credit_usage(self, day: date, login: str | None = None) -> list[CreditUsageItem]:
        if login == "bob":
            raise RuntimeError("GitHub said no")
        if login == "carol":
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.carol_cancelled = True
                raise
        return [item(1)]


async def test_one_failing_call_cancels_the_others_and_its_error_is_raised() -> None:
    github, store = BobFails(), FakeStore()

    with pytest.raises(RuntimeError, match="GitHub said no"):
        await service(github, store, parallel=3).sync_credits([NOV_2])

    assert github.carol_cancelled  # not left running in the background
    assert NOV_2 not in store.days
