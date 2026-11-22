import logging

from copilot_metrics.identity.domain import AccessPolicy, SessionUser
from copilot_metrics.identity.ports import IdentityProvider
from copilot_metrics.shared.kernel import Clock

log = logging.getLogger(__name__)


class SignInService:
    def __init__(self, provider: IdentityProvider, clock: Clock, policy: AccessPolicy) -> None:
        self._provider = provider
        self._clock = clock
        self._policy = policy

    def start(self, *, state: str, redirect_uri: str) -> str:
        return self._provider.authorize_url(state=state, redirect_uri=redirect_uri)

    async def complete(self, *, code: str, redirect_uri: str) -> SessionUser:
        """Exchange the code, read identity, org membership and teams, then drop the user token."""
        token = await self._provider.exchange_code(code=code, redirect_uri=redirect_uri)
        try:
            user = await self._provider.fetch_user(token)
            membership = await self._provider.fetch_org_membership(token)
            role = self._policy.role_without_teams(membership)
            if role is None:  # only look teams up when they can change the outcome
                teams = await self._provider.fetch_team_memberships(token, user.login, self._policy.teams)
                role = self._policy.role(membership, teams)
        finally:
            try:
                await self._provider.revoke(token)
            except Exception:  # best effort; the token expires on its own
                log.warning("could not revoke GitHub user token", exc_info=True)
        log.info("sign-in: %s as %s", user.login, role)
        return SessionUser(
            user_id=user.id,
            login=user.login,
            name=user.name,
            avatar_url=user.avatar_url,
            role=role,
            signed_in_at=self._clock.now(),
        )
