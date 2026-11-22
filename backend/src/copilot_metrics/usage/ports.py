from abc import ABC, abstractmethod
from datetime import date

from copilot_metrics.shared.kernel import Period, Viewer
from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.usage.domain import (
    ActivityBreakdown,
    ActivityDayRow,
    Budget,
    CreditRow,
    JobStatus,
    MemberProfile,
    MemberRow,
    ModelCallsRow,
    OrgReportDay,
    OrgReportUse,
    SeatCost,
    SeatSummary,
    TeamModelCredits,
    UserBudget,
)


class UsageReader(ABC):
    """Read-only access to the synced data, always as a given viewer (row-level security)."""

    @abstractmethod
    async def user_credits(self, viewer: Viewer, user_id: int, period: Period) -> list[CreditRow]: ...

    @abstractmethod
    async def org_credits(self, viewer: Viewer, period: Period) -> list[CreditRow]: ...

    @abstractmethod
    async def user_activity(self, viewer: Viewer, user_id: int, period: Period) -> list[UserDayMetrics]: ...

    @abstractmethod
    async def model_calls(self, viewer: Viewer, period: Period, user_id: int | None = None) -> list[ModelCallsRow]:
        """Requests and tokens per day, client and model as GitHub reports them.

        ``user_id`` narrows to one person, else everyone RLS lets through."""

    @abstractmethod
    async def activity_days(
        self, viewer: Viewer, first: date, last: date, team: str | None = None
    ) -> list[ActivityDayRow]:
        """Every stored person-day from ``first`` through ``last`` (RLS: members get only their own)."""

    @abstractmethod
    async def activity_breakdown(self, viewer: Viewer, period: Period, team: str | None = None) -> ActivityBreakdown:
        """Per-feature, per-language and per-editor totals with distinct people, from the raw metrics."""

    @abstractmethod
    async def metrics_through(self, viewer: Viewer) -> date | None: ...

    @abstractmethod
    async def org_report_days(self, viewer: Viewer, period: Period) -> list[OrgReportDay]: ...

    @abstractmethod
    async def org_report_use(self, viewer: Viewer, period: Period) -> OrgReportUse:
        """Interactions per MCP server and custom agent, from the raw org reports."""

    @abstractmethod
    async def seat_summary(self, viewer: Viewer) -> SeatSummary | None: ...

    @abstractmethod
    async def user_budgets(self, viewer: Viewer, user_id: int | None = None) -> list[UserBudget]:
        """Per-person budgets (RLS: members only ever get their own); ``user_id`` narrows to one person."""

    @abstractmethod
    async def org_budgets(self, viewer: Viewer) -> list[Budget]: ...

    @abstractmethod
    async def seat_cost(self, viewer: Viewer, month: date) -> SeatCost | None: ...

    @abstractmethod
    async def members(self, viewer: Viewer, period: Period) -> list[MemberRow]: ...

    @abstractmethod
    async def team_models(self, viewer: Viewer, period: Period) -> list[TeamModelCredits]: ...

    @abstractmethod
    async def member_profile(self, viewer: Viewer, login: str) -> MemberProfile | None: ...

    @abstractmethod
    async def jobs(self, viewer: Viewer) -> list[JobStatus]: ...
