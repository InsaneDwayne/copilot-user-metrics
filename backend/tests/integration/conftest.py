"""Integration tests against a real Postgres (TEST_DATABASE_URL, owner role).

They migrate the test database from scratch, write data as the worker role and
read it through the API exactly as a browser would - so row-level security,
grants and the session guards are all exercised together.
"""

import os
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest
from alembic import command
from alembic.config import Config
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from copilot_metrics.api import create_app
from copilot_metrics.cli import BACKEND_ROOT
from copilot_metrics.identity.domain import GitHubUser, OrgMembership
from copilot_metrics.identity.ports import IdentityProvider
from copilot_metrics.settings import AccessSettings, ApiSettings, GitHubSettings, SessionSettings, Settings
from copilot_metrics.shared.adapters.outbound.postgres.engine import create_engine, sqlalchemy_url
from copilot_metrics.shared.adapters.outbound.postgres.tables import metadata

from ..clock import FixedClock
from .seed import NOW, seeded  # noqa: F401  (fixture re-exported for every integration test)


class TestDatabase(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEST_", extra="ignore")
    __test__ = False  # not a pytest test class

    database_url: PostgresDsn = PostgresDsn("postgresql://copilot:copilot@db:5432/copilot_metrics_test")
    api_role: str = "copilot_api:copilot_api"
    worker_role: str = "copilot_worker:copilot_worker"

    def as_role(self, credentials: str) -> str:
        parts = urlsplit(str(self.database_url))
        return urlunsplit(parts._replace(netloc=f"{credentials}@{parts.hostname}:{parts.port or 5432}"))


DB = TestDatabase()


class FakeGitHub(IdentityProvider):
    """Stands in for GitHub's OAuth: the "code" is simply the login to sign in as."""

    MEMBER = OrgMembership(active=True)
    PEOPLE: dict[str, tuple[int, OrgMembership, frozenset[str]]] = {
        "alice": (1, MEMBER, frozenset()),
        "bob": (2, MEMBER, frozenset()),
        "owner": (3, OrgMembership(active=True, owner=True), frozenset({"copilot-readers"})),
        "stranger": (4, OrgMembership(active=False), frozenset({"copilot-readers"})),
        "orgreader": (5, MEMBER, frozenset({"copilot-readers"})),
        "teamadmin": (6, MEMBER, frozenset({"copilot-admins", "copilot-readers"})),
    }

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://github.test/login/oauth/authorize?state={state}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        return code

    async def fetch_user(self, token: str) -> GitHubUser:
        return GitHubUser(id=self.PEOPLE[token][0], login=token)

    async def fetch_org_membership(self, token: str) -> OrgMembership:
        return self.PEOPLE[token][1]

    async def fetch_team_memberships(self, token: str, login: str, teams: Iterable[str]) -> frozenset[str]:
        return self.PEOPLE[token][2] & frozenset(teams)

    async def revoke(self, token: str) -> None:
        return None


@pytest.fixture(scope="session")
def migrated() -> None:
    owner_url = sqlalchemy_url(DB.database_url)
    try:
        create_sync_engine(owner_url).connect().close()
    except Exception as exc:
        # CI sets TEST_DATABASE_REQUIRED so a broken database fails the run instead of skipping it.
        if os.environ.get("TEST_DATABASE_REQUIRED"):
            raise
        pytest.skip(f"test database unavailable: {exc}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", owner_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def clean(migrated: None) -> None:
    engine = create_sync_engine(sqlalchemy_url(DB.database_url))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(metadata.tables)}"))
    engine.dispose()


@pytest.fixture
async def worker_engine(clean: None) -> AsyncGenerator[AsyncEngine]:
    engine = create_engine(DB.as_role(DB.worker_role))
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_engine(clean: None) -> AsyncGenerator[AsyncEngine]:
    engine = create_engine(DB.as_role(DB.api_role))
    yield engine
    await engine.dispose()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@asynccontextmanager
async def _client(clock: FixedClock, access: AccessSettings) -> AsyncGenerator[httpx.AsyncClient]:
    settings = Settings(
        github=GitHubSettings(org="acme-labs", app_client_id="id", app_client_secret="secret"),
        api=ApiSettings(database_url=DB.as_role(DB.api_role), public_url="http://testserver", allow_http=True),
        session=SessionSettings(secret="test-secret-" + "x" * 32),
        access=access,
    )
    app = create_app(settings, clock=clock, identity_provider=FakeGitHub())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest.fixture
async def client(clean: None, clock: FixedClock) -> AsyncGenerator[httpx.AsyncClient]:
    """Teams mapped: ``copilot-admins`` are admins, ``copilot-readers`` organization readers."""
    access = AccessSettings(admin_teams=("copilot-admins",), org_reader_teams=("copilot-readers",))
    async with _client(clock, access) as http:
        yield http


@pytest.fixture
async def client_without_teams(clean: None, clock: FixedClock) -> AsyncGenerator[httpx.AsyncClient]:
    """The default deployment: no team mapped, so only org owners see org data."""
    async with _client(clock, AccessSettings()) as http:
        yield http


async def sign_in(client: httpx.AsyncClient, login: str) -> None:
    client.cookies.clear()
    start = await client.get("/auth/github")
    assert start.status_code == 307
    state = start.headers["location"].split("state=")[1]
    done = await client.get("/auth/github/callback", params={"code": login, "state": state})
    assert done.status_code == 307
    assert done.headers["location"] == "/"
