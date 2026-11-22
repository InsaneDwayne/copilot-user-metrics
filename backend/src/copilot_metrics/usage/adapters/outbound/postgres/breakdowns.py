"""Org and team breakdowns of the raw metrics for the adoption page.

Distinct people and totals per feature, skill, language, editor and model. Missing or non-array
breakdowns count as empty.
"""

from sqlalchemy import TextClause, text

# Only the rows of people in ``:team`` that day (membership is stored per day, so moving
# between teams moves the activity with it); everyone when ``:team`` is null.
_IN_TEAM = """(CAST(:team AS text) IS NULL OR EXISTS (
    SELECT 1 FROM user_team_day t WHERE t.user_id = a.user_id AND t.day = a.day AND t.team_slug = :team))"""


def _num(field: str) -> str:
    return f"coalesce((e->>'{field}')::numeric, 0)"


def _sum(field: str) -> str:
    return f"coalesce(sum((e->>'{field}')::numeric), 0)::bigint"


def _breakdown(key: str, keys: dict[str, str], columns: str) -> TextClause:
    """Totals per entry of one raw breakdown array (``e``), grouped by ``keys`` (alias: field).

    Built once at import from the literals below, never from input; values are bind parameters.
    """
    selected = ", ".join(f"e->>'{field}' AS {alias}" for alias, field in keys.items())
    present = " AND ".join(f"e->>'{field}' IS NOT NULL" for field in keys.values())
    sql = f"""
SELECT {selected}, {columns}
FROM user_activity a
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(a.raw->'{key}') = 'array' THEN a.raw->'{key}' ELSE '[]' END
) e
WHERE a.day BETWEEN :start AND :end AND {present} AND {_IN_TEAM}
GROUP BY {", ".join(str(i + 1) for i in range(len(keys)))}
"""  # noqa: S608 - module constants only, see above
    return text(sql)


def _users(*fields: str) -> str:
    """Distinct people with any of ``fields`` above zero."""
    return f"count(DISTINCT a.user_id) FILTER (WHERE {' + '.join(_num(f) for f in fields)} > 0) AS users"


FEATURE_USE_SQL = _breakdown(
    "totals_by_feature",
    {"name": "feature"},
    f"""{_users("user_initiated_interaction_count", "code_generation_activity_count")},
       {_sum("user_initiated_interaction_count")} AS prompts,
       {_sum("loc_suggested_to_add_sum")} AS loc_suggested_add,
       {_sum("loc_suggested_to_delete_sum")} AS loc_suggested_delete,
       {_sum("loc_added_sum")} AS loc_added,
       {_sum("loc_deleted_sum")} AS loc_deleted""",
)

SKILL_USE_SQL = _breakdown(
    "totals_by_skill",
    {"name": "skill"},
    f"""{_users("interaction_count")},
       {_sum("interaction_count")} AS invocations""",
)

LANGUAGE_USE_SQL = _breakdown(
    "totals_by_language_feature",
    {"language": "language"},
    f"""{_users("code_generation_activity_count", "loc_added_sum")},
       {_sum("loc_added_sum")} AS loc_added,
       {_sum("code_generation_activity_count")} AS generations,
       {_sum("code_acceptance_activity_count")} AS acceptances""",
)

IDE_USE_SQL = _breakdown(
    "totals_by_ide",
    {"ide": "ide"},
    _users("user_initiated_interaction_count", "code_generation_activity_count"),
)

MODEL_FEATURE_SQL = _breakdown(
    "totals_by_model_feature",
    {"model": "model", "feature": "feature"},
    f"""{_sum("user_initiated_interaction_count")} AS prompts,
       {_sum("code_generation_activity_count")} AS generations,
       ({_sum("loc_added_sum")} + {_sum("loc_deleted_sum")}) AS loc_changed""",
)

LANGUAGE_MODEL_SQL = _breakdown(
    "totals_by_language_model",
    {"language": "language", "model": "model"},
    f"""{_sum("code_generation_activity_count")} AS generations,
       {_sum("code_acceptance_activity_count")} AS acceptances,
       ({_sum("loc_added_sum")} + {_sum("loc_deleted_sum")}) AS loc_changed""",
)
