"""IdentityProvider backed by the GitHub App's user authorization."""

import logging
from collections.abc import Iterable
from urllib.parse import quote, urlencode

import httpx

from copilot_metrics.identity.domain import GitHubUser, OrgMembership, SignInFailed
from copilot_metrics.identity.ports import IdentityProvider
from copilot_metrics.settings import ConfigurationError, GitHubSettings
from copilot_metrics.shared.adapters.outbound.github.http_client import bearer
from copilot_metrics.shared.kernel import Frozen

log = logging.getLogger(__name__)


class _TokenResponse(Frozen):
    access_token: str | None = None
    error: str | None = None
    error_description: str | None = None


class _Membership(Frozen):
    state: str
    role: str


class _TeamMembership(Frozen):
    state: str


class GitHubIdentityProvider(IdentityProvider):
    def __init__(self, settings: GitHubSettings, client: httpx.AsyncClient) -> None:
        if not settings.app_client_id or not settings.app_client_secret:
            raise ConfigurationError("GitHub App client id and secret are required")
        self._settings = settings
        self._client = client
        self._client_id = settings.app_client_id
        self._client_secret = settings.app_client_secret.get_secret_value()

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode({"client_id": self._client_id, "redirect_uri": redirect_uri, "state": state})
        return f"{self._settings.web_url}/login/oauth/authorize?{query}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> str:
        response = await self._client.post(
            f"{self._settings.web_url}/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        token = _TokenResponse.model_validate_json(response.content)
        if not token.access_token:
            raise SignInFailed(token.error_description or token.error or "GitHub returned no token")
        return token.access_token

    async def fetch_user(self, token: str) -> GitHubUser:
        response = await self._client.get("/user", headers=bearer(token))
        response.raise_for_status()
        return GitHubUser.model_validate_json(response.content)

    async def fetch_org_membership(self, token: str) -> OrgMembership:
        response = await self._client.get(f"/user/memberships/orgs/{self._settings.org}", headers=bearer(token))
        if response.status_code in (403, 404):
            return OrgMembership(active=False)
        response.raise_for_status()
        membership = _Membership.model_validate_json(response.content)
        return OrgMembership(active=membership.state == "active", owner=membership.role == "admin")

    async def fetch_team_memberships(self, token: str, login: str, teams: Iterable[str]) -> frozenset[str]:
        """One call per team; GitHub counts members of child teams too. Secret teams are
        visible to their own members, so the user token can always see a team they belong to."""
        org = quote(self._settings.org, safe="")
        found: set[str] = set()
        for slug in teams:
            path = f"/orgs/{org}/teams/{quote(slug, safe='')}/memberships/{quote(login, safe='')}"
            response = await self._client.get(path, headers=bearer(token))
            if response.status_code == 404:  # not a member, or no such team visible to them
                continue
            if response.status_code == 403:
                log.warning("GitHub refused the team membership check for %r (does the App have Members: read?)", slug)
                continue
            response.raise_for_status()
            if _TeamMembership.model_validate_json(response.content).state == "active":
                found.add(slug.lower())
        return frozenset(found)

    async def revoke(self, token: str) -> None:
        response = await self._client.request(
            "DELETE",
            f"/applications/{self._client_id}/token",
            auth=(self._client_id, self._client_secret),
            json={"access_token": token},
        )
        if response.status_code not in (204, 404, 422):
            response.raise_for_status()
