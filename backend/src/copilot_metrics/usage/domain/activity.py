"""One person's activity from the usage metrics: surfaces, adoption phase, totals."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from enum import StrEnum

from copilot_metrics.shared.kernel import Frozen, Period
from copilot_metrics.shared.metrics_record import UserDayMetrics
from copilot_metrics.usage.domain.changes import (
    CodeChanges,
    FeatureLoc,
    LanguageModelUse,
    ModelFeatureUse,
    code_changes,
    language_model_matrix,
    model_feature_matrix,
)


class Surface(StrEnum):
    CHAT = "chat"
    AGENT = "agent"
    CLI = "cli"
    CLOUD_AGENT = "cloud_agent"
    CODE_REVIEW = "code_review"
    APP = "app"


class AdoptionPhase(Frozen):
    """GitHub's AI adoption phase for a person (``ai_adoption_phase`` in the daily metrics).

    GitHub documents "No Cohort" (0, the default) and "Phase 1" to "Phase 3", higher meaning
    deeper use. It doesn't publish the thresholds, and the classifier is versioned.
    """

    number: int
    label: str
    version: str | None = None

    @classmethod
    def parse(cls, value: object) -> AdoptionPhase | None:
        """From GitHub's object; anything missing or malformed counts as not reported."""
        if isinstance(value, AdoptionPhase):
            return value
        if not isinstance(value, dict):
            return None
        number, label, version = value.get("phase_number"), value.get("phase"), value.get("version")
        if not isinstance(number, int) or isinstance(number, bool) or not isinstance(label, str) or not label:
            return None
        return cls(number=number, label=label, version=version if isinstance(version, str) else None)


def latest_phase(days: Iterable[UserDayMetrics]) -> AdoptionPhase | None:
    """The phase on the last day that reports one."""
    phase = None
    for d in sorted(days, key=lambda d: d.day):
        phase = AdoptionPhase.parse((d.model_extra or {}).get("ai_adoption_phase")) or phase
    return phase


def surfaces_used(
    chat: bool, agent: bool, cli: bool, cloud_agent: bool, code_review: bool, app: bool
) -> dict[Surface, bool]:
    return {
        Surface.CHAT: chat,
        Surface.AGENT: agent,
        Surface.CLI: cli,
        Surface.CLOUD_AGENT: cloud_agent,
        Surface.CODE_REVIEW: code_review,
        Surface.APP: app,
    }


def _day_surfaces(d: UserDayMetrics) -> dict[Surface, bool]:
    return surfaces_used(
        d.used_chat, d.used_agent, d.used_cli, d.used_cloud_agent, d.used_code_review, d.used_copilot_app
    )


def has_activity(prompts: int, generations: int, surfaces: dict[Surface, bool]) -> bool:
    """Any prompt, generated code or surface used. The Postgres ``MEMBERS_SQL`` counts days the same way."""
    return bool(prompts or generations) or any(surfaces.values())


def is_active_day(d: UserDayMetrics) -> bool:
    return has_activity(d.user_initiated_interaction_count, d.code_generation_activity_count, _day_surfaces(d))


class NamedCount(Frozen):
    name: str
    count: int


class LanguageStat(Frozen):
    language: str
    loc_added: int
    acceptance_rate: float | None


class SurfaceDays(Frozen):
    surface: Surface
    days: int


def acceptance_rate(accepted: int, generated: int) -> float | None:
    return accepted / generated if generated else None


class ActivitySummary(Frozen):
    period: Period
    data_through: date | None  # metrics cover complete days only
    active_days: int
    elapsed_days: int
    prompts: int
    generations: int
    acceptances: int
    loc_suggested: int
    loc_added: int
    acceptance_rate: float | None
    top_ide: str | None
    features: list[NamedCount]
    skills: list[NamedCount]  # invocations per skill, most used first
    languages: list[LanguageStat]
    surfaces: list[SurfaceDays]
    adoption_phase: AdoptionPhase | None  # on the last day in the period that reports one
    code_changes: CodeChanges
    model_features: list[ModelFeatureUse]
    language_models: list[LanguageModelUse]


def summarize_activity(
    days: Sequence[UserDayMetrics], period: Period, today: date, data_through: date | None
) -> ActivitySummary:
    features: defaultdict[str, int] = defaultdict(int)
    skills: defaultdict[str, int] = defaultdict(int)
    ides: defaultdict[str, int] = defaultdict(int)
    lang_loc: defaultdict[str, int] = defaultdict(int)
    lang_gen: defaultdict[str, int] = defaultdict(int)
    lang_acc: defaultdict[str, int] = defaultdict(int)
    loc: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    model_feature: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    language_model: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for d in days:
        for mf in d.totals_by_model_feature:
            cell = model_feature[mf.model, mf.feature]
            cell[0] += mf.user_initiated_interaction_count
            cell[1] += mf.code_generation_activity_count
            cell[2] += mf.loc_added_sum + mf.loc_deleted_sum
        for lm in d.totals_by_language_model:
            cell = language_model[lm.language, lm.model]
            cell[0] += lm.code_generation_activity_count
            cell[1] += lm.code_acceptance_activity_count
            cell[2] += lm.loc_added_sum + lm.loc_deleted_sum
        for f in d.totals_by_feature:
            features[f.feature] += f.user_initiated_interaction_count
            sums = loc[f.feature]
            sums[0] += f.loc_suggested_to_add_sum
            sums[1] += f.loc_suggested_to_delete_sum
            sums[2] += f.loc_added_sum
            sums[3] += f.loc_deleted_sum
        for sk in d.totals_by_skill or []:
            skills[sk.skill] += sk.interaction_count
        for i in d.totals_by_ide:
            ides[i.ide] += i.user_initiated_interaction_count + i.code_generation_activity_count
        for lf in d.totals_by_language_feature:
            lang_loc[lf.language] += lf.loc_added_sum
            lang_gen[lf.language] += lf.code_generation_activity_count
            lang_acc[lf.language] += lf.code_acceptance_activity_count

    generations = sum(d.code_generation_activity_count for d in days)
    acceptances = sum(d.code_acceptance_activity_count for d in days)
    surfaces = {s: sum(_day_surfaces(d)[s] for d in days) for s in Surface}
    last_day = min(period.end, data_through or today, today)
    return ActivitySummary(
        period=period,
        data_through=data_through,
        active_days=sum(is_active_day(d) for d in days),
        elapsed_days=max(0, (last_day - period.start).days + 1),
        prompts=sum(d.user_initiated_interaction_count for d in days),
        generations=generations,
        acceptances=acceptances,
        loc_suggested=sum(d.loc_suggested_to_add_sum for d in days),
        loc_added=sum(d.loc_added_sum for d in days),
        acceptance_rate=acceptance_rate(acceptances, generations),
        top_ide=max(ides, key=lambda k: ides[k]) if ides else None,
        features=sorted(
            (NamedCount(name=k, count=v) for k, v in features.items() if v), key=lambda n: n.count, reverse=True
        ),
        skills=sorted((NamedCount(name=k, count=v) for k, v in skills.items() if v), key=lambda n: (-n.count, n.name)),
        languages=sorted(
            (
                LanguageStat(language=k, loc_added=v, acceptance_rate=acceptance_rate(lang_acc[k], lang_gen[k]))
                for k, v in lang_loc.items()
            ),
            key=lambda s: s.loc_added,
            reverse=True,
        )[:10],
        surfaces=[SurfaceDays(surface=s, days=n) for s, n in surfaces.items()],
        adoption_phase=latest_phase(days),
        code_changes=code_changes(
            FeatureLoc(feature=k, loc_suggested_add=a, loc_suggested_delete=b, loc_added=c, loc_deleted=e)
            for k, (a, b, c, e) in loc.items()
        ),
        model_features=model_feature_matrix(
            [
                ModelFeatureUse(model=m, feature=f, prompts=p, generations=g, loc_changed=c)
                for (m, f), (p, g, c) in model_feature.items()
            ]
        ),
        language_models=language_model_matrix(
            [
                LanguageModelUse(language=lang, model=m, generations=g, acceptances=a, loc_changed=c)
                for (lang, m), (g, a, c) in language_model.items()
            ]
        ),
    )
