"""The org-wide report: stored by the worker, served to org owners only."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.metrics_record import OrgDayMetrics, PullRequestTotals
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresSyncStore

from .conftest import sign_in


def report_day(day: str, **fields: object) -> OrgDayMetrics:
    return OrgDayMetrics.model_validate({**fields, "day": day})


async def test_admin_sees_pull_requests_mcp_and_coverage(
    client: httpx.AsyncClient, worker_engine: AsyncEngine, seeded: None
) -> None:
    store = PostgresSyncStore(worker_engine)
    first = report_day(
        "2026-11-03",
        pull_requests={"total_created": 3, "total_created_by_copilot": 1, "total_merged": 2},
        totals_by_mcp=[{"mcp": "docs", "interaction_count": 4}, {"mcp": "jira", "interaction_count": 1}],
    )
    assert await store.upsert_org_activity([first]) == 1
    # A re-sync of a day replaces it.
    await store.upsert_org_activity(
        [
            first.model_copy(update={"pull_requests": PullRequestTotals(total_created=5, total_merged=2)}),
            report_day(
                "2026-11-04",
                missing_client_telemetry_user_count=2,
                monthly_active_users=7,
                totals_by_mcp=[{"mcp": "docs", "interaction_count": 2}],
                totals_by_custom_agent=[{"custom_agent": "reviewer", "interaction_count": 3}],
            ),
        ]
    )

    await sign_in(client, "alice")
    assert (await client.get("/api/admin/org-report")).status_code == 403

    await sign_in(client, "owner")
    report = (await client.get("/api/admin/org-report", params={"from": "2026-11-01", "to": "2026-11-30"})).json()
    assert report["days_reported"] == 2
    assert (report["pull_requests"]["created"], report["pull_requests"]["merged"]) == (5, 2)
    assert [d["day"] for d in report["daily"]] == ["2026-11-03"]
    assert report["mcp_servers"] == [{"name": "docs", "count": 6}, {"name": "jira", "count": 1}]
    assert report["custom_agents"] == [{"name": "reviewer", "count": 3}]
    coverage = report["coverage"]
    assert (coverage["day"], coverage["missing_telemetry_users"], coverage["monthly_active_users"]) == (
        "2026-11-04",
        2,
        7,
    )
