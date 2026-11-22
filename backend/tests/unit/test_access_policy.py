from collections.abc import Iterable
from datetime import UTC, datetime

import pytest

from copilot_metrics.identity.domain import Access, AccessPolicy, GitHubUser, OrgMembership
from copilot_metrics.identity.ports import IdentityProvider
from copilot_metrics.identity.service import SignInService
from copilot_metrics.settings import AccessSettings
from copilot_metrics.shared.kernel import Role
from tests.clock import FixedClock

MEMBER = OrgMembership(active=True)
OWNER = OrgMembership(active=True, owner=True)
GONE = OrgMembership(active=False)
POLICY = AccessPolicy(admin_teams=("App-Admins",), org_reader_teams=("Finance", "leads", "finance"))
NONE: frozenset[str] = frozenset()


@pytest.mark.parametrize(
    ("membership", "teams", "role"),
    [
        (GONE, frozenset({"finance"}), Role.OUTSIDER),  # teams never admit outsiders
        (OWNER, NONE, Role.ADMIN),
        (OWNER, frozenset({"finance"}), Role.ADMIN),  # owners stay admins in an organization reader team
        (MEMBER, NONE, Role.MEMBER),
        (MEMBER, frozenset({"finance"}), Role.ORG_READER),  # slugs compare case-insensitively
        (MEMBER, frozenset({"leads"}), Role.ORG_READER),
        (MEMBER, frozenset({"other"}), Role.MEMBER),
        (MEMBER, frozenset({"app-admins"}), Role.ADMIN),  # no owner rights needed
        (MEMBER, frozenset({"app-admins", "finance"}), Role.ADMIN),  # admin wins over organization reader
        (GONE, frozenset({"app-admins"}), Role.OUTSIDER),
    ],
)
def test_role_from_membership_and_teams(membership: OrgMembership, teams: frozenset[str], role: Role) -> None:
    assert POLICY.role(membership, teams) is role


def test_no_team_lookup_when_it_cannot_change_the_role() -> None:
    assert POLICY.role_without_teams(GONE) is Role.OUTSIDER
    assert POLICY.role_without_teams(OWNER) is Role.ADMIN
    assert POLICY.role_without_teams(MEMBER) is None
    assert AccessPolicy().role_without_teams(MEMBER) is Role.MEMBER


def test_team_slugs_are_listed_once_in_lower_case() -> None:
    assert POLICY.teams == ("app-admins", "finance", "leads")


def test_owners_are_admins_without_any_team() -> None:
    assert AccessPolicy(admin_teams=("app-admins",)).role(OWNER, NONE) is Role.ADMIN
    assert AccessPolicy(admin_teams=("app-admins",)).role_without_teams(MEMBER) is None


def test_access_per_role() -> None:
    assert Access.of(Role.ADMIN, has_seat=False).model_dump() == {
        "can_view_own_usage": False,
        "can_view_admin": True,
        "can_manage_sync": True,
    }
    assert Access.of(Role.ORG_READER, has_seat=True).model_dump() == {
        "can_view_own_usage": True,
        "can_view_admin": True,
        "can_manage_sync": False,
    }
    assert Access.of(Role.MEMBER, has_seat=True).can_view_admin is False


def test_settings_read_comma_separated_team_slugs(monkeypatch: pytest.MonkeyPatch) -> None:
    from copilot_metrics.settings import Settings

    monkeypatch.setenv("GITHUB_ORG", "acme-labs")
    monkeypatch.setenv("ACCESS_ADMIN_TEAMS", "app-admins")
    monkeypatch.setenv("ACCESS_ORG_READER_TEAMS", " finance , team-leads,")
    access = Settings(_env_file=None).access
    assert access == AccessSettings(admin_teams=("app-admins",), org_reader_teams=("finance", "team-leads"))


class _GitHub(IdentityProvider):
    def __init__(self, membership: OrgMembership, teams: frozenset[str]) -> None:
        self.membership = membership
        self.member_of = teams
        self.team_lookups: list[tuple[str, ...]] = []

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        return ""

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        return "token"

    async def fetch_user(self, token: str) -> GitHubUser:
        return GitHubUser(id=7, login="carol")

    async def fetch_org_membership(self, token: str) -> OrgMembership:
        return self.membership

    async def fetch_team_memberships(self, token: str, login: str, teams: Iterable[str]) -> frozenset[str]:
        asked = tuple(teams)
        self.team_lookups.append(asked)
        return self.member_of & frozenset(asked)

    async def revoke(self, token: str) -> None:
        return None


async def test_sign_in_maps_an_organization_reader_team_to_the_role() -> None:
    github = _GitHub(MEMBER, frozenset({"finance"}))
    user = await SignInService(github, FixedClock(datetime(2026, 11, 17, tzinfo=UTC)), POLICY).complete(
        code="c", redirect_uri="r"
    )
    assert user.role is Role.ORG_READER
    assert github.team_lookups == [("app-admins", "finance", "leads")]


async def test_sign_in_skips_team_lookups_for_owners_and_outsiders() -> None:
    for membership in (OWNER, GONE):
        github = _GitHub(membership, frozenset({"finance"}))
        await SignInService(github, FixedClock(datetime(2026, 11, 17, tzinfo=UTC)), POLICY).complete(
            code="c", redirect_uri="r"
        )
        assert github.team_lookups == []


async def test_github_team_lookup_counts_active_memberships_only() -> None:
    import httpx

    from copilot_metrics.identity.adapters.outbound.github.identity_provider import GitHubIdentityProvider
    from copilot_metrics.settings import GitHubSettings

    answers = {
        "/orgs/acme-labs/teams/finance/memberships/carol": (404, {"message": "Not Found"}),
        "/orgs/acme-labs/teams/leads/memberships/carol": (200, {"state": "pending", "role": "member"}),
        "/orgs/acme-labs/teams/ops/memberships/carol": (200, {"state": "active", "role": "member"}),
        "/user/memberships/orgs/acme-labs": (200, {"state": "active", "role": "admin"}),
    }

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer token"
        status, body = answers[request.url.path]
        return httpx.Response(status, json=body)

    settings = GitHubSettings(org="acme-labs", app_client_id="id", app_client_secret="secret")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), base_url="https://api.github.test") as client:
        github = GitHubIdentityProvider(settings, client)
        teams = ("finance", "leads", "ops")
        assert await github.fetch_team_memberships("token", "carol", teams) == frozenset({"ops"})
        assert await github.fetch_org_membership("token") == OWNER
