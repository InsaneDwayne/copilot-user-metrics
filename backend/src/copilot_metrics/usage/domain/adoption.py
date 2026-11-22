"""Who in the org uses Copilot, how often and for what."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from copilot_metrics.shared.kernel import Frozen, Period
from copilot_metrics.usage.domain.activity import AdoptionPhase, Surface, acceptance_rate, has_activity, surfaces_used
from copilot_metrics.usage.domain.changes import (
    CodeChanges,
    FeatureLoc,
    LanguageModelUse,
    ModelFeatureUse,
    code_changes,
    language_model_matrix,
    model_feature_matrix,
)
from copilot_metrics.usage.domain.members import MemberRow, SegmentCount, segment_counts


class ActivityDayRow(Frozen):
    """One person's day of usage metrics, from the stored columns (no breakdowns)."""

    user_id: int
    day: date
    prompts: int
    generations: int
    acceptances: int
    loc_suggested: int
    loc_added: int
    used_chat: bool
    used_agent: bool
    used_cli: bool
    used_cloud_agent: bool
    used_app: bool
    used_review: bool

    @property
    def surfaces(self) -> dict[Surface, bool]:
        return surfaces_used(
            self.used_chat, self.used_agent, self.used_cli, self.used_cloud_agent, self.used_review, self.used_app
        )

    @property
    def active(self) -> bool:
        return has_activity(self.prompts, self.generations, self.surfaces)


class FeatureUse(Frozen):
    name: str  # GitHub's feature key, e.g. chat_panel_agent_mode
    users: int  # distinct people who used it in the period
    prompts: int
    loc_suggested_add: int = 0
    loc_suggested_delete: int = 0
    loc_added: int = 0
    loc_deleted: int = 0


class LanguageTotals(Frozen):
    language: str
    users: int
    loc_added: int
    generations: int
    acceptances: int


class IdeUse(Frozen):
    ide: str
    users: int


class SkillUse(Frozen):
    name: str  # GitHub's skill name; "other" groups the ones it doesn't list
    users: int  # distinct people who invoked it in the period
    invocations: int


class ActivityBreakdown(Frozen):
    """The org's per-feature, per-language and per-editor totals for a period, from the raw metrics."""

    features: list[FeatureUse]
    languages: list[LanguageTotals]
    ides: list[IdeUse]
    model_features: list[ModelFeatureUse] = []
    language_models: list[LanguageModelUse] = []
    skills: list[SkillUse] = []


class LanguageUse(Frozen):
    language: str
    users: int
    loc_added: int
    acceptance_rate: float | None


class AdoptionDay(Frozen):
    day: date
    active_users: int  # active that day
    active_7d: int  # active on any of the 7 days ending that day
    active_28d: int  # likewise for 28 days
    prompts: int
    acceptance_rate: float | None
    loc_added: int


class SurfaceUsers(Frozen):
    surface: Surface
    users: int  # distinct people who used it in the period


class PhaseCount(Frozen):
    phase: AdoptionPhase | None  # None: GitHub reported no phase for them in the period
    members: int


class OrgAdoption(Frozen):
    """Who in the org uses Copilot, how often and for what (org owners only)."""

    period: Period
    data_through: date | None  # metrics cover complete days only
    seats: int  # seat holders in the period
    active_users: int  # active on at least one day of the period
    average_daily_active: float | None
    prompts: int
    loc_suggested: int
    loc_added: int
    acceptance_rate: float | None
    daily: list[AdoptionDay]  # period start through the last day with data
    segments: list[SegmentCount]  # seat holders by days active
    phases: list[PhaseCount]  # seat holders by latest adoption phase, lowest phase first, unreported last
    surfaces: list[SurfaceUsers]
    features: list[FeatureUse]
    skills: list[SkillUse]  # most people first
    languages: list[LanguageUse]
    ides: list[IdeUse]
    code_changes: CodeChanges
    model_features: list[ModelFeatureUse]
    language_models: list[LanguageModelUse]


ROLLING_WINDOWS = (7, 28)
LOOKBACK_DAYS = max(ROLLING_WINDOWS) - 1  # rolling counts on the first day reach this far back


def _phase_counts(members: Sequence[MemberRow]) -> list[PhaseCount]:
    by_number: dict[int, AdoptionPhase] = {}
    counts: defaultdict[int | None, int] = defaultdict(int)
    for m in members:
        p = m.adoption_phase
        if p is not None:
            by_number.setdefault(p.number, p)
        counts[p.number if p else None] += 1
    phases = [PhaseCount(phase=by_number[n], members=counts[n]) for n in sorted(by_number)]
    if counts[None]:
        phases.append(PhaseCount(phase=None, members=counts[None]))
    return phases


def org_adoption(
    days: Sequence[ActivityDayRow],
    breakdown: ActivityBreakdown,
    members: Sequence[MemberRow],
    period: Period,
    today: date,
    data_through: date | None,
) -> OrgAdoption:
    """``days`` may start up to ``LOOKBACK_DAYS`` before the period, for the rolling counts."""
    active_on: defaultdict[date, set[int]] = defaultdict(set)
    for d in days:
        if d.active:
            active_on[d.day].add(d.user_id)
    in_period = [d for d in days if period.contains(d.day)]
    per_day: defaultdict[date, list[ActivityDayRow]] = defaultdict(list)
    for d in in_period:
        per_day[d.day].append(d)

    def active_within(day: date, window: int) -> int:
        return len(set[int]().union(*(active_on[day - timedelta(days=i)] for i in range(window))))

    series = []
    if data_through is not None:
        for day in period.each_day(until=min(data_through, today)):
            rows = per_day[day]
            series.append(
                AdoptionDay(
                    day=day,
                    active_users=len(active_on[day]),
                    active_7d=active_within(day, 7),
                    active_28d=active_within(day, 28),
                    prompts=sum(r.prompts for r in rows),
                    acceptance_rate=acceptance_rate(sum(r.acceptances for r in rows), sum(r.generations for r in rows)),
                    loc_added=sum(r.loc_added for r in rows),
                )
            )

    surface_users = {s: len({d.user_id for d in in_period if d.surfaces[s]}) for s in Surface}
    generations = sum(d.generations for d in in_period)
    acceptances = sum(d.acceptances for d in in_period)
    return OrgAdoption(
        period=period,
        data_through=data_through,
        seats=len(members),
        active_users=len({d.user_id for d in in_period if d.active}),
        average_daily_active=sum(d.active_users for d in series) / len(series) if series else None,
        prompts=sum(d.prompts for d in in_period),
        loc_suggested=sum(d.loc_suggested for d in in_period),
        loc_added=sum(d.loc_added for d in in_period),
        acceptance_rate=acceptance_rate(acceptances, generations),
        daily=series,
        segments=segment_counts(m.active_days for m in members),
        phases=_phase_counts(members),
        surfaces=[SurfaceUsers(surface=s, users=n) for s, n in surface_users.items()],
        features=sorted(
            (f for f in breakdown.features if f.users or f.prompts), key=lambda f: (-f.users, -f.prompts, f.name)
        ),
        skills=sorted(
            (s for s in breakdown.skills if s.users or s.invocations),
            key=lambda s: (-s.users, -s.invocations, s.name),
        ),
        languages=sorted(
            (
                LanguageUse(
                    language=lt.language,
                    users=lt.users,
                    loc_added=lt.loc_added,
                    acceptance_rate=acceptance_rate(lt.acceptances, lt.generations),
                )
                for lt in breakdown.languages
                if lt.users
            ),
            key=lambda lu: (-lu.users, -lu.loc_added, lu.language),
        )[:12],
        ides=sorted((i for i in breakdown.ides if i.users), key=lambda i: (-i.users, i.ide)),
        code_changes=code_changes(
            FeatureLoc(
                feature=f.name,
                loc_suggested_add=f.loc_suggested_add,
                loc_suggested_delete=f.loc_suggested_delete,
                loc_added=f.loc_added,
                loc_deleted=f.loc_deleted,
            )
            for f in breakdown.features
        ),
        model_features=model_feature_matrix(breakdown.model_features),
        language_models=language_model_matrix(breakdown.language_models),
    )
