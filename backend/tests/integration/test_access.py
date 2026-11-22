"""The core promise: members only ever see their own rows."""

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.shared.kernel import Period, Role, Viewer
from copilot_metrics.sync.adapters.outbound.postgres.repository import PostgresSyncStore
from copilot_metrics.sync.domain import (
    CopilotBilling,
    SeatBreakdown,
    UserTeamRecord,
)
from copilot_metrics.usage.adapters.outbound.postgres.repository import PostgresUsageReader

from ..clock import FixedClock
from .conftest import sign_in
from .seed import BOB, NOW, seat


async def test_member_sees_only_their_own_usage(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    summary = (await client.get("/api/me/summary")).json()
    assert summary["totals"]["credits"] == 100
    models = (await client.get("/api/me/models")).json()
    assert [m["model"] for m in models] == ["Claude Sonnet 4.6"]


async def test_session_reports_seat_and_access(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    me = (await client.get("/api/session")).json()
    assert me["login"] == "alice"
    assert me["has_seat"] is True
    assert me["access"] == {"can_view_own_usage": True, "can_view_admin": False, "can_manage_sync": False}


async def test_member_cannot_open_admin_routes(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    for path in (
        "/api/admin/members",
        "/api/admin/members/bob/summary",
        "/api/admin/seats",
        "/api/admin/daily",
        "/api/admin/adoption",
        "/api/admin/members.csv",
        "/api/admin/seats/idle.csv",
    ):
        assert (await client.get(path)).status_code == 403, path


async def test_member_cannot_see_org_totals(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    response = await client.get("/api/org/summary")
    assert (response.status_code, response.json()["code"]) == (403, "org_readers_only")


async def test_admin_sees_org_totals_and_budgets(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    org = (await client.get("/api/org/summary")).json()
    assert org["totals"]["credits"] == 450
    assert "members" not in org  # never per person
    assert [(b["scope"], b["amount_usd"], b["consumed_usd"]) for b in org["budgets"]] == [("organization", 500, 120)]


async def test_member_sees_only_their_own_budget(
    client: httpx.AsyncClient, seeded: None, api_engine: AsyncEngine
) -> None:
    await sign_in(client, "alice")
    # The org-wide budget applies to Alice: she sees its amount and her own consumption.
    mine = (await client.get("/api/me/summary")).json()["budget"]
    assert (mine["scope"], mine["amount_usd"], mine["consumed_usd"]) == ("organization", 500, 4)
    # Bob's personal budget is invisible to Alice, even when asked for directly.
    alice = Viewer(user_id=1, login="alice", role=Role.MEMBER)
    budgets = await PostgresUsageReader(api_engine).user_budgets(alice)
    assert [b.user_id for b in budgets] == [1]


async def test_member_sees_their_personal_budget(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "bob")
    mine = (await client.get("/api/me/summary")).json()["budget"]
    assert (mine["scope"], mine["amount_usd"], mine["consumed_usd"]) == ("user", 80, 31)


async def test_admin_drill_down_shows_the_org_budget_that_applies(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    alice = (await client.get("/api/admin/members/alice/summary")).json()["budget"]
    assert (alice["scope"], alice["consumed_usd"]) == ("organization", 4)


async def test_admin_sees_every_members_budget(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    members = {m["login"]: m for m in (await client.get("/api/admin/members")).json()["items"]}
    assert members["bob"]["budget"]["scope"] == "user"
    assert members["bob"]["budget"]["amount_usd"] == 80


async def test_admin_member_list_is_paged_and_filtered(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    pages = [(await client.get("/api/admin/members", params={"size": 1, "page": n})).json() for n in (1, 2)]
    assert [(p["page"], p["pages"], p["total"], len(p["items"])) for p in pages] == [(1, 2, 2, 1), (2, 2, 2, 1)]
    assert {p["items"][0]["login"] for p in pages} == {"alice", "bob"}
    found = (await client.get("/api/admin/members", params={"q": "BO"})).json()
    assert ([m["login"] for m in found["items"]], found["total"], found["members"]) == (["bob"], 1, 2)


async def test_admin_sees_org_credits_per_day_and_model(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    daily = (await client.get("/api/admin/daily", params={"from": "2026-11-01", "to": "2026-11-30"})).json()
    assert [(d["day"], d["model"], d["credits"]) for d in daily] == [
        ("2026-11-03", "GPT-5.5", 300),
        ("2026-11-03", "Claude Sonnet 4.6", 150),
    ]


async def test_row_level_security_backs_up_the_service(api_engine: AsyncEngine, seeded: None) -> None:
    """Even a buggy query asking for Bob's rows as Alice gets nothing back."""
    reader = PostgresUsageReader(api_engine)
    alice = Viewer(user_id=1, login="alice", role=Role.MEMBER)
    period = Period.cycle_of(date(2026, 11, 1))
    assert await reader.user_credits(alice, BOB.user_id, period) == []
    rows = await reader.members(alice, period)
    assert [r.login for r in rows] == ["alice"]


async def test_api_role_cannot_write_usage(api_engine: AsyncEngine, seeded: None) -> None:
    async with api_engine.begin() as conn:
        with pytest.raises(ProgrammingError, match="permission denied"):
            await conn.execute(text("DELETE FROM credit_usage"))


async def test_admin_can_drill_into_a_member(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    members = (await client.get("/api/admin/members")).json()["items"]
    assert [m["login"] for m in members] == ["bob", "alice"]
    assert members[0]["top_model"] == "GPT-5.5"
    bob = (await client.get("/api/admin/members/bob/summary")).json()
    assert bob["totals"]["credits"] == 350
    assert (await client.get("/api/admin/members/nobody")).status_code == 404


async def test_outsider_reaches_no_data(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "stranger")
    me = (await client.get("/api/session")).json()
    assert me["role"] == "outsider"
    assert me["has_seat"] is False
    assert (await client.get("/api/me/summary")).status_code == 403
    assert (await client.get("/api/org/summary")).status_code == 403
    assert (await client.get("/api/sync/status")).status_code == 403


async def test_member_without_seat_is_refused(
    client: httpx.AsyncClient, worker_engine: AsyncEngine, seeded: None
) -> None:
    store = PostgresSyncStore(worker_engine)
    await store.save_seats(CopilotBilling(seat_breakdown=SeatBreakdown(total=1)), [seat(BOB)], NOW)
    await sign_in(client, "alice")
    assert (await client.get("/api/session")).json()["has_seat"] is False
    assert (await client.get("/api/me/summary")).status_code == 403


async def test_session_expires_absolutely(client: httpx.AsyncClient, seeded: None, clock: FixedClock) -> None:
    await sign_in(client, "alice")
    assert (await client.get("/api/session")).status_code == 200
    clock.current += timedelta(hours=13)
    assert (await client.get("/api/session")).status_code == 401


async def test_callback_rejects_a_forged_state(client: httpx.AsyncClient) -> None:
    await client.get("/auth/github")
    response = await client.get("/auth/github/callback", params={"code": "owner", "state": "forged"})
    assert response.headers["location"] == "/?signin_error=state"
    assert (await client.get("/api/session")).status_code == 401


async def test_sign_out_clears_the_session(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.get("/api/session")).status_code == 401


async def test_sync_status_is_stale_without_runs(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    status = (await client.get("/api/sync/status")).json()
    assert status["stale"] is True
    assert status["jobs"] == []


async def test_member_sees_only_their_own_model_tokens(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    tokens = (await client.get("/api/me/model-tokens", params={"from": "2026-11-01", "to": "2026-11-30"})).json()
    assert tokens == [
        {"day": "2026-11-03", "model": "claude-sonnet-4.6", "requests": 10, "prompt_tokens": 5000, "output_tokens": 800}
    ]


async def test_admin_sees_org_model_tokens_summed_across_clients(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    period = {"from": "2026-11-01", "to": "2026-11-30"}
    tokens = (await client.get("/api/admin/model-tokens", params=period)).json()
    assert [(t["day"], t["model"], t["requests"], t["prompt_tokens"], t["output_tokens"]) for t in tokens] == [
        ("2026-11-03", "gpt-5-mini", 42, 91000, 12200),
        ("2026-11-03", "claude-sonnet-4.6", 10, 5000, 800),
        ("2026-11-04", "gpt-5-mini", 5, 3000, 400),
        ("2026-11-04", "Code review (model not reported)", 2, 700, 100),
    ]
    bob = (await client.get("/api/admin/members/bob/model-tokens", params=period)).json()
    assert [(t["day"], t["model"]) for t in bob] == [
        ("2026-11-03", "gpt-5-mini"),
        ("2026-11-04", "gpt-5-mini"),
        ("2026-11-04", "Code review (model not reported)"),
    ]


async def test_admin_sees_org_adoption(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    org = (await client.get("/api/admin/adoption", params={"from": "2026-11-01", "to": "2026-11-30"})).json()
    assert (org["seats"], org["active_users"], org["prompts"], org["loc_added"]) == (2, 1, 6, 30)
    assert org["data_through"] == "2026-11-05"
    assert [(d["day"], d["active_users"], d["active_7d"]) for d in org["daily"]] == [
        ("2026-11-01", 0, 0),
        ("2026-11-02", 0, 0),
        ("2026-11-03", 0, 0),  # Bob's model calls alone don't make an active day
        ("2026-11-04", 1, 1),
        ("2026-11-05", 1, 1),
    ]
    assert [(s["segment"], s["members"]) for s in org["segments"]] == [("none", 1), ("occasional", 1), ("regular", 0)]
    assert [(p["phase"] and p["phase"]["label"], p["members"]) for p in org["phases"]] == [("Phase 2", 1), (None, 1)]
    surfaces = {s["surface"]: s["users"] for s in org["surfaces"]}
    assert (surfaces["chat"], surfaces["code_review"], surfaces["cli"]) == (1, 1, 0)
    assert [(f["name"], f["users"], f["prompts"]) for f in org["features"]] == [("chat_panel_agent_mode", 1, 6)]
    assert org["languages"] == [{"language": "python", "users": 1, "loc_added": 30, "acceptance_rate": 0.5}]
    assert org["ides"] == [{"ide": "vscode", "users": 1}]
    changes = org["code_changes"]
    assert [(c["feature"], c["agent"], c["loc_added"], c["loc_deleted"]) for c in changes["by_feature"]] == [
        ("agent_edit", True, 24, 6),
        ("code_completion", False, 6, 0),
    ]
    assert (changes["agent_loc_changed"], changes["agent_share"]) == (30, 30 / 36)
    assert org["model_features"] == [
        {"model": "gpt-5-mini", "feature": "agent_edit", "prompts": 0, "generations": 0, "loc_changed": 30},
        {"model": "gpt-5-mini", "feature": "chat_panel_agent_mode", "prompts": 6, "generations": 0, "loc_changed": 0},
    ]
    assert org["language_models"] == [
        {"language": "python", "model": "gpt-5-mini", "generations": 4, "acceptances": 0, "loc_changed": 30}
    ]


async def test_team_adoption_counts_members_on_the_days_they_were_in_the_team(
    client: httpx.AsyncClient, worker_engine: AsyncEngine, seeded: None
) -> None:
    # Bob was in "core" on Nov 4 only; his Nov 5 activity belongs to no team.
    record = UserTeamRecord.model_validate({"day": "2026-11-04", "user_id": 2, "user_login": "bob", "slug": "core"})
    await PostgresSyncStore(worker_engine).replace_user_teams(date(2026, 11, 4), [record])
    await sign_in(client, "owner")
    period = {"from": "2026-11-01", "to": "2026-11-30"}
    core = (await client.get("/api/admin/adoption", params={**period, "team": "core"})).json()
    assert (core["seats"], core["active_users"], core["prompts"]) == (1, 1, 6)
    assert [(d["day"], d["active_users"]) for d in core["daily"][-2:]] == [("2026-11-04", 1), ("2026-11-05", 0)]
    assert core["surfaces"][[s["surface"] for s in core["surfaces"]].index("code_review")]["users"] == 0
    assert core["code_changes"]["agent_loc_changed"] == 30
    other = (await client.get("/api/admin/adoption", params={**period, "team": "web"})).json()
    assert (other["seats"], other["active_users"], other["features"], other["model_features"]) == (0, 0, [], [])


async def test_admin_member_list_carries_activity(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    page = (await client.get("/api/admin/members", params={"sort": "active_days"})).json()
    bob, alice = page["items"]
    assert (bob["login"], bob["active_days"], bob["prompts"], bob["segment"]) == ("bob", 2, 6, "occasional")
    assert bob["adoption_phase"] == {"number": 2, "label": "Phase 2", "version": "v1"}
    assert (alice["login"], alice["active_days"], alice["segment"], alice["adoption_phase"]) == (
        "alice",
        0,
        "none",
        None,
    )
    idle = (await client.get("/api/admin/members", params={"segment": "none"})).json()
    assert ([m["login"] for m in idle["items"]], idle["total"]) == (["alice"], 1)
    assert [(s["segment"], s["members"]) for s in idle["segments"]] == [("none", 1), ("occasional", 1), ("regular", 0)]


async def test_member_activity_shows_their_adoption_phase(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "bob")
    activity = (await client.get("/api/me/activity", params={"from": "2026-11-01", "to": "2026-11-30"})).json()
    assert activity["adoption_phase"]["label"] == "Phase 2"
    assert activity["active_days"] == 2


async def test_admin_exports_filtered_members_and_idle_seats(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    members = await client.get("/api/admin/members.csv", params={"sort": "active_days"})
    assert members.status_code == 200
    assert members.headers["content-type"].startswith("text/csv")
    assert "attachment" in members.headers["content-disposition"]
    header, *rows = members.text.splitlines()
    assert header.startswith("login,teams,ai_credits,")
    assert [r.split(",")[0] for r in rows] == ["bob", "alice"]
    occasional = await client.get("/api/admin/members.csv", params={"segment": "occasional"})
    assert [r.split(",")[0] for r in occasional.text.splitlines()[1:]] == ["bob"]

    seats = (await client.get("/api/admin/seats", params={"idle_days": 30})).json()
    assert (seats["idle_after_days"], seats["assigned"], seats["active"], seats["reclaimable"]) == (30, 2, 2, 0)
    idle = await client.get("/api/admin/seats/idle.csv", params={"idle_days": 30})
    assert idle.text.splitlines() == [
        "login,teams,status,inactive_days,last_activity_at,seat_assigned_at,pending_cancellation_date"
    ]
    assert (await client.get("/api/admin/seats", params={"idle_days": 0})).status_code == 422


async def test_teams_come_from_each_persons_latest_listed_day(
    client: httpx.AsyncClient, worker_engine: AsyncEngine, seeded: None
) -> None:
    """The latest report day lists only Bob; Alice keeps her team from the day before."""
    store = PostgresSyncStore(worker_engine)

    def listed(day: str, user_id: int, login: str, team: str) -> UserTeamRecord:
        return UserTeamRecord.model_validate({"day": day, "user_id": user_id, "user_login": login, "slug": team})

    await store.replace_user_teams(
        date(2026, 11, 3),
        [listed("2026-11-03", 1, "alice", "core"), listed("2026-11-03", 2, "bob", "core")],
    )
    await store.replace_user_teams(
        date(2026, 11, 4),
        [listed("2026-11-04", 2, "bob", "web"), listed("2026-11-04", 2, "bob", "data")],
    )
    await sign_in(client, "owner")
    period = {"from": "2026-11-01", "to": "2026-11-30"}
    members = (await client.get("/api/admin/members", params=period)).json()
    assert {m["login"]: m["teams"] for m in members["items"]} == {"alice": ["core"], "bob": ["data", "web"]}
    assert members["teams"] == ["core", "data", "web"]
    teams = (await client.get("/api/admin/teams", params=period)).json()
    assert {t["team"]: t["seats"] for t in teams} == {"core": 1, "data": 1, "web": 1}
    # Bob's credits count for his current teams, Alice's for hers.
    assert {t["team"]: t["top_model"] for t in teams} == {
        "core": "Claude Sonnet 4.6",
        "data": "GPT-5.5",
        "web": "GPT-5.5",
    }
    # As of Nov 3, Bob was still in core.
    early = (await client.get("/api/admin/members", params={"from": "2026-11-01", "to": "2026-11-03"})).json()
    assert {m["login"]: m["teams"] for m in early["items"]} == {"alice": ["core"], "bob": ["core"]}


async def test_organization_reader_reads_the_org_but_not_sync(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "orgreader")
    me = (await client.get("/api/session")).json()
    assert me["role"] == "org_reader"
    assert me["access"] == {"can_view_own_usage": False, "can_view_admin": True, "can_manage_sync": False}
    members = (await client.get("/api/admin/members")).json()["items"]
    assert [m["login"] for m in members] == ["bob", "alice"]
    assert (await client.get("/api/admin/members/bob/summary")).json()["totals"]["credits"] == 350
    assert (await client.get("/api/admin/seats/idle.csv")).status_code == 200
    org = (await client.get("/api/org/summary")).json()
    assert [b["scope"] for b in org["budgets"]] == ["organization"]
    # Without a seat an organization reader still reaches their own (empty) usage, like an owner.
    assert (await client.get("/api/me/summary")).status_code == 200
    # Jobs are part of the Sync page, which is for admins.
    assert (await client.get("/api/sync/status")).json()["jobs"] == []


async def test_admin_team_member_is_an_admin_without_being_an_owner(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "teamadmin")  # also in the organization reader team: admin wins
    me = (await client.get("/api/session")).json()
    assert me["role"] == "admin"
    assert me["access"] == {"can_view_own_usage": False, "can_view_admin": True, "can_manage_sync": True}
    assert (await client.get("/api/admin/members/bob/summary")).status_code == 200


async def test_owner_in_an_organization_reader_team_stays_admin(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    me = (await client.get("/api/session")).json()
    assert me["role"] == "admin"
    assert me["access"]["can_manage_sync"] is True


async def test_team_membership_does_not_admit_outsiders(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "stranger")  # in the organization reader team, but not an active org member
    assert (await client.get("/api/session")).json()["role"] == "outsider"
    assert (await client.get("/api/admin/members")).status_code == 403


ORG_DATA = (
    "/api/org/summary",
    "/api/admin/models",
    "/api/admin/daily",
    "/api/admin/members",
    "/api/admin/members.csv",
    "/api/admin/members/bob",
    "/api/admin/members/bob/summary",
    "/api/admin/adoption",
    "/api/admin/org-report",
    "/api/admin/teams",
    "/api/admin/seats",
    "/api/admin/seats/idle.csv",
    "/api/admin/sync",
)


async def test_without_mapped_teams_only_org_owners_see_org_data(
    client_without_teams: httpx.AsyncClient, seeded: None
) -> None:
    # Team members get nothing from a team that isn't mapped: they are plain members.
    for login in ("alice", "orgreader", "teamadmin"):
        await sign_in(client_without_teams, login)
        me = (await client_without_teams.get("/api/session")).json()
        assert me["role"] == "member", login
        assert me["access"]["can_view_admin"] is False, login
        for path in ORG_DATA:
            assert (await client_without_teams.get(path)).status_code == 403, (login, path)

    await sign_in(client_without_teams, "owner")
    assert (await client_without_teams.get("/api/session")).json()["role"] == "admin"
    for path in ORG_DATA:
        assert (await client_without_teams.get(path)).status_code == 200, ("owner", path)


PUBLIC = {"/api/config", "/auth/logout"}  # signing out needs no session; sign-in and /healthz are not in the schema
OWN_DATA = "/api/me/"  # all a plain member may open, plus the two routes below
MEMBER_ROUTES = {"/api/session", "/api/sync/status"}


async def test_every_route_denies_by_default(client: httpx.AsyncClient, seeded: None) -> None:
    """Walks the app's own route list, so a route added without a guard fails here."""
    paths = client._transport.app.openapi()["paths"]  # type: ignore[attr-defined]
    routes = [
        (method, path.replace("{login}", "bob").replace("{target}", "credits").replace("{action}", "run"))
        for path, methods in paths.items()
        if path not in PUBLIC
        for method in methods
    ]
    assert len(routes) > 20  # the walk really found the API
    client.cookies.clear()
    for method, path in routes:
        assert (await client.request(method, path)).status_code == 401, (method, path)

    await sign_in(client, "alice")  # a plain member with a seat
    for method, path in routes:
        expected = 200 if path.startswith(OWN_DATA) or path in MEMBER_ROUTES else 403
        assert (await client.request(method, path)).status_code == expected, (method, path)
