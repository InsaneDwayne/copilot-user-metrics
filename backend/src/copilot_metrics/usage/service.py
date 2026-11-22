"""Read-side use cases. Every method takes the viewer; the subject is explicit."""

from datetime import date, timedelta

from copilot_metrics.shared.errors import NotFound
from copilot_metrics.shared.kernel import Clock, PageRequest, Period, Viewer
from copilot_metrics.usage import domain
from copilot_metrics.usage.ports import UsageReader


class MemberNotFound(NotFound):
    code = "member_not_found"
    default_message = "No seat on record for this login"


class UsageService:
    def __init__(self, reader: UsageReader, clock: Clock, stale_after: timedelta) -> None:
        self._reader = reader
        self._clock = clock
        self._stale_after = stale_after

    @property
    def _today(self) -> date:
        return self._clock.now().date()

    # -- one person (the viewer themself, or a member an admin opened) ---------

    async def summary(self, viewer: Viewer, user_id: int, period: Period) -> domain.UsageSummary:
        rows = await self._reader.user_credits(viewer, user_id, period)
        budgets = await self._reader.user_budgets(viewer, user_id)
        # The budget GitHub applies to this person (personal, else the org-wide one), with their
        # own consumption against it. RLS limits members to their own row, so this is never
        # someone else's budget; the org's total consumption stays in org_summary (organization readers and admins).
        budget = budgets[0].budget if budgets else None
        return domain.summarize(rows, period, self._today, budget)

    async def models(self, viewer: Viewer, user_id: int, period: Period) -> list[domain.ModelUsage]:
        return domain.model_breakdown(await self._reader.user_credits(viewer, user_id, period))

    async def model_tokens(self, viewer: Viewer, user_id: int, period: Period) -> list[domain.ModelTokens]:
        return domain.model_tokens(await self._reader.model_calls(viewer, period, user_id))

    async def daily(self, viewer: Viewer, user_id: int, period: Period) -> list[domain.DailyModelUsage]:
        return domain.daily_line_items(await self._reader.user_credits(viewer, user_id, period))

    async def activity(self, viewer: Viewer, user_id: int, period: Period) -> domain.ActivitySummary:
        days = await self._reader.user_activity(viewer, user_id, period)
        through = await self._reader.metrics_through(viewer)
        return domain.summarize_activity(days, period, self._today, through)

    # -- org totals (organization readers and admins) ---------------------------

    async def org_summary(self, viewer: Viewer, period: Period) -> domain.OrgSummary:
        rows = await self._reader.org_credits(viewer, period)
        seats = await self._reader.seat_summary(viewer)
        budgets = await self._reader.org_budgets(viewer)
        seat_cost = await self._reader.seat_cost(viewer, period.start.replace(day=1))
        return domain.org_summary(rows, period, self._today, seats, budgets, seat_cost)

    async def sync_status(self, viewer: Viewer) -> domain.SyncStatus:
        jobs = await self._reader.jobs(viewer)
        return domain.sync_status(jobs, self._clock.now(), self._stale_after, include_jobs=viewer.is_admin)

    # -- admin console (organization readers and admins) ------------------------

    async def org_models(self, admin: Viewer, period: Period) -> list[domain.ModelUsage]:
        return domain.model_breakdown(await self._reader.org_credits(admin, period))

    async def org_model_tokens(self, admin: Viewer, period: Period) -> list[domain.ModelTokens]:
        return domain.model_tokens(await self._reader.model_calls(admin, period))

    async def org_daily(self, admin: Viewer, period: Period) -> list[domain.DailyModelUsage]:
        return domain.daily_line_items(await self._reader.org_credits(admin, period))

    async def members(
        self, admin: Viewer, period: Period, query: domain.MemberQuery, request: PageRequest
    ) -> domain.MemberPage:
        # Ranking and each member's share need every seat's totals, so the page is cut after
        # aggregating: the database work is the same, but only one page leaves the API.
        return domain.member_page(await self._member_usage(admin, period), query, request)

    async def member_export(
        self, admin: Viewer, period: Period, query: domain.MemberQuery
    ) -> list[domain.MemberExportRow]:
        """Every member matching the filters, in the list's order, unpaged."""
        return domain.member_export(domain.filter_members(await self._member_usage(admin, period), query))

    async def _member_usage(self, admin: Viewer, period: Period) -> list[domain.MemberUsage]:
        rows = await self._reader.members(admin, period)
        budgets = await self._reader.user_budgets(admin)
        return domain.member_usage(rows, budgets, period, self._today)

    async def adoption(self, admin: Viewer, period: Period, team: str | None = None) -> domain.OrgAdoption:
        """The org's adoption, or one team's: its members' activity on the days they were in it."""
        first = period.start - timedelta(days=domain.LOOKBACK_DAYS)
        days = await self._reader.activity_days(admin, first, period.end, team)
        breakdown = await self._reader.activity_breakdown(admin, period, team)
        members = await self._reader.members(admin, period)
        if team is not None:
            members = [m for m in members if team in m.teams]
        through = await self._reader.metrics_through(admin)
        return domain.org_adoption(days, breakdown, members, period, self._today, through)

    async def org_report(self, admin: Viewer, period: Period) -> domain.OrgReport:
        days = await self._reader.org_report_days(admin, period)
        return domain.org_report(days, await self._reader.org_report_use(admin, period), period)

    async def teams(self, admin: Viewer, period: Period) -> list[domain.TeamUsage]:
        rows = await self._reader.members(admin, period)
        team_models = await self._reader.team_models(admin, period)
        return domain.team_usage(rows, team_models, self._clock.now())

    async def seats(self, admin: Viewer, request: PageRequest, idle_after_days: int) -> domain.SeatOverview:
        cycle = Period.cycle_of(self._today)
        rows = await self._reader.members(admin, cycle)
        seat_cost = await self._reader.seat_cost(admin, cycle.start)
        return domain.seat_overview(rows, self._clock.now(), seat_cost, request, idle_after_days)

    async def idle_seat_export(self, admin: Viewer, idle_after_days: int) -> list[domain.IdleSeatExportRow]:
        """Every idle seat, in the Seats page's order, unpaged."""
        rows = await self._reader.members(admin, Period.cycle_of(self._today))
        return domain.idle_seat_export(domain.idle_seats(rows, self._clock.now(), idle_after_days))

    async def open_member(self, admin: Viewer, login: str) -> domain.MemberProfile:
        """Resolve a member for an admin drill-down."""
        profile = await self._reader.member_profile(admin, login)
        if profile is None:
            raise MemberNotFound
        return profile
