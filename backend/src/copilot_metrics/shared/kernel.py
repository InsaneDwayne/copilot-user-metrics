"""Value objects shared by every module."""

import calendar
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from copilot_metrics.shared.errors import InvalidRequest

MAX_PERIOD_DAYS = 800
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class InvalidPeriod(InvalidRequest):
    code = "invalid_period"


# Dollars and AI credits, stored as Numeric(14, 4). Exact in Python, so sums don't drift;
# a plain number in JSON, so the frontend reads it like any other.
Amount = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
ZERO = Decimal(0)


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Role(StrEnum):
    """Resolved once at sign-in (see ``identity.domain.AccessPolicy``)."""

    ADMIN = "admin"  # org owner or admin team member (ACCESS_ADMIN_TEAMS): all org data, runs syncs
    ORG_READER = "org_reader"  # organization reader: member of an ACCESS_ORG_READER_TEAMS team, reads all org data
    MEMBER = "member"  # organization member: their own usage only
    OUTSIDER = "outsider"  # signed in, but not a member of the org

    @property
    def can_read_org(self) -> bool:
        """May read every member's usage: the admin console without the Sync page."""
        return self in (Role.ADMIN, Role.ORG_READER)


class Viewer(Frozen):
    """Who is asking. Drives row-level security in Postgres."""

    user_id: int
    login: str
    role: Role

    @property
    def is_admin(self) -> bool:
        """May control syncs (the admin console's Sync page)."""
        return self.role is Role.ADMIN

    @property
    def can_read_org(self) -> bool:
        """See ``Role.can_read_org``."""
        return self.role.can_read_org


def _period_problem(start: date, end: date) -> str | None:
    if end < start:
        return "period end is before its start"
    if (end - start).days >= MAX_PERIOD_DAYS:
        return f"period is longer than {MAX_PERIOD_DAYS} days"
    return None


class Period(Frozen):
    """An inclusive range of UTC days."""

    start: date
    end: date

    @model_validator(mode="after")
    def _check(self) -> Self:
        if problem := _period_problem(self.start, self.end):
            raise ValueError(problem)
        return self

    @classmethod
    def between(cls, start: date, end: date) -> Self:
        """Like the constructor, but an impossible range is an ``InvalidPeriod``."""
        if problem := _period_problem(start, end):
            raise InvalidPeriod(problem)
        return cls(start=start, end=end)

    @classmethod
    def cycle_of(cls, day: date) -> Self:
        """The billing cycle (calendar month, UTC) containing ``day``."""
        last = calendar.monthrange(day.year, day.month)[1]
        return cls(start=day.replace(day=1), end=day.replace(day=last))

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def each_day(self, until: date | None = None) -> Iterator[date]:
        last = min(self.end, until) if until else self.end
        day = self.start
        while day <= last:
            yield day
            day += timedelta(days=1)


class PageRequest(Frozen):
    """Which slice of a list to return: 1-based page number and rows per page."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class Page[T](Frozen):
    """One page of an ordered list, with what the caller needs to page through the rest."""

    items: list[T]
    total: int  # rows across all pages
    page: int  # 1-based; a page past the end is answered with the last page
    size: int
    pages: int  # at least 1, so an empty list is one empty page

    @classmethod
    def of(cls, rows: Sequence[T], request: PageRequest, **extra: Any) -> Self:
        """Slices ``rows``, which must already be in their final order. ``extra`` fills subclass fields."""
        pages = max(1, -(-len(rows) // request.size))
        page = min(request.page, pages)
        start = (page - 1) * request.size
        return cls(
            items=list(rows[start : start + request.size]),
            total=len(rows),
            page=page,
            size=request.size,
            pages=pages,
            **extra,
        )


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)


def recent_days(today: date, count: int) -> list[date]:
    """``count`` days ending with ``today``, oldest first."""
    return [today - timedelta(days=offset) for offset in reversed(range(count))]


# The run log's vocabulary: the sync module writes ``sync_run`` and ``sync_day``, the usage
# module reads them for the "last synced" banner and the Sync page, so both need these names.
# What an admin can run or stop, and the worker's task names, belong to the sync module alone
# (``sync.domain.control``).


class SyncJob(StrEnum):
    SEATS = "sync-seats"
    CREDITS = "sync-credits"
    METRICS = "sync-metrics"
    BUDGETS = "sync-budgets"
    HISTORY = "history"  # the catch-up and backfill runs that queue the per-month/per-day jobs


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"  # stopped from the admin console
