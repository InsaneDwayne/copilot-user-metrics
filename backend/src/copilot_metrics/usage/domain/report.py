"""GitHub's org-wide report (organization-1-day): pull requests, MCP servers, coverage."""

from collections.abc import Iterable, Sequence
from datetime import date

from copilot_metrics.shared.kernel import Frozen, Period
from copilot_metrics.usage.domain.activity import NamedCount


class OrgReportDay(Frozen):
    """One stored day of GitHub's org-wide report. ``None``: GitHub left that number out."""

    day: date
    daily_active_users: int | None
    weekly_active_users: int | None
    monthly_active_users: int | None
    missing_telemetry_users: int | None
    below_minimum_users: int | None
    prs_created: int | None
    prs_created_by_copilot: int | None
    prs_reviewed: int | None
    prs_reviewed_by_copilot: int | None
    prs_merged: int | None
    prs_merged_created_by_copilot: int | None
    pr_suggestions: int | None
    pr_applied_suggestions: int | None
    pr_copilot_suggestions: int | None
    pr_copilot_applied_suggestions: int | None
    median_minutes_to_merge: float | None
    median_minutes_to_merge_copilot: float | None


class OrgReportUse(Frozen):
    """MCP servers and custom agents used in a period, from the raw org report."""

    mcp_servers: list[NamedCount]
    custom_agents: list[NamedCount]


class PullRequestDay(Frozen):
    day: date
    created: int
    created_by_copilot: int
    merged: int
    merged_created_by_copilot: int
    reviewed_by_copilot: int


class PullRequestTotals(Frozen):
    created: int
    created_by_copilot: int
    reviewed: int
    reviewed_by_copilot: int
    merged: int
    merged_created_by_copilot: int
    suggestions: int  # review suggestions on pull requests
    applied_suggestions: int
    copilot_suggestions: int  # the share of those Copilot made
    copilot_applied_suggestions: int
    # GitHub gives a median per day; over a period this is their mean, weighted by the PRs merged
    # each day (a true median would need every PR). None without a merge that reported one.
    minutes_to_merge: float | None
    minutes_to_merge_copilot: float | None


class ReportCoverage(Frozen):
    """How complete the per-user numbers are, as of the last reported day."""

    day: date
    missing_telemetry_users: int | None  # used Copilot in an editor that sent no usage telemetry
    below_minimum_users: int | None  # left out of the breakdowns, too few to report
    # GitHub's own active-user counts, to compare with the ones counted from the per-user rows.
    daily_active_users: int | None
    weekly_active_users: int | None
    monthly_active_users: int | None


class OrgReport(Frozen):
    period: Period
    days_reported: int  # days in the period with an org report
    pull_requests: PullRequestTotals | None  # None if no reported day had pull request numbers
    daily: list[PullRequestDay]  # days with pull request numbers, oldest first
    mcp_servers: list[NamedCount]  # interactions per MCP server, most used first
    custom_agents: list[NamedCount]
    coverage: ReportCoverage | None


def _weighted_minutes(pairs: Iterable[tuple[float | None, int | None]]) -> float | None:
    weighted = [(m, n) for m, n in pairs if m is not None and n]
    total = sum(n for _, n in weighted)
    return sum(m * n for m, n in weighted) / total if total else None


def org_report(days: Sequence[OrgReportDay], use: OrgReportUse, period: Period) -> OrgReport:
    days = sorted((d for d in days if period.contains(d.day)), key=lambda d: d.day)
    with_prs = [d for d in days if d.prs_created is not None]

    def total(field: str) -> int:
        return sum(getattr(d, field) or 0 for d in with_prs)

    prs = (
        PullRequestTotals(
            created=total("prs_created"),
            created_by_copilot=total("prs_created_by_copilot"),
            reviewed=total("prs_reviewed"),
            reviewed_by_copilot=total("prs_reviewed_by_copilot"),
            merged=total("prs_merged"),
            merged_created_by_copilot=total("prs_merged_created_by_copilot"),
            suggestions=total("pr_suggestions"),
            applied_suggestions=total("pr_applied_suggestions"),
            copilot_suggestions=total("pr_copilot_suggestions"),
            copilot_applied_suggestions=total("pr_copilot_applied_suggestions"),
            minutes_to_merge=_weighted_minutes((d.median_minutes_to_merge, d.prs_merged) for d in with_prs),
            minutes_to_merge_copilot=_weighted_minutes(
                (d.median_minutes_to_merge_copilot, d.prs_merged_created_by_copilot) for d in with_prs
            ),
        )
        if with_prs
        else None
    )
    last = days[-1] if days else None
    return OrgReport(
        period=period,
        days_reported=len(days),
        pull_requests=prs,
        daily=[
            PullRequestDay(
                day=d.day,
                created=d.prs_created or 0,
                created_by_copilot=d.prs_created_by_copilot or 0,
                merged=d.prs_merged or 0,
                merged_created_by_copilot=d.prs_merged_created_by_copilot or 0,
                reviewed_by_copilot=d.prs_reviewed_by_copilot or 0,
            )
            for d in with_prs
        ],
        mcp_servers=sorted(use.mcp_servers, key=lambda n: (-n.count, n.name)),
        custom_agents=sorted(use.custom_agents, key=lambda n: (-n.count, n.name)),
        coverage=ReportCoverage(
            day=last.day,
            missing_telemetry_users=last.missing_telemetry_users,
            below_minimum_users=last.below_minimum_users,
            daily_active_users=last.daily_active_users,
            weekly_active_users=last.weekly_active_users,
            monthly_active_users=last.monthly_active_users,
        )
        if last
        else None,
    )
