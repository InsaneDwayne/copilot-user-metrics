from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import date, datetime, timedelta

from copilot_metrics.shared.kernel import RunStatus, SyncJob, Viewer
from copilot_metrics.shared.metrics_record import OrgDayMetrics, UserDayMetrics
from copilot_metrics.sync.domain import (
    BudgetPage,
    BudgetRecord,
    CopilotBilling,
    CopilotSeat,
    CreditUsageItem,
    ModelCredits,
    QueuedJob,
    SeatCostRecord,
    SeatHolder,
    SyncAction,
    SyncRequest,
    SyncTarget,
    UsageSummaryItem,
    UserTeamRecord,
)


class GitHubOrg(ABC):
    """The org's Copilot data, read with the GitHub App's installation token."""

    @abstractmethod
    async def copilot_billing(self) -> CopilotBilling: ...

    @abstractmethod
    async def seats(self) -> list[CopilotSeat]: ...

    @abstractmethod
    async def credit_usage(self, day: date, login: str | None = None) -> list[CreditUsageItem]: ...

    @abstractmethod
    async def monthly_credit_usage(self, year: int, month: int, login: str | None = None) -> list[CreditUsageItem]:
        """The month's totals per model; GitHub has no per-day split in one call."""

    @abstractmethod
    async def user_metrics(self, day: date) -> list[UserDayMetrics]: ...

    @abstractmethod
    async def user_teams(self, day: date) -> list[UserTeamRecord]: ...

    @abstractmethod
    async def org_metrics(self, day: date) -> list[OrgDayMetrics]:
        """The org-wide report for ``day``: usually one record, none if GitHub has no report."""

    @abstractmethod
    async def budgets(self, user: str | None = None) -> BudgetPage:
        """All budget pages merged; with ``user``, consumed amounts are that person's."""

    @abstractmethod
    async def usage_summary(self, year: int, month: int) -> list[UsageSummaryItem]: ...


class SyncStore(ABC):
    """The only writer of usage tables. Every write is idempotent (replace or upsert)."""

    @abstractmethod
    async def save_seats(self, billing: CopilotBilling, seats: list[CopilotSeat], now: datetime) -> int: ...

    @abstractmethod
    async def seat_holders_since(self, day: date) -> list[SeatHolder]: ...

    @abstractmethod
    async def replace_day_credits(
        self,
        day: date,
        holders: Sequence[SeatHolder],
        user_rows: Mapping[int, list[ModelCredits]],
        org_rows: list[ModelCredits],
    ) -> int:
        """In one transaction, replace the day's rows of the org and of each holder (not in ``user_rows``: none)."""

    @abstractmethod
    async def upsert_activity(self, records: list[UserDayMetrics]) -> int: ...

    @abstractmethod
    async def upsert_org_activity(self, records: list[OrgDayMetrics]) -> int: ...

    @abstractmethod
    async def replace_user_teams(self, day: date, records: list[UserTeamRecord]) -> int: ...

    @abstractmethod
    async def replace_org_budgets(self, records: list[BudgetRecord], now: datetime) -> int: ...

    @abstractmethod
    async def save_user_budget(self, holder: SeatHolder, record: BudgetRecord | None, now: datetime) -> int: ...

    @abstractmethod
    async def save_seat_cost(self, record: SeatCostRecord, now: datetime) -> int: ...

    @abstractmethod
    async def mark_day_synced(self, job: SyncJob, day: date, at: datetime) -> None: ...

    @abstractmethod
    async def last_synced(self, job: SyncJob, first: date, last: date) -> dict[date, datetime]:
        """When each day between ``first`` and ``last`` was last synced (days never synced are absent)."""


class RunLog(ABC):
    @abstractmethod
    async def start(self, job: SyncJob, at: datetime) -> int: ...

    @abstractmethod
    async def finish(self, run_id: int, status: RunStatus, at: datetime, rows: int, error: str | None) -> None: ...

    @abstractmethod
    async def close_interrupted(self, at: datetime, heartbeat_within: timedelta) -> int:
        """Fail the runs still marked running, as a stopped worker leaves them; returns how many.

        Does nothing while any worker sent a heartbeat within ``heartbeat_within``: the runs may
        be its own. Call it when a worker starts, before it takes jobs.
        """

    @abstractmethod
    async def prune(self, before: datetime) -> int:
        """Delete finished runs started before ``before``, keeping each job's latest success."""

    @abstractmethod
    async def failures_since_success(self) -> dict[SyncJob, int]:
        """Per job that has failed since its latest success (or never succeeded): how often."""


class SyncRequests(ABC):
    """API side: the admins' run/stop requests (the API never touches the job queue itself)."""

    @abstractmethod
    async def request(self, admin: Viewer, target: SyncTarget, action: SyncAction) -> SyncRequest:
        """The open request for ``target`` and ``action``, or a new one that wakes the worker."""

    @abstractmethod
    async def recent(self, admin: Viewer, limit: int) -> list[SyncRequest]: ...

    @abstractmethod
    async def job_counts(self, admin: Viewer) -> dict[tuple[str, str], int]:
        """Jobs in the worker's queue by (task name, status), read-only."""


class JobQueue(ABC):
    """Worker side: the procrastinate queue."""

    @abstractmethod
    async def start(self, target: SyncTarget) -> bool:
        """Queue the target's sync now; False when one is already waiting."""

    @abstractmethod
    async def jobs(self, target: SyncTarget) -> list[QueuedJob]:
        """The target's waiting and running jobs."""

    @abstractmethod
    async def cancel(self, job_id: int) -> bool: ...

    @abstractmethod
    async def abort(self, job_id: int) -> bool: ...


RequestHandler = Callable[[SyncRequest], Awaitable[str]]


class RequestInbox(ABC):
    """Worker side: requests the API wrote and no worker has handled yet."""

    @abstractmethod
    async def handle_pending(self, handler: RequestHandler) -> int:
        """Apply ``handler`` to each open request, oldest first, and store its outcome."""

    @abstractmethod
    async def prune(self, before: datetime) -> int:
        """Delete requests handled before ``before``; open ones stay."""
