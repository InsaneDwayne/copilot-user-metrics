"""Who a signed-in person is and what that allows."""

from datetime import datetime, timedelta

from pydantic import field_validator

from copilot_metrics.shared.errors import AccessDenied, DomainError, NotAuthenticated
from copilot_metrics.shared.kernel import Frozen, Role, Viewer

# ---------------------------------------------------------------- errors


class NotSignedIn(NotAuthenticated):
    code = "not_signed_in"
    default_message = "Not signed in"


class SessionInvalid(NotAuthenticated):
    code = "session_invalid"
    default_message = "Session is invalid"


class SessionExpired(NotAuthenticated):
    code = "session_expired"
    default_message = "Session expired"


class NoSeat(AccessDenied):
    code = "no_seat"
    default_message = "No Copilot seat on record"


class NotOrgMember(AccessDenied):
    code = "not_org_member"
    default_message = "Not a member of the organization"


class OrgReadersOnly(AccessDenied):
    code = "org_readers_only"
    default_message = "Organization readers and admins only"


class AdminsOnly(AccessDenied):
    code = "admins_only"
    default_message = "Admins only"


class SignInFailed(DomainError):
    """GitHub refused the OAuth exchange. Handled by the callback, which redirects."""

    code = "sign_in_failed"
    default_message = "GitHub sign-in failed"


# ---------------------------------------------------------------- models


class GitHubUser(Frozen):
    id: int
    login: str
    name: str | None = None
    avatar_url: str | None = None


class OrgMembership(Frozen):
    """The signed-in person's standing in the org, as GitHub reports it."""

    active: bool  # an active member (a pending invitation is not)
    owner: bool = False


class AccessPolicy(Frozen):
    """Maps org ownership and team membership to a ``Role``.

    Org owners are always admins. Members of an admin team (``ACCESS_ADMIN_TEAMS``) are admins
    too, so running the app needs no owner rights. Members of an organization reader team
    (``ACCESS_ORG_READER_TEAMS``) are organization readers. Teams never admit people outside the org.
    """

    admin_teams: tuple[str, ...] = ()
    org_reader_teams: tuple[str, ...] = ()

    @field_validator("admin_teams", "org_reader_teams")
    @classmethod
    def _normalized(cls, slugs: tuple[str, ...]) -> tuple[str, ...]:
        """GitHub team slugs are case-insensitive: keep them lower case, without duplicates."""
        return tuple(dict.fromkeys(slug.lower() for slug in slugs))

    def role_without_teams(self, membership: OrgMembership) -> Role | None:
        """The role if no team lookup can change it, else ``None``."""
        if not membership.active:
            return Role.OUTSIDER
        if membership.owner:
            return Role.ADMIN
        if not self.teams:
            return Role.MEMBER
        return None

    def role(self, membership: OrgMembership, teams: frozenset[str]) -> Role:
        """``teams``: the configured team slugs (lower case) the person is an active member of."""
        if (known := self.role_without_teams(membership)) is not None:
            return known
        if teams.intersection(self.admin_teams):
            return Role.ADMIN
        if teams.intersection(self.org_reader_teams):
            return Role.ORG_READER
        return Role.MEMBER

    @property
    def teams(self) -> tuple[str, ...]:
        """Every team slug to look up, admin teams first, lower case, without duplicates."""
        return tuple(dict.fromkeys((*self.admin_teams, *self.org_reader_teams)))


class SessionUser(Frozen):
    """What the session cookie holds. Never contains a GitHub token."""

    user_id: int
    login: str
    name: str | None
    avatar_url: str | None
    role: Role
    signed_in_at: datetime

    def viewer(self) -> Viewer:
        return Viewer(user_id=self.user_id, login=self.login, role=self.role)

    def is_expired(self, now: datetime, max_age: timedelta) -> bool:
        """The org role is only verified at sign-in, so sessions expire absolutely."""
        return now - self.signed_in_at > max_age


class Access(Frozen):
    """What the UI may open for this person."""

    can_view_own_usage: bool
    can_view_admin: bool  # the admin console: every member's usage (admins and organization readers)
    can_manage_sync: bool  # the admin console's Sync page (admins only)

    @classmethod
    def of(cls, role: Role, has_seat: bool) -> Access:
        return cls(
            can_view_own_usage=has_seat and role is not Role.OUTSIDER,
            can_view_admin=role.can_read_org,
            can_manage_sync=role is Role.ADMIN,
        )
