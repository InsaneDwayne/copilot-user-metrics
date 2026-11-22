"""GitHub's daily Copilot metrics records: per user (users-1-day NDJSON) and for the
whole org (organization-1-day).

The sync module parses downloads into it and stores the original as ``raw``
jsonb; the usage module re-reads ``raw`` for the breakdowns. Unknown fields are
kept (``extra="allow"``) and every breakdown defaults to empty, so a change in
GitHub's report doesn't break either side. ``missing_fields`` makes such a change visible:
a renamed field would otherwise just read as zero on the dashboard.
"""

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict


class _Record(BaseModel):
    model_config = ConfigDict(extra="allow")


class FeatureTotals(_Record):
    feature: str
    user_initiated_interaction_count: int = 0
    code_generation_activity_count: int = 0
    code_acceptance_activity_count: int = 0
    loc_suggested_to_add_sum: int = 0
    loc_suggested_to_delete_sum: int = 0
    loc_added_sum: int = 0
    loc_deleted_sum: int = 0


class ModelFeatureTotals(_Record):
    model: str
    feature: str
    user_initiated_interaction_count: int = 0
    code_generation_activity_count: int = 0
    code_acceptance_activity_count: int = 0
    loc_added_sum: int = 0
    loc_deleted_sum: int = 0


class LanguageModelTotals(_Record):
    language: str
    model: str
    code_generation_activity_count: int = 0
    code_acceptance_activity_count: int = 0
    loc_added_sum: int = 0
    loc_deleted_sum: int = 0


class LanguageFeatureTotals(_Record):
    language: str
    feature: str | None = None
    code_generation_activity_count: int = 0
    code_acceptance_activity_count: int = 0
    loc_suggested_to_add_sum: int = 0
    loc_added_sum: int = 0


class IdeTotals(_Record):
    ide: str
    user_initiated_interaction_count: int = 0
    code_generation_activity_count: int = 0


class TokenUsage(_Record):
    prompt_tokens_sum: int = 0
    output_tokens_sum: int = 0


class ModelTotals(_Record):
    """Model calls one client made for the user that day (``request_count`` counts calls, not prompts)."""

    model: str
    model_selection_mode: str | None = None
    request_count: int = 0
    token_usage: TokenUsage = TokenUsage()


class ClientTotals(_Record):
    client: str
    request_count: int = 0
    token_usage: TokenUsage = TokenUsage()
    totals_by_model: list[ModelTotals] = []


class SkillTotals(_Record):
    """One skill and how often it was invoked. GitHub groups names it doesn't list under ``other``."""

    skill: str
    interaction_count: int = 0


class UserDayMetrics(_Record):
    day: date
    user_id: int
    user_login: str
    user_initiated_interaction_count: int = 0
    code_generation_activity_count: int = 0
    code_acceptance_activity_count: int = 0
    loc_suggested_to_add_sum: int = 0
    loc_added_sum: int = 0
    used_agent: bool = False
    used_chat: bool = False
    used_cli: bool = False
    used_cloud_agent: bool = False
    used_copilot_app: bool = False
    used_code_review: bool = False
    totals_by_ide: list[IdeTotals] = []
    totals_by_feature: list[FeatureTotals] = []
    totals_by_language_feature: list[LanguageFeatureTotals] = []
    totals_by_model_feature: list[ModelFeatureTotals] = []
    totals_by_language_model: list[LanguageModelTotals] = []
    totals_by_client: list[ClientTotals] = []
    # GitHub leaves the customization breakdowns out when it has no such data (and did before
    # September 2026), so a missing one isn't a format change.
    totals_by_skill: list[SkillTotals] | None = None


class PullRequestTotals(_Record):
    """The org's pull requests that day; GitHub leaves the medians out on days nothing merged."""

    total_created: int = 0
    total_created_by_copilot: int = 0
    total_reviewed: int = 0
    total_reviewed_by_copilot: int = 0
    total_merged: int = 0
    total_merged_created_by_copilot: int = 0
    total_merged_reviewed_by_copilot: int = 0
    total_suggestions: int = 0
    total_applied_suggestions: int = 0
    total_copilot_suggestions: int = 0
    total_copilot_applied_suggestions: int = 0
    median_minutes_to_merge: float | None = None
    median_minutes_to_merge_copilot_authored: float | None = None


class NamedInteractions(_Record):
    """One MCP server (``mcp``) or custom agent (``custom_agent``) and how often it was used."""

    interaction_count: int = 0


class OrgDayMetrics(_Record):
    """One day of the org-wide report. Counts GitHub may leave out are ``None``, not 0."""

    day: date
    daily_active_users: int | None = None
    weekly_active_users: int | None = None
    monthly_active_users: int | None = None
    missing_client_telemetry_user_count: int | None = None
    below_usage_metrics_minimum_user_count: int | None = None
    pull_requests: PullRequestTotals | None = None
    totals_by_mcp: list[NamedInteractions] = []
    totals_by_custom_agent: list[NamedInteractions] = []


def missing_fields(records: Iterable[BaseModel]) -> tuple[list[str], list[str]]:
    """Expected fields no record carried, and the unknown fields that were sent instead.

    A field is expected unless its default is ``None`` (GitHub may leave those out). Paths
    are dotted, with ``[]`` for list entries (``totals_by_ide[].ide``); nested models are only
    checked where at least one record has them, so an empty breakdown is not a gap. One
    record without a field is normal, every record of a report without it is a format change.
    """
    known: dict[str, type[BaseModel]] = {}
    sent: dict[str, set[str]] = {}
    unknown: set[str] = set()

    def walk(record: BaseModel, path: str) -> None:
        known.setdefault(path, type(record))
        sent.setdefault(path, set()).update(record.model_fields_set)
        unknown.update(path + name for name in record.model_extra or {})
        for name in record.model_fields_set:
            value = getattr(record, name)
            if isinstance(value, BaseModel):
                walk(value, f"{path}{name}.")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, BaseModel):
                        walk(item, f"{path}{name}[].")

    for record in records:
        walk(record, "")
    missing = [
        path + name
        for path, model in known.items()
        for name, info in model.model_fields.items()
        if name not in sent[path] and info.default is not None
    ]
    return sorted(missing), sorted(unknown)
