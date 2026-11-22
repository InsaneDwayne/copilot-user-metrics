"""Run/stop from the admin console, through the API and as the worker sees it."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.adapters.outbound.postgres.engine import viewer_scope
from copilot_metrics.shared.adapters.outbound.postgres.tables import sync_request
from copilot_metrics.shared.kernel import Role, Viewer
from copilot_metrics.sync.adapters.outbound.postgres.requests import PostgresRequestInbox
from copilot_metrics.sync.domain import SyncRequest

from ..clock import FixedClock
from .conftest import sign_in
from .seed import NOW


async def test_admin_requests_a_run_and_sees_it_listed(client: httpx.AsyncClient) -> None:
    await sign_in(client, "owner")
    created = await client.post("/api/admin/sync/credits/run")
    assert created.status_code == 202
    body = created.json()
    assert body | {"id": 0, "requested_at": ""} == {
        "id": 0,
        "requested_at": "",
        "admin_login": "owner",
        "action": "run",
        "target": "credits",
        "handled_at": None,
        "outcome": None,
    }
    # Asking again before the worker got to it returns the same open request.
    assert (await client.post("/api/admin/sync/credits/run")).json()["id"] == body["id"]

    status = (await client.get("/api/admin/sync")).json()
    assert [t["target"] for t in status["targets"]] == ["credits", "seats", "budgets", "metrics", "history"]
    assert status["targets"][0] == {"target": "credits", "queued": 0, "running": 0}
    assert [r["id"] for r in status["requests"]] == [body["id"]]


async def test_unknown_target_or_action_is_rejected(client: httpx.AsyncClient) -> None:
    await sign_in(client, "owner")
    response = await client.post("/api/admin/sync/everything/run")
    assert response.status_code == 422
    assert "code" in response.json()
    assert (await client.post("/api/admin/sync/credits/explode")).status_code == 422


async def test_members_cannot_run_or_see_syncs(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    assert (await client.get("/api/admin/sync")).status_code == 403
    assert (await client.post("/api/admin/sync/credits/run")).status_code == 403


async def test_row_level_security_only_lets_admins_request_in_their_own_name(api_engine: AsyncEngine) -> None:
    alice = Viewer(user_id=1, login="alice", role=Role.MEMBER)
    owner = Viewer(user_id=3, login="owner", role=Role.ADMIN)
    values = {"admin_login": "x", "action": "run", "target": "credits"}
    with pytest.raises(DBAPIError, match="row-level security"):
        async with viewer_scope(api_engine, alice) as conn:
            await conn.execute(sync_request.insert().values(admin_user_id=1, **values))
    with pytest.raises(DBAPIError, match="row-level security"):
        async with viewer_scope(api_engine, owner) as conn:
            await conn.execute(sync_request.insert().values(admin_user_id=1, **values))
    # The API can read the job queue but never change it.
    with pytest.raises(DBAPIError, match="permission denied"):
        async with viewer_scope(api_engine, owner) as conn:
            await conn.execute(text("DELETE FROM procrastinate_jobs"))


async def test_worker_applies_each_open_request_once(client: httpx.AsyncClient, worker_engine: AsyncEngine) -> None:
    await sign_in(client, "owner")
    await client.post("/api/admin/sync/history/stop")
    await client.post("/api/admin/sync/seats/run")
    seen: list[str] = []

    async def handler(request: SyncRequest) -> str:
        seen.append(f"{request.action}:{request.target}")
        return "Done"

    inbox = PostgresRequestInbox(worker_engine, FixedClock(NOW))
    assert await inbox.handle_pending(handler) == 2
    assert await inbox.handle_pending(handler) == 0
    assert seen == ["stop:history", "run:seats"]
    requests = (await client.get("/api/admin/sync")).json()["requests"]
    assert [(r["outcome"], r["handled_at"] is not None) for r in requests] == [("Done", True), ("Done", True)]


async def test_organization_readers_cannot_run_or_see_syncs(client: httpx.AsyncClient, api_engine: AsyncEngine) -> None:
    await sign_in(client, "orgreader")
    assert (await client.get("/api/admin/sync")).status_code == 403
    response = await client.post("/api/admin/sync/credits/run")
    assert (response.status_code, response.json()["code"]) == (403, "admins_only")
    # Row-level security refuses an organization reader's request even if the API let one through.
    reader = Viewer(user_id=5, login="orgreader", role=Role.ORG_READER)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with viewer_scope(api_engine, reader) as conn:
            await conn.execute(
                sync_request.insert().values(admin_user_id=5, admin_login="orgreader", action="run", target="credits")
            )


async def test_admin_team_members_can_run_syncs(client: httpx.AsyncClient) -> None:
    await sign_in(client, "teamadmin")
    assert (await client.post("/api/admin/sync/credits/run")).status_code == 202
