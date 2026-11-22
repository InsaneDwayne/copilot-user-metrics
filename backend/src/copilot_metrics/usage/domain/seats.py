"""Seat overview and idle seats."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum

from copilot_metrics.shared.kernel import Amount, Frozen, Page, PageRequest
from copilot_metrics.usage.domain.members import MemberRow
from copilot_metrics.usage.domain.org import SeatCost


class SeatStatus(StrEnum):
    NEVER_USED = "never_used"
    INACTIVE = "inactive"


class IdleSeat(Frozen):
    login: str
    avatar_url: str | None
    teams: list[str]
    assigned_at: datetime | None
    last_activity_at: datetime | None
    status: SeatStatus
    inactive_days: int | None  # days since the last activity; None when never used
    pending_cancellation_date: date | None  # already being removed, so nothing left to reclaim


class SeatOverview(Frozen):
    idle_after_days: int
    assigned: int
    active: int  # activity within the last ``idle_after_days``
    inactive: int  # used before, idle since
    never_used: int  # assigned at least ``idle_after_days`` ago, no activity on record
    recently_assigned: int  # assigned within ``idle_after_days``, not used yet: too new to judge
    pending_cancellation: int  # idle seats GitHub is already removing
    reclaimable: int  # idle seats not being removed yet
    reclaimable_usd: Amount | None  # their monthly seat fee; None until GitHub lists the seat price
    seat_cost: SeatCost | None  # this month's seat charges, as GitHub reports them
    idle: Page[IdleSeat]  # reclaimable first (never used, then longest idle), pending cancellation last


INACTIVE_AFTER = timedelta(days=7)


def is_active(m: MemberRow, now: datetime, within: timedelta = INACTIVE_AFTER) -> bool:
    return m.last_activity_at is not None and now - m.last_activity_at <= within


def _is_idle(m: MemberRow, now: datetime, after: timedelta) -> bool:
    """No activity within ``after``; a never-used seat only once it has been assigned that long."""
    if m.last_activity_at is not None:
        return now - m.last_activity_at > after
    return m.assigned_at is None or now - m.assigned_at >= after


def idle_seats(rows: Sequence[MemberRow], now: datetime, idle_after_days: int) -> list[IdleSeat]:
    """Current seats idle for ``idle_after_days``, in the order to act on them."""
    after = timedelta(days=idle_after_days)
    idle = [
        IdleSeat(
            login=m.login,
            avatar_url=m.avatar_url,
            teams=m.teams,
            assigned_at=m.assigned_at,
            last_activity_at=m.last_activity_at,
            status=SeatStatus.NEVER_USED if m.last_activity_at is None else SeatStatus.INACTIVE,
            inactive_days=(now - m.last_activity_at).days if m.last_activity_at else None,
            pending_cancellation_date=m.pending_cancellation_date,
        )
        for m in rows
        if m.ended_at is None and _is_idle(m, now, after)
    ]
    idle.sort(
        key=lambda s: (
            s.pending_cancellation_date is not None,
            s.status is not SeatStatus.NEVER_USED,
            -(s.inactive_days or 0),
            s.login.lower(),
        )
    )
    return idle


class IdleSeatExportRow(Frozen):
    """One idle seat in the CSV export; the fields, in order, are its columns."""

    login: str
    teams: str  # "; "-separated
    status: SeatStatus
    inactive_days: int | None
    last_activity_at: datetime | None
    seat_assigned_at: datetime | None
    pending_cancellation_date: date | None


def idle_seat_export(seats: Sequence[IdleSeat]) -> list[IdleSeatExportRow]:
    return [
        IdleSeatExportRow(
            login=s.login,
            teams="; ".join(s.teams),
            status=s.status,
            inactive_days=s.inactive_days,
            last_activity_at=s.last_activity_at,
            seat_assigned_at=s.assigned_at,
            pending_cancellation_date=s.pending_cancellation_date,
        )
        for s in seats
    ]


def seat_overview(
    rows: Sequence[MemberRow],
    now: datetime,
    seat_cost: SeatCost | None,
    request: PageRequest | None = None,
    idle_after_days: int = INACTIVE_AFTER.days,
) -> SeatOverview:
    """Current seats only: members whose seat ended this cycle still appear in usage, not here."""
    rows = [r for r in rows if r.ended_at is None]
    within = timedelta(days=idle_after_days)
    idle = idle_seats(rows, now, idle_after_days)
    pending = sum(s.pending_cancellation_date is not None for s in idle)
    reclaimable = len(idle) - pending
    active = sum(is_active(m, now, within) for m in rows)
    never = sum(s.status is SeatStatus.NEVER_USED for s in idle)
    return SeatOverview(
        idle_after_days=idle_after_days,
        assigned=len(rows),
        active=active,
        inactive=len(idle) - never,
        never_used=never,
        recently_assigned=len(rows) - active - len(idle),
        pending_cancellation=pending,
        reclaimable=reclaimable,
        reclaimable_usd=reclaimable * seat_cost.price_per_seat_usd if seat_cost else None,
        seat_cost=seat_cost,
        idle=Page[IdleSeat].of(idle, request or PageRequest()),
    )
