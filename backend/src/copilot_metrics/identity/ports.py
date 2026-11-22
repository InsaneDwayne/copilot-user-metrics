from abc import ABC, abstractmethod
from collections.abc import Iterable

from copilot_metrics.identity.domain import GitHubUser, OrgMembership
from copilot_metrics.shared.kernel import Viewer


class IdentityProvider(ABC):
    """GitHub's user authorization (OAuth web flow) for the GitHub App."""

    @abstractmethod
    def authorize_url(self, *, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def fetch_user(self, token: str) -> GitHubUser: ...

    @abstractmethod
    async def fetch_org_membership(self, token: str) -> OrgMembership: ...

    @abstractmethod
    async def fetch_team_memberships(self, token: str, login: str, teams: Iterable[str]) -> frozenset[str]:
        """Which of the org's ``teams`` (slugs) ``login`` is an active member of, lower case."""

    @abstractmethod
    async def revoke(self, token: str) -> None: ...


class SeatDirectory(ABC):
    @abstractmethod
    async def has_active_seat(self, viewer: Viewer) -> bool: ...
