"""GitHubOrgClient against a fake GitHub: token handling, rate limits, pagination, report downloads."""

import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from copilot_metrics.settings import GitHubSettings
from copilot_metrics.shared.adapters.outbound.github.http_client import github_client
from copilot_metrics.sync.adapters.outbound.github import org_client
from copilot_metrics.sync.adapters.outbound.github.org_client import AppTokenProvider, GitHubOrgClient

API = "https://api.github.test"
DOWNLOADS = "https://reports.example.test"
SETTINGS = GitHubSettings(org="acme-labs", api_url=API)
APP_ID = 42

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY = _KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()

Handler = Callable[[httpx.Request], httpx.Response]


@dataclass
class FakeGitHub:
    """Answers the App token endpoints itself; every other request goes to ``routes``."""

    routes: dict[str, Handler] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    tokens_minted: int = 0
    token_lifetime: timedelta = timedelta(hours=1)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/orgs/acme-labs/installation":
            self._assert_app_jwt(request)
            return httpx.Response(200, json={"id": 7})
        if path == "/app/installations/7/access_tokens":
            self._assert_app_jwt(request)
            self.tokens_minted += 1
            expires_at = datetime.now(UTC) + self.token_lifetime
            return httpx.Response(
                201, json={"token": f"inst-{self.tokens_minted}", "expires_at": expires_at.isoformat()}
            )
        return self.routes[f"{request.url.host}{path}"](request)

    def _assert_app_jwt(self, request: httpx.Request) -> None:
        scheme, _, token = request.headers["authorization"].partition(" ")
        assert scheme == "Bearer"
        # Signed with the App key; GitHub accepts at most 10 minutes between iat and exp.
        claims = jwt.decode(token, _KEY.public_key(), algorithms=["RS256"], options={"verify_exp": False})
        assert claims["iss"] == str(APP_ID)
        assert 0 < claims["exp"] - claims["iat"] <= 600

    def to(self, host: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host]


@pytest.fixture
def fake() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
async def client(fake: FakeGitHub) -> AsyncGenerator[GitHubOrgClient]:
    transport = httpx.MockTransport(fake.handle)
    async with (
        github_client(SETTINGS, transport) as api,
        httpx.AsyncClient(transport=transport, follow_redirects=True) as downloads,
    ):
        yield GitHubOrgClient(SETTINGS, AppTokenProvider(SETTINGS, APP_ID, PRIVATE_KEY, api), api, downloads)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waited: list[float] = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr("asyncio.sleep", sleep)  # what org_client awaits
    return waited


def _json(body: Any, status: int = 200, headers: dict[str, str] | None = None) -> Handler:
    return lambda _: httpx.Response(status, json=body, headers=headers)


def _billing() -> dict[str, Any]:
    return {"seat_breakdown": {"total": 3}, "plan_type": "business"}


# ---------------------------------------------------------------- report downloads


async def test_report_downloads_never_carry_the_installation_token(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    links = [f"{DOWNLOADS}/r/1.ndjson?sig=abc", f"{DOWNLOADS}/r/2.ndjson?sig=def"]
    fake.routes["api.github.test/orgs/acme-labs/copilot/metrics/reports/user-teams-1-day"] = _json(
        {"download_links": links, "report_day": "2026-11-17"}
    )
    line = '{{"day": "2026-11-17", "user_id": {id}, "user_login": "u{id}", "slug": "core"}}'
    fake.routes["reports.example.test/r/1.ndjson"] = lambda _: httpx.Response(200, text=line.format(id=1) + "\n")
    fake.routes["reports.example.test/r/2.ndjson"] = lambda _: httpx.Response(200, text=line.format(id=2) + "\n\n")

    records = await client.user_teams(date(2026, 11, 17))

    assert [r.user_login for r in records] == ["u1", "u2"]
    downloads = fake.to("reports.example.test")
    assert [str(r.url) for r in downloads] == links
    for request in downloads:
        assert "authorization" not in request.headers
        assert "inst-1" not in str(request.headers)
    (report,) = [r for r in fake.to("api.github.test") if "metrics/reports" in r.url.path]
    assert report.headers["authorization"] == "Bearer inst-1"
    assert report.url.params["day"] == "2026-11-17"


async def test_a_redirected_download_does_not_pick_up_the_token(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/metrics/reports/users-1-day"] = _json(
        {"download_links": [f"{DOWNLOADS}/start"]}
    )
    fake.routes["reports.example.test/start"] = lambda _: httpx.Response(302, headers={"location": f"{DOWNLOADS}/end"})
    fake.routes["reports.example.test/end"] = lambda _: httpx.Response(200, text="")

    assert await client.user_metrics(date(2026, 11, 17)) == []
    assert [r.url.path for r in fake.to("reports.example.test")] == ["/start", "/end"]
    assert all("authorization" not in r.headers for r in fake.to("reports.example.test"))


@pytest.mark.parametrize("status", [204, 404])
async def test_a_day_without_a_report_is_empty(fake: FakeGitHub, client: GitHubOrgClient, status: int) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/metrics/reports/users-1-day"] = lambda _: httpx.Response(status)

    assert await client.user_metrics(date(2026, 11, 17)) == []
    assert fake.to("reports.example.test") == []


async def test_a_failed_download_raises(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/metrics/reports/users-1-day"] = _json(
        {"download_links": [f"{DOWNLOADS}/gone"]}
    )
    fake.routes["reports.example.test/gone"] = lambda _: httpx.Response(403)

    with pytest.raises(httpx.HTTPStatusError):
        await client.user_metrics(date(2026, 11, 17))


async def test_a_report_format_change_is_logged(
    fake: FakeGitHub, client: GitHubOrgClient, caplog: pytest.LogCaptureFixture
) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/metrics/reports/users-1-day"] = _json(
        {"download_links": [f"{DOWNLOADS}/day"]}
    )
    renamed = (Path(__file__).parent.parent / "fixtures" / "users-1-day.ndjson").read_text()
    renamed = renamed.replace('"used_chat"', '"used_chat_panel"')
    fake.routes["reports.example.test/day"] = lambda _: httpx.Response(200, text=renamed)

    with caplog.at_level(logging.WARNING, logger=org_client.__name__):
        [record] = await client.user_metrics(date(2026, 11, 17))

    assert record.used_chat is False
    [warning] = caplog.messages
    assert "users-1-day 2026-11-17: no record has used_chat," in warning
    assert "used_chat_panel" in warning


# ---------------------------------------------------------------- installation token


async def test_the_installation_token_is_minted_once_and_reused(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = _json(_billing())

    await client.copilot_billing()
    await client.copilot_billing()

    assert fake.tokens_minted == 1
    calls = [r for r in fake.requests if r.url.path == "/orgs/acme-labs/copilot/billing"]
    assert [r.headers["authorization"] for r in calls] == ["Bearer inst-1", "Bearer inst-1"]


async def test_a_token_close_to_expiry_is_replaced(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    fake.token_lifetime = timedelta(minutes=4)  # within the 5-minute safety margin
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = _json(_billing())

    await client.copilot_billing()
    await client.copilot_billing()

    assert fake.tokens_minted == 2
    calls = [r for r in fake.requests if r.url.path == "/orgs/acme-labs/copilot/billing"]
    assert [r.headers["authorization"] for r in calls] == ["Bearer inst-1", "Bearer inst-2"]


async def test_a_refused_installation_lookup_raises() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    async with github_client(SETTINGS, httpx.MockTransport(handle)) as api:
        tokens = AppTokenProvider(SETTINGS, APP_ID, PRIVATE_KEY, api)
        with pytest.raises(httpx.HTTPStatusError):
            await tokens.token()


# ---------------------------------------------------------------- rate limits


async def test_retry_after_is_honoured(fake: FakeGitHub, client: GitHubOrgClient, sleeps: list[float]) -> None:
    answers = iter([httpx.Response(429, headers={"retry-after": "12"}), httpx.Response(200, json=_billing())])
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = lambda _: next(answers)

    billing = await client.copilot_billing()

    assert billing.seat_breakdown.total == 3
    assert sleeps == [12.0]


async def test_an_exhausted_quota_waits_for_the_reset(
    fake: FakeGitHub, client: GitHubOrgClient, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("time.time", lambda: 1_000.0)
    limited = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"}
    answers = iter([httpx.Response(403, headers=limited), httpx.Response(200, json=_billing())])
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = lambda _: next(answers)

    await client.copilot_billing()

    assert sleeps == [30.0]


async def test_waits_are_capped(fake: FakeGitHub, client: GitHubOrgClient, sleeps: list[float]) -> None:
    answers = iter([httpx.Response(429, headers={"retry-after": "86400"}), httpx.Response(200, json=_billing())])
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = lambda _: next(answers)

    await client.copilot_billing()

    assert sleeps == [org_client._MAX_RATE_LIMIT_WAIT]


async def test_gives_up_after_the_retries(fake: FakeGitHub, client: GitHubOrgClient, sleeps: list[float]) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = _json({}, 429, {"retry-after": "1"})

    with pytest.raises(httpx.HTTPStatusError):
        await client.copilot_billing()

    assert len(sleeps) == org_client._RETRIES


async def test_a_plain_forbidden_is_not_retried(fake: FakeGitHub, client: GitHubOrgClient, sleeps: list[float]) -> None:
    fake.routes["api.github.test/orgs/acme-labs/copilot/billing"] = _json({"message": "Forbidden"}, 403)

    with pytest.raises(httpx.HTTPStatusError):
        await client.copilot_billing()

    assert sleeps == []


# ---------------------------------------------------------------- pagination


async def test_seats_follow_the_next_link(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    def seats(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        body = {"total_seats": 2, "seats": [{"assignee": {"id": int(page), "login": f"user{page}"}}]}
        if page == "1":
            assert request.url.params["per_page"] == "100"
            next_url = f"{API}/orgs/acme-labs/copilot/billing/seats?per_page=100&page=2"
            return httpx.Response(200, json=body, headers={"link": f'<{next_url}>; rel="next"'})
        return httpx.Response(200, json=body)

    fake.routes["api.github.test/orgs/acme-labs/copilot/billing/seats"] = seats

    result = await client.seats()

    assert [s.assignee.login for s in result if s.assignee] == ["user1", "user2"]
    assert all(r.headers["authorization"] == "Bearer inst-1" for r in fake.requests if "seats" in r.url.path)


async def test_budgets_are_merged_across_pages(fake: FakeGitHub, client: GitHubOrgClient) -> None:
    def budgets(request: httpx.Request) -> httpx.Response:
        assert request.url.params["user"] == "mona"
        page = int(request.url.params["page"])
        budget = {"id": f"b{page}", "budget_scope": "organization"}
        return httpx.Response(200, json={"budgets": [budget], "has_next_page": page < 3})

    fake.routes["api.github.test/organizations/acme-labs/settings/billing/budgets"] = budgets

    result = await client.budgets(user="mona")

    assert [b.id for b in result.budgets] == ["b1", "b2", "b3"]
    assert result.has_next_page is False
