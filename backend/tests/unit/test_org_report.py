"""GitHub's org-wide daily report: reading its files, and the period summary built from it."""

import json
from datetime import date

import pytest

from copilot_metrics.shared.kernel import Period
from copilot_metrics.shared.metrics_record import OrgDayMetrics
from copilot_metrics.sync.adapters.outbound.github.org_client import org_day_records
from copilot_metrics.usage import domain

DAY = {
    "day": "2026-11-03",
    "daily_active_users": 2,
    "monthly_active_users": 6,
    "missing_client_telemetry_user_count": 1,
    "pull_requests": {"total_created": 4, "total_created_by_copilot": 1, "median_minutes_to_merge": 90.5},
    "totals_by_mcp": [{"mcp": "docs-server", "interaction_count": 3}],
    "some_future_field": {"kept": True},
}


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"report_start_day": "2026-11-03", "day_totals": [DAY]}, indent=2),  # documented shape
        json.dumps(DAY, indent=2),  # a flat day
        json.dumps(DAY) + "\n",  # NDJSON
        json.dumps([DAY]),
    ],
)
def test_reads_every_shape_of_the_report_file(text: str) -> None:
    (record,) = [OrgDayMetrics.model_validate(r) for r in org_day_records(text)]
    assert record.day == date(2026, 11, 3)
    assert record.pull_requests is not None
    assert record.pull_requests.median_minutes_to_merge == 90.5
    assert record.weekly_active_users is None  # left out by GitHub, not 0
    assert record.model_dump()["some_future_field"] == {"kept": True}


def day(d: int, **values: float | None) -> domain.OrgReportDay:
    fields = {name: None for name in domain.OrgReportDay.model_fields if name != "day"}
    return domain.OrgReportDay.model_validate({**fields, **values, "day": date(2026, 11, d)})


NOV = Period.between(date(2026, 11, 1), date(2026, 11, 30))


def test_org_report_sums_pull_requests_and_weights_merge_times() -> None:
    days = [
        day(4, prs_created=2, prs_merged=1, median_minutes_to_merge=30, missing_telemetry_users=3),
        day(2, prs_created=5, prs_created_by_copilot=2, prs_merged=3, median_minutes_to_merge=10),
        day(3, daily_active_users=4),  # a report without pull request numbers
        day(5, prs_created=1, prs_merged=0, median_minutes_to_merge=999),  # nothing merged: no weight
    ]
    use = domain.OrgReportUse(
        mcp_servers=[domain.NamedCount(name="b", count=1), domain.NamedCount(name="a", count=5)], custom_agents=[]
    )
    report = domain.org_report(days, use, NOV)
    assert report.days_reported == 4
    assert report.pull_requests is not None
    assert (report.pull_requests.created, report.pull_requests.created_by_copilot) == (8, 2)
    assert report.pull_requests.minutes_to_merge == pytest.approx((10 * 3 + 30 * 1) / 4)
    assert report.pull_requests.minutes_to_merge_copilot is None
    assert [d.day.day for d in report.daily] == [2, 4, 5]
    assert [m.name for m in report.mcp_servers] == ["a", "b"]
    assert report.coverage is not None
    assert (report.coverage.day.day, report.coverage.missing_telemetry_users) == (5, None)


def test_org_report_without_reports() -> None:
    report = domain.org_report([], domain.OrgReportUse(mcp_servers=[], custom_agents=[]), NOV)
    assert (report.days_reported, report.pull_requests, report.daily, report.coverage) == (0, None, [], None)
