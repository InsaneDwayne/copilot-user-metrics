"""Usage per team."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from copilot_metrics.shared.kernel import ZERO, Amount, Frozen
from copilot_metrics.usage.domain.activity import acceptance_rate
from copilot_metrics.usage.domain.members import MemberRow
from copilot_metrics.usage.domain.seats import is_active


class TeamUsage(Frozen):
    team: str
    seats: int
    active_7d: int
    credits: Amount
    gross_usd: Amount
    acceptance_rate: float | None
    top_model: str | None


class TeamModelCredits(Frozen):
    team: str
    model: str
    credits: Amount


def team_usage(rows: Sequence[MemberRow], team_models: Sequence[TeamModelCredits], now: datetime) -> list[TeamUsage]:
    """Teams as GitHub reports them; a member in several teams counts in each."""
    by_team: defaultdict[str, list[MemberRow]] = defaultdict(list)
    for r in rows:
        for t in r.teams:
            by_team[t].append(r)
    best: dict[str, TeamModelCredits] = {}
    for tm in team_models:
        if tm.team not in best or tm.credits > best[tm.team].credits:
            best[tm.team] = tm
    teams = [
        TeamUsage(
            team=team,
            seats=len(members),
            active_7d=sum(is_active(m, now) for m in members),
            credits=sum((m.credits for m in members), ZERO),
            gross_usd=sum((m.gross_usd for m in members), ZERO),
            acceptance_rate=acceptance_rate(sum(m.acceptances for m in members), sum(m.generations for m in members)),
            top_model=best[team].model if team in best else None,
        )
        for team, members in by_team.items()
    ]
    return sorted(teams, key=lambda t: t.credits, reverse=True)
