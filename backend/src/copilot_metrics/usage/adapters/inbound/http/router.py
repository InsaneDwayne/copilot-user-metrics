"""Inbound HTTP adapter for the read side.

``/api/me/*`` takes no login at all - the subject is the session's own user.
``/api/admin/members/{login}/*`` is the only place a login comes from the URL,
and it requires an organization reader or admin.
"""

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from copilot_metrics.shared.adapters.inbound.http.csv_response import CSV, csv_response
from copilot_metrics.shared.kernel import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Clock, PageRequest, Period, Viewer
from copilot_metrics.usage import domain
from copilot_metrics.usage.service import UsageService


def build_usage_router(
    *,
    service: UsageService,
    seat_holder: Callable[..., Any],
    org_member: Callable[..., Any],
    org_reader: Callable[..., Any],
    clock: Clock,
) -> APIRouter:
    """``seat_holder``, ``org_member`` and ``org_reader`` are FastAPI dependencies resolving to the ``Viewer``.

    Every ``/api/admin/*`` route here only reads, so organization readers and admins may use all of them.
    """

    def period(
        start: Annotated[date | None, Query(alias="from")] = None,
        end: Annotated[date | None, Query(alias="to")] = None,
    ) -> Period:
        """``?from=&to=`` (inclusive, UTC). Defaults to the current billing cycle."""
        current = Period.cycle_of(clock.now().date())
        return Period.between(start or current.start, end or current.end)

    def page_request(
        page: Annotated[int, Query(ge=1, description="1-based; past the last page answers with the last page")] = 1,
        size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    ) -> PageRequest:
        return PageRequest(page=page, size=size)

    def member_query(
        team: str | None = None,
        q: Annotated[str | None, Query(max_length=100, description="Part of the login, any case")] = None,
        segment: Annotated[
            domain.ActivitySegment | None, Query(description="none: no active day, occasional: 1-6, regular: 7+")
        ] = None,
        sort: domain.MemberSort = domain.MemberSort.CREDITS,
    ) -> domain.MemberQuery:
        return domain.MemberQuery(team=team or None, login=q or None, segment=segment, sort=sort)

    IdleDays = Annotated[int, Query(ge=1, le=365, description="A seat is idle after this many days without activity")]

    SeatHolder = Annotated[Viewer, Depends(seat_holder)]
    OrgMember = Annotated[Viewer, Depends(org_member)]
    OrgReader = Annotated[Viewer, Depends(org_reader)]
    InPeriod = Annotated[Period, Depends(period)]
    Paged = Annotated[PageRequest, Depends(page_request)]
    MemberFilter = Annotated[domain.MemberQuery, Depends(member_query)]

    me = APIRouter(prefix="/api/me", tags=["me"])

    @me.get("/summary")
    async def my_summary(viewer: SeatHolder, p: InPeriod) -> domain.UsageSummary:
        return await service.summary(viewer, viewer.user_id, p)

    @me.get("/models")
    async def my_models(viewer: SeatHolder, p: InPeriod) -> list[domain.ModelUsage]:
        return await service.models(viewer, viewer.user_id, p)

    @me.get("/model-tokens")
    async def my_model_tokens(viewer: SeatHolder, p: InPeriod) -> list[domain.ModelTokens]:
        """Model calls and prompt/output tokens per day and model, from the usage metrics."""
        return await service.model_tokens(viewer, viewer.user_id, p)

    @me.get("/daily")
    async def my_daily(viewer: SeatHolder, p: InPeriod) -> list[domain.DailyModelUsage]:
        return await service.daily(viewer, viewer.user_id, p)

    @me.get("/activity")
    async def my_activity(viewer: SeatHolder, p: InPeriod) -> domain.ActivitySummary:
        return await service.activity(viewer, viewer.user_id, p)

    org = APIRouter(prefix="/api", tags=["org"])

    @org.get("/org/summary")
    async def org_summary(viewer: OrgReader, p: InPeriod) -> domain.OrgSummary:
        """Org totals, seat cost and org budgets - organization readers and admins only."""
        return await service.org_summary(viewer, p)

    @org.get("/sync/status")
    async def sync_status(viewer: OrgMember) -> domain.SyncStatus:
        return await service.sync_status(viewer)

    admin = APIRouter(prefix="/api/admin", tags=["admin"])

    @admin.get("/models")
    async def org_models(viewer: OrgReader, p: InPeriod) -> list[domain.ModelUsage]:
        return await service.org_models(viewer, p)

    @admin.get("/model-tokens")
    async def org_model_tokens(viewer: OrgReader, p: InPeriod) -> list[domain.ModelTokens]:
        return await service.org_model_tokens(viewer, p)

    @admin.get("/daily")
    async def org_daily(viewer: OrgReader, p: InPeriod) -> list[domain.DailyModelUsage]:
        """Org-wide AI credits per day and model."""
        return await service.org_daily(viewer, p)

    @admin.get("/members")
    async def members(viewer: OrgReader, p: InPeriod, query: MemberFilter, page: Paged) -> domain.MemberPage:
        """One page of seat holders with their totals, filtered by team and login."""
        return await service.members(viewer, p, query, page)

    @admin.get("/members.csv", response_class=Response, responses=CSV)
    async def members_csv(viewer: OrgReader, p: InPeriod, query: MemberFilter) -> Response:
        """Every member matching the filters, in the list's order, as CSV."""
        rows = await service.member_export(viewer, p, query)
        return csv_response(f"copilot-members-{p.start}_{p.end}.csv", domain.MemberExportRow, rows)

    @admin.get("/adoption")
    async def adoption(
        viewer: OrgReader,
        p: InPeriod,
        team: Annotated[
            str | None, Query(max_length=100, description="One team's slug; the whole org if left out")
        ] = None,
    ) -> domain.OrgAdoption:
        """Active people over time, how often seat holders use Copilot, for what, and their adoption phases."""
        return await service.adoption(viewer, p, team or None)

    @admin.get("/org-report")
    async def org_report(viewer: OrgReader, p: InPeriod) -> domain.OrgReport:
        """GitHub's org-wide daily report: pull requests, MCP servers, custom agents, data coverage."""
        return await service.org_report(viewer, p)

    @admin.get("/teams")
    async def teams(viewer: OrgReader, p: InPeriod) -> list[domain.TeamUsage]:
        return await service.teams(viewer, p)

    @admin.get("/seats")
    async def seats(
        viewer: OrgReader, page: Paged, idle_days: IdleDays = domain.INACTIVE_AFTER.days
    ) -> domain.SeatOverview:
        """Seat counts, what idle seats cost, and one page of the seats idle for ``idle_days``+ days."""
        return await service.seats(viewer, page, idle_days)

    @admin.get("/seats/idle.csv", response_class=Response, responses=CSV)
    async def idle_seats_csv(viewer: OrgReader, idle_days: IdleDays = domain.INACTIVE_AFTER.days) -> Response:
        """Every seat idle for ``idle_days``+ days, in the Seats page's order, as CSV."""
        rows = await service.idle_seat_export(viewer, idle_days)
        return csv_response(f"copilot-idle-seats-{idle_days}d.csv", domain.IdleSeatExportRow, rows)

    async def subject(viewer: OrgReader, login: str) -> domain.MemberProfile:
        return await service.open_member(viewer, login)

    Subject = Annotated[domain.MemberProfile, Depends(subject)]

    @admin.get("/members/{login}")
    async def member(m: Subject) -> domain.MemberProfile:
        return m

    @admin.get("/members/{login}/summary")
    async def member_summary(viewer: OrgReader, m: Subject, p: InPeriod) -> domain.UsageSummary:
        return await service.summary(viewer, m.user_id, p)

    @admin.get("/members/{login}/models")
    async def member_models(viewer: OrgReader, m: Subject, p: InPeriod) -> list[domain.ModelUsage]:
        return await service.models(viewer, m.user_id, p)

    @admin.get("/members/{login}/model-tokens")
    async def member_model_tokens(viewer: OrgReader, m: Subject, p: InPeriod) -> list[domain.ModelTokens]:
        return await service.model_tokens(viewer, m.user_id, p)

    @admin.get("/members/{login}/daily")
    async def member_daily(viewer: OrgReader, m: Subject, p: InPeriod) -> list[domain.DailyModelUsage]:
        return await service.daily(viewer, m.user_id, p)

    @admin.get("/members/{login}/activity")
    async def member_activity(viewer: OrgReader, m: Subject, p: InPeriod) -> domain.ActivitySummary:
        return await service.activity(viewer, m.user_id, p)

    router = APIRouter()
    for sub in (me, org, admin):
        router.include_router(sub)
    return router
