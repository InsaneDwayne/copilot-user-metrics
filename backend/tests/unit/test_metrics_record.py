"""missing_fields: spotting a change in GitHub's report format before it reads as zeros."""

from pathlib import Path

from copilot_metrics.shared.metrics_record import OrgDayMetrics, UserDayMetrics, missing_fields

# A users-1-day record with every field the model knows. Swap in a line from a real
# download to check the model against GitHub itself.
SAMPLE = Path(__file__).parent.parent / "fixtures" / "users-1-day.ndjson"


def sample() -> UserDayMetrics:
    return UserDayMetrics.model_validate_json(SAMPLE.read_text())


def record(**fields: object) -> UserDayMetrics:
    return UserDayMetrics.model_validate({"day": "2026-11-03", "user_id": 1, "user_login": "alice", **fields})


def test_the_sample_has_every_expected_field() -> None:
    missing, unknown = missing_fields([sample()])

    assert missing == []
    assert unknown == ["ai_adoption_phase"]  # read from raw by the members query


def test_a_renamed_field_is_missing_and_its_new_name_unknown() -> None:
    raw = sample().model_dump(mode="json", exclude_unset=True)
    feature = raw["totals_by_feature"][0]
    feature["lines_added"] = feature.pop("loc_added_sum")

    missing, unknown = missing_fields([UserDayMetrics.model_validate(raw)])

    assert missing == ["totals_by_feature[].loc_added_sum"]
    assert unknown == ["ai_adoption_phase", "totals_by_feature[].lines_added"]


def test_a_field_one_record_has_is_not_missing() -> None:
    full = sample()
    sparse = record(totals_by_ide=[{"ide": "jetbrains"}])

    assert missing_fields([full, sparse])[0] == []
    assert "totals_by_ide[].user_initiated_interaction_count" in missing_fields([sparse])[0]


def test_an_empty_breakdown_is_not_a_gap() -> None:
    missing, _ = missing_fields([sample().model_copy(update={"totals_by_ide": []})])

    assert missing == []


def test_fields_github_may_leave_out_are_not_expected() -> None:
    missing, _ = missing_fields(
        [OrgDayMetrics.model_validate({"day": "2026-11-03", "totals_by_mcp": [], "totals_by_custom_agent": []})]
    )

    assert missing == []


def test_no_records_no_findings() -> None:
    assert missing_fields([]) == ([], [])
