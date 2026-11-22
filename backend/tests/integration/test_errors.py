"""Every error leaves the API in one shape: ``{"code", "detail"}`` with the mapped status."""

import httpx

from .conftest import sign_in


async def test_not_signed_in_is_401_with_a_code(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me/summary")
    assert response.status_code == 401
    assert response.json() == {"code": "not_signed_in", "detail": "Not signed in"}


async def test_access_denied_is_403(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    response = await client.get("/api/admin/members")
    assert response.status_code == 403
    assert response.json()["code"] == "org_readers_only"


async def test_unknown_member_is_404(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    response = await client.get("/api/admin/members/nobody")
    assert response.status_code == 404
    assert response.json() == {"code": "member_not_found", "detail": "No seat on record for this login"}


async def test_impossible_period_is_422(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    response = await client.get("/api/me/summary", params={"from": "2026-05-10", "to": "2026-05-01"})
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_period", "detail": "period end is before its start"}


async def test_malformed_query_is_422_in_the_same_shape(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "alice")
    response = await client.get("/api/me/summary", params={"from": "not-a-date"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_request"
    assert body["detail"].startswith("from:")


async def test_unknown_route_is_404_in_the_same_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_oversized_page_is_422(client: httpx.AsyncClient, seeded: None) -> None:
    await sign_in(client, "owner")
    response = await client.get("/api/admin/members", params={"size": 1000})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


async def test_api_docs_are_off_by_default(client: httpx.AsyncClient) -> None:
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert (await client.get(path)).status_code == 404, path
