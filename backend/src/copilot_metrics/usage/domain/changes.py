"""Code changes and models.

Shared by one person's Activity tab and the org and team Adoption pages.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence

from copilot_metrics.shared.kernel import Frozen

# GitHub's feature for code an agent changed on its own (agent and edit modes in the editor);
# every other feature is a person accepting or applying a suggestion.
AGENT_FEATURES = frozenset({"agent_edit"})


class FeatureLoc(Frozen):
    """Lines one feature suggested and changed in a period."""

    feature: str
    loc_suggested_add: int
    loc_suggested_delete: int
    loc_added: int
    loc_deleted: int


class CodeChange(FeatureLoc):
    agent: bool


class CodeChanges(Frozen):
    by_feature: list[CodeChange]  # features that changed any line, most lines changed first
    loc_added: int
    loc_deleted: int
    agent_loc_changed: int  # added + deleted by agents
    agent_share: float | None  # of all lines added + deleted; None without changes


def code_changes(features: Iterable[FeatureLoc]) -> CodeChanges:
    rows = [
        CodeChange(**f.model_dump(), agent=f.feature in AGENT_FEATURES)
        for f in features
        if f.loc_added or f.loc_deleted or f.loc_suggested_add or f.loc_suggested_delete
    ]
    rows.sort(key=lambda c: (-(c.loc_added + c.loc_deleted), c.feature))
    changed = sum(c.loc_added + c.loc_deleted for c in rows)
    agent = sum(c.loc_added + c.loc_deleted for c in rows if c.agent)
    return CodeChanges(
        by_feature=rows,
        loc_added=sum(c.loc_added for c in rows),
        loc_deleted=sum(c.loc_deleted for c in rows),
        agent_loc_changed=agent,
        agent_share=agent / changed if changed else None,
    )


class ModelFeatureUse(Frozen):
    """One model in one feature: what people asked, what it generated and the lines it changed."""

    model: str
    feature: str
    prompts: int
    generations: int
    loc_changed: int  # added + deleted


class LanguageModelUse(Frozen):
    language: str
    model: str
    generations: int
    acceptances: int
    loc_changed: int  # added + deleted


TOP_MODELS = 8
TOP_LANGUAGES = 10


def _top[T](rows: Sequence[T], key: Callable[[T], str], weight: Callable[[T], int], n: int) -> set[str]:
    totals: defaultdict[str, int] = defaultdict(int)
    for r in rows:
        totals[key(r)] += weight(r)
    return {k for k, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:n] if totals[k]}


def model_feature_matrix(rows: Sequence[ModelFeatureUse]) -> list[ModelFeatureUse]:
    """The most used models' cells (prompts, generations and lines all count), largest first."""

    def weight(r: ModelFeatureUse) -> int:
        return r.prompts + r.generations + r.loc_changed

    models = _top(rows, lambda r: r.model, weight, TOP_MODELS)
    return sorted((r for r in rows if r.model in models and weight(r)), key=lambda r: (-weight(r), r.model, r.feature))


def language_model_matrix(rows: Sequence[LanguageModelUse]) -> list[LanguageModelUse]:
    """The most used languages × models, largest first."""

    def weight(r: LanguageModelUse) -> int:
        return r.generations + r.loc_changed

    languages = _top(rows, lambda r: r.language, weight, TOP_LANGUAGES)
    models = _top(rows, lambda r: r.model, weight, TOP_MODELS)
    return sorted(
        (r for r in rows if r.language in languages and r.model in models and weight(r)),
        key=lambda r: (-weight(r), r.language, r.model),
    )
