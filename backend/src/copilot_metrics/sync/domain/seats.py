"""Copilot seats and the org's seat breakdown."""

from datetime import date, datetime

from copilot_metrics.shared.kernel import Frozen


class SeatAssignee(Frozen):
    id: int
    login: str
    avatar_url: str | None = None


class AssigningTeam(Frozen):
    slug: str


class CopilotSeat(Frozen):
    assignee: SeatAssignee | None = None  # null for seats pending an org invite
    created_at: datetime | None = None
    pending_cancellation_date: date | None = None
    last_activity_at: datetime | None = None
    last_activity_editor: str | None = None
    plan_type: str | None = None
    assigning_team: AssigningTeam | None = None


class SeatsPage(Frozen):
    total_seats: int = 0
    seats: list[CopilotSeat] = []


class SeatBreakdown(Frozen):
    total: int = 0
    added_this_cycle: int = 0
    pending_invitation: int = 0
    pending_cancellation: int = 0
    active_this_cycle: int = 0
    inactive_this_cycle: int = 0


class CopilotBilling(Frozen):
    seat_breakdown: SeatBreakdown
    plan_type: str | None = None


class SeatHolder(Frozen):
    user_id: int
    login: str
