"""The admin member list: rows, activity segments, filtering, paging and export."""

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import field_validator

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen, Page, PageRequest, Period
from copilot_metrics.usage.domain.activity import AdoptionPhase, acceptance_rate
from copilot_metrics.usage.domain.budgets import Budget, UserBudget, current_only


class MemberProfile(Frozen):
    user_id: int
    login: str
    avatar_url: str | None
    assigned_at: datetime | None
    ended_at: datetime | None
    last_activity_at: datetime | None
    last_activity_editor: str | None


class MemberRow(MemberProfile):
    """A seat holder with their totals for a period (from one repository query)."""

    teams: list[str]
    credits: Amount
    gross_usd: Amount
    top_model: str | None
    generations: int
    acceptances: int
    prompts: int = 0
    active_days: int = 0  # days in the period with any activity (see ``is_active_day``)
    adoption_phase: AdoptionPhase | None = None  # GitHub's raw object as stored, parsed leniently
    pending_cancellation_date: date | None = None  # GitHub removes the seat at the end of this cycle

    @field_validator("adoption_phase", mode="before")
    @classmethod
    def _lenient_phase(cls, value: object) -> AdoptionPhase | None:
        return AdoptionPhase.parse(value)


class ActivitySegment(StrEnum):
    """How often a seat holder used Copilot in the period."""

    NONE = "none"  # not a single day
    OCCASIONAL = "occasional"  # 1 to 6 days
    REGULAR = "regular"  # 7 days or more


REGULAR_FROM_DAYS = 7


def segment_of(active_days: int) -> ActivitySegment:
    if active_days <= 0:
        return ActivitySegment.NONE
    return ActivitySegment.OCCASIONAL if active_days < REGULAR_FROM_DAYS else ActivitySegment.REGULAR


class SegmentCount(Frozen):
    segment: ActivitySegment
    members: int


def segment_counts(active_days: Iterable[int]) -> list[SegmentCount]:
    """Every segment, in order, even when empty."""
    counts = {s: 0 for s in ActivitySegment}
    for n in active_days:
        counts[segment_of(n)] += 1
    return [SegmentCount(segment=s, members=n) for s, n in counts.items()]


class MemberUsage(Frozen):
    user_id: int
    login: str
    avatar_url: str | None
    teams: list[str]
    credits: Amount
    gross_usd: Amount
    share: float  # 0..1 of all members' credits in the period
    top_model: str | None
    last_activity_at: datetime | None
    last_activity_editor: str | None
    budget: Budget | None  # GitHub budget that applies to this member (current month)
    active_days: int
    prompts: int
    acceptance_rate: float | None
    segment: ActivitySegment
    adoption_phase: AdoptionPhase | None


class MemberSort(StrEnum):
    CREDITS = "credits"  # most AI credits first
    BUDGET = "budget"  # closest to (or past) their budget first; members without a budget last
    ACTIVE_DAYS = "active_days"  # most days with activity first


class MemberQuery(Frozen):
    """Filters and order for the admin member list."""

    team: str | None = None
    login: str | None = None  # case-insensitive substring
    segment: ActivitySegment | None = None
    sort: MemberSort = MemberSort.CREDITS


class MemberPage(Page[MemberUsage]):
    members: int  # seat holders in the period before the team and login filters
    teams: list[str]  # every team among them, for the team filter
    segments: list[SegmentCount]  # after the team and login filters, before the segment filter


def budget_used(m: MemberUsage) -> float | None:
    """Share of the member's own budget used this month (may pass 1); None without a budget."""
    b = m.budget
    if b is None or b.amount_usd <= 0:
        return None
    return float(b.consumed_usd / b.amount_usd)


def _credits_order(m: MemberUsage) -> tuple[Decimal, str]:
    return -m.credits, m.login.lower()


def _budget_order(m: MemberUsage) -> tuple[bool, float, Decimal, str]:
    used = budget_used(m)
    return used is None, -(used or 0), -m.credits, m.login.lower()


def _active_days_order(m: MemberUsage) -> tuple[int, Decimal, str]:
    return -m.active_days, -m.credits, m.login.lower()


_MEMBER_ORDER = {
    MemberSort.CREDITS: _credits_order,
    MemberSort.BUDGET: _budget_order,
    MemberSort.ACTIVE_DAYS: _active_days_order,
}


def _matching(usage: Sequence[MemberUsage], query: MemberQuery) -> list[MemberUsage]:
    needle = (query.login or "").strip().lower()
    return [
        m for m in usage if (query.team is None or query.team in m.teams) and (not needle or needle in m.login.lower())
    ]


def _in_segment(matching: Sequence[MemberUsage], query: MemberQuery) -> list[MemberUsage]:
    rows = [m for m in matching if query.segment is None or m.segment is query.segment]
    rows.sort(key=_MEMBER_ORDER[query.sort])
    return rows


def filter_members(usage: Sequence[MemberUsage], query: MemberQuery) -> list[MemberUsage]:
    """Every member ``member_page`` would page through, in the same order (for exports)."""
    return _in_segment(_matching(usage, query), query)


def member_page(usage: Sequence[MemberUsage], query: MemberQuery, request: PageRequest) -> MemberPage:
    """Filter, order and slice ``member_usage`` output. Ties fall back to the login, so pages never overlap."""
    matching = _matching(usage, query)
    rows = _in_segment(matching, query)
    teams = sorted({t for m in usage for t in m.teams})
    segments = segment_counts(m.active_days for m in matching)
    return MemberPage.of(rows, request, members=len(usage), teams=teams, segments=segments)


class MemberExportRow(Frozen):
    """One member in the CSV export; the fields, in order, are its columns."""

    login: str
    teams: str  # "; "-separated
    ai_credits: Amount
    list_value_usd: Amount
    share: float
    top_model: str | None
    active_days: int
    activity: ActivitySegment
    prompts: int
    acceptance_rate: float | None
    adoption_phase: str | None
    last_activity_at: datetime | None
    last_activity_editor: str | None
    budget_usd: Amount | None
    budget_consumed_usd: Amount | None


def member_export(usage: Sequence[MemberUsage]) -> list[MemberExportRow]:
    return [
        MemberExportRow(
            login=m.login,
            teams="; ".join(m.teams),
            ai_credits=round(m.credits, 4),
            list_value_usd=round(m.gross_usd, 2),
            share=round(m.share, 4),
            top_model=m.top_model,
            active_days=m.active_days,
            activity=m.segment,
            prompts=m.prompts,
            acceptance_rate=None if m.acceptance_rate is None else round(m.acceptance_rate, 4),
            adoption_phase=m.adoption_phase.label if m.adoption_phase else None,
            last_activity_at=m.last_activity_at,
            last_activity_editor=m.last_activity_editor,
            budget_usd=m.budget.amount_usd if m.budget else None,
            budget_consumed_usd=m.budget.consumed_usd if m.budget else None,
        )
        for m in usage
    ]


def member_usage(
    rows: Sequence[MemberRow], budgets: Sequence[UserBudget], period: Period, today: date
) -> list[MemberUsage]:
    total = sum((r.credits for r in rows), ZERO) or Decimal(1)
    budget_of = {b.user_id: b.budget for b in current_only(budgets, period, today) or []}
    usage = [
        MemberUsage(
            user_id=r.user_id,
            login=r.login,
            avatar_url=r.avatar_url,
            teams=r.teams,
            credits=r.credits,
            gross_usd=r.gross_usd,
            share=float(r.credits / total),
            top_model=r.top_model,
            last_activity_at=r.last_activity_at,
            last_activity_editor=r.last_activity_editor,
            budget=budget_of.get(r.user_id),
            active_days=r.active_days,
            prompts=r.prompts,
            acceptance_rate=acceptance_rate(r.acceptances, r.generations),
            segment=segment_of(r.active_days),
            adoption_phase=r.adoption_phase,
        )
        for r in rows
    ]
    return sorted(usage, key=lambda u: u.credits, reverse=True)
